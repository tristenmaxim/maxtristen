import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('GEMINI_API_KEY', 'test')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test')
os.environ.setdefault('NOTION_TOKEN', 'test')
os.environ.setdefault('NOTION_DATABASE_ID', 'test')

import db
import library
import worker


class WebpageTests(unittest.TestCase):
    def test_page_is_saved_without_video_downloader(self):
        with tempfile.TemporaryDirectory() as directory:
            db.DB_PATH = os.path.join(directory, 'test.db')
            db.init_db()
            entry = db.create_entry('wallet', 'url', 'https://example.com/article', queued=True)
            with patch.object(worker.pipeline, 'FILES_DIR', directory), \
                 patch.object(library, 'webpage', return_value='Полный текст статьи'), \
                 patch.object(library, 'describe', return_value=('Статья', 'Описание', ['тег'], '')) as describe, \
                 patch.object(worker.pipeline, '_download_via_downloader_service') as download, \
                 patch.object(worker.pipeline.notion_store, 'create_entry', return_value={'id': 'page', 'url': 'https://example.com/page'}), \
                 patch.object(worker.pipeline.notion_store, 'append_text') as append, \
                 patch.object(worker.pipeline.notion_store, 'update_entry') as update, patch.object(worker, 'notify'):
                worker.process_job(db.claim_job())
            self.assertEqual(db.get_entry(entry)['status'], 'done')
            describe.assert_called_once_with('Полный текст статьи', [])
            append.assert_called_once_with('page', 'Текст страницы', 'Полный текст статьи')
            self.assertEqual(update.call_args.args[1:4], ('Статья', 'Описание', ['тег']))
            download.assert_not_called()

    def test_private_addresses_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'публичной сети'):
            library.webpage('http://127.0.0.1/test')


if __name__ == '__main__':
    unittest.main()
