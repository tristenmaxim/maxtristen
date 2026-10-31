import concurrent.futures
import asyncio
import os
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('GEMINI_API_KEY', 'test')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test')
os.environ.setdefault('NOTION_TOKEN', 'test')
os.environ.setdefault('NOTION_DATABASE_ID', 'test')

import db
import library
import telegram
import worker


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db.DB_PATH = os.path.join(self.temp.name, 'test.db')
        db.init_db()

    def tearDown(self):
        self.temp.cleanup()

    def test_batch_deduplicates_and_redelivery_is_idempotent(self):
        with patch.object(db, 'get_wallet_for_telegram', return_value='wallet'):
            parsed = telegram.parse_update({'message': {'from': {'id': 5}, 'chat': {'id': 7},
                'text': 'https://example.com/a\nhttps://example.com/b\nhttps://example.com/a'}})
        self.assertEqual(parsed['urls'], ['https://example.com/a', 'https://example.com/b'])
        self.assertEqual(db.enqueue_telegram_urls('wallet', parsed['urls'], 7, 123), (2, 0, False))
        self.assertEqual(db.enqueue_telegram_urls('wallet', parsed['urls'], 7, 123), (0, 0, True))
        self.assertEqual(db.enqueue_telegram_urls('wallet', parsed['urls'], 7, 124), (0, 2, False))
        self.assertEqual(len(db.list_entries('wallet')), 2)

    def test_concurrent_batches_do_not_create_duplicate_jobs(self):
        def submit(i):
            return db.enqueue_telegram_urls('wallet', ['https://example.com/a'], 7, i)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(submit, range(20)))
        self.assertEqual(sum(result[0] for result in results), 1)
        self.assertEqual(len(db.list_entries('wallet')), 1)

    def test_retry_and_recovery(self):
        entry_id = db.create_entry('wallet', 'url', 'https://example.com/a', queued=True)
        with patch.object(worker.pipeline, 'process_entry', side_effect=TimeoutError('temporary')), \
             patch.object(worker, 'notify') as notify, patch.object(worker.log, 'exception'):
            first = db.claim_job()
            worker.process_job(first)
            row = db.get_entry(entry_id)
            self.assertEqual((row['status'], row['job_state'], row['attempts']), ('queued', 'pending', 1))
            self.assertIsNone(db.claim_job())
            with db._connect() as conn:
                conn.execute('UPDATE entries SET next_attempt = NULL WHERE id = ?', (entry_id,))
            self.assertEqual(db.claim_job()['attempts'], 2)
            db.recover_jobs()
            resumed = db.claim_job()
            self.assertEqual(resumed['attempts'], 2)
            db.retry_job(entry_id, 'temporary', 0)
            third = db.claim_job()
            self.assertEqual(third['attempts'], 3)
            worker.process_job(third)
            row = db.get_entry(entry_id)
            self.assertEqual((row['status'], row['job_state']), ('error', 'failed'))
            notify.assert_called_once()
        self.assertEqual(db.enqueue_telegram_urls('wallet', ['https://example.com/a'], 7, 125), (1, 0, False))
        row = db.get_entry(entry_id)
        self.assertEqual((row['job_state'], row['attempts']), ('pending', 0))
        self.assertEqual(len(db.list_entries('wallet')), 1)

    def test_telegram_file_redelivery_does_not_duplicate_job(self):
        self.assertTrue(db.enqueue_telegram_file('wallet', 'file-id', 7, 501))
        self.assertFalse(db.enqueue_telegram_file('wallet', 'file-id', 7, 501))
        self.assertEqual(len(db.list_entries('wallet')), 1)

    def test_webhook_schedules_each_link_once(self):
        import main
        class Request:
            async def json(self):
                return {'update_id': 66, 'message': {'from': {'id': 1}, 'chat': {'id': 2},
                    'text': 'https://example.com/1\nhttps://example.com/2'}}
        with patch.object(db, 'get_wallet_for_telegram', return_value='wallet'), \
             patch.object(telegram, 'send_message') as send, patch.object(worker, 'wake') as wake:
            asyncio.run(main.telegram_webhook(Request()))
            asyncio.run(main.telegram_webhook(Request()))
        self.assertEqual(len(db.list_entries('wallet')), 2)
        send.assert_called_once_with(2, 'Добавлено в очередь: 2.')
        wake.assert_called_once()

    def test_worker_processes_batch_in_order(self):
        db.enqueue_telegram_urls('wallet', ['https://example.com/a', 'https://example.com/b', 'https://example.com/c'], 7, 71)
        seen = []
        def process(entry_id):
            seen.append(entry_id)
            db.update_entry(entry_id, status='done', transcript='ok')
        with patch.object(worker.pipeline, 'process_entry', side_effect=process), patch.object(worker, 'notify'):
            worker.start()
            worker.wake()
            try:
                deadline = time.monotonic() + 5
                while len(seen) < 3 and time.monotonic() < deadline:
                    time.sleep(0.01)
            finally:
                worker.stop()
                worker._thread.join(timeout=5)
        self.assertEqual(seen, sorted(seen))
        self.assertEqual(len(seen), 3)
        self.assertTrue(all(db.get_entry(i)['job_state'] == 'done' for i in seen))

    def test_uploaded_media_checkpoint(self):
        saved = []
        with patch.object(library, 'files_for_notion', return_value=['part1', 'part2']), \
             patch.object(library.notion_store, 'append_file', side_effect=[None, RuntimeError('network')]) as append:
            with self.assertRaises(RuntimeError):
                library.upload_media('page', ['video'], self.temp.name, on_saved=saved.append)
            self.assertEqual(saved, [1])
        with patch.object(library, 'files_for_notion', return_value=['part1', 'part2']), \
             patch.object(library.notion_store, 'append_file') as append:
            library.upload_media('page', ['video'], self.temp.name, saved=saved[-1], on_saved=saved.append)
            append.assert_called_once_with('page', 'part2')
            self.assertEqual(saved, [1, 2])

    def test_retry_reuses_page_and_does_not_duplicate_content(self):
        entry_id = db.create_entry('wallet', 'url', 'https://x.com/user/status/123', queued=True)
        def fetch(_url, directory):
            paths = []
            for name in ('one.jpg', 'two.jpg'):
                path = os.path.join(directory, name)
                with open(path, 'wb') as f:
                    f.write(b'image')
                paths.append(path)
            return 'post text', paths
        with patch.object(worker.pipeline, 'FILES_DIR', self.temp.name), \
             patch.object(worker.pipeline.library, 'tweet', side_effect=fetch), \
             patch.object(worker.pipeline.library, 'describe', side_effect=[RuntimeError('temporary'), ('title', 'summary', [])]), \
             patch.object(worker.pipeline.notion_store, 'create_entry', return_value={'id': 'page', 'url': 'https://example.com/page'}) as create, \
             patch.object(worker.pipeline.notion_store, 'append_text') as append_text, \
             patch.object(worker.pipeline.notion_store, 'append_file') as append_file, \
             patch.object(worker.pipeline.notion_store, 'update_entry'), patch.object(worker.pipeline.notion_store, 'set_status'), \
             patch.object(worker, 'notify'), patch.object(worker.log, 'exception'):
            worker.process_job(db.claim_job())
            row = db.get_entry(entry_id)
            self.assertEqual((row['job_state'], row['saved_text'], row['saved_media']), ('pending', 1, 2))
            with db._connect() as conn:
                conn.execute('UPDATE entries SET next_attempt = NULL WHERE id = ?', (entry_id,))
            worker.process_job(db.claim_job())
        self.assertEqual(db.get_entry(entry_id)['job_state'], 'done')
        self.assertEqual(create.call_count, 1)
        self.assertEqual(append_text.call_count, 1)
        self.assertEqual(append_file.call_count, 2)


if __name__ == '__main__':
    unittest.main()
