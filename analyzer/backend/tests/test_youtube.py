import json
import os
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('GEMINI_API_KEY', 'test')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test')
os.environ.setdefault('NOTION_TOKEN', 'test')
os.environ.setdefault('NOTION_DATABASE_ID', 'test')

import db
import gemini
import library
import worker

URL = 'https://www.youtube.com/watch?v=jNQXAC9IVRw'


class YouTubeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db.DB_PATH = os.path.join(self.temp.name, 'test.db')
        db.init_db()

    def tearDown(self):
        self.temp.cleanup()

    def test_youtube_url_canonicalization(self):
        for url in ('https://youtu.be/jNQXAC9IVRw?t=2', URL + '&list=example',
                    'https://m.youtube.com/shorts/jNQXAC9IVRw'):
            self.assertEqual(library.youtube_url(url), URL)
            self.assertEqual(library.source_for(url), 'YouTube')
        self.assertIsNone(library.youtube_url('https://youtube.com.example.org/watch?v=jNQXAC9IVRw'))
        self.assertIsNone(library.youtube_url('https://www.youtube.com/watch?v=invalid'))

    def test_metadata_combines_selected_tracks_and_handles_unknown(self):
        info = {'title': 'Test', 'duration': 120, 'requested_formats': [
            {'filesize': 4_000_000}, {'filesize_approx': 2_000_000}]}
        with patch.object(library.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps(info))):
            self.assertEqual(library.youtube_metadata(URL), {'size': 6_000_000, 'duration': 120.0, 'title': 'Test'})
        with patch.object(library.subprocess, 'run', side_effect=subprocess.TimeoutExpired('yt-dlp', 90)):
            self.assertEqual(library.youtube_metadata(URL), {'size': None, 'duration': None, 'title': None})

    def test_transcription_resumes_after_partial_failure(self):
        cached = {}
        def response(text):
            return SimpleNamespace(text=text, candidates=[SimpleNamespace(finish_reason='STOP')], prompt_feedback=None)
        with patch.object(gemini, 'generate', side_effect=[response('first'), RuntimeError('network')]):
            with self.assertRaises(RuntimeError):
                gemini.transcribe_youtube(URL, 1201, cached, lambda start, text: cached.update({start: text}))
        self.assertEqual(cached, {0: 'first'})
        with patch.object(gemini, 'generate', side_effect=[response('second'), response('third')]) as generate:
            result = gemini.transcribe_youtube(URL, 1201, cached, lambda start, text: cached.update({start: text}))
        self.assertEqual(generate.call_count, 2)
        self.assertIn('first', result)
        self.assertIn('second', result)
        self.assertIn('third', result)
        self.assertEqual(set(cached), {0, 600, 1200})
        self.assertEqual(generate.call_args_list[0].kwargs['contents'][0].video_metadata.start_offset, '600s')

    def test_truncated_response_is_not_saved(self):
        response = SimpleNamespace(text='incomplete', candidates=[SimpleNamespace(finish_reason='MAX_TOKENS')], prompt_feedback=None)
        saved = []
        with patch.object(gemini, 'generate', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'полный фрагмент'):
                gemini.transcribe_youtube(URL, 60, on_part=lambda start, text: saved.append(text))
        self.assertEqual(saved, [])

    def test_blocked_response_is_not_saved(self):
        response = SimpleNamespace(text=None, candidates=[], prompt_feedback=SimpleNamespace(block_reason='SAFETY'))
        saved = []
        with patch.object(gemini, 'generate', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'отклонил'):
                gemini.transcribe_youtube(URL, 60, on_part=lambda start, text: saved.append(text))
        self.assertEqual(saved, [])

    def test_large_and_unknown_video_do_not_download(self):
        for size in (5_000_001, None):
            entry = db.create_entry('wallet', 'url', URL, queued=True)
            metadata = {'size': size, 'duration': 19, 'title': 'Test video'}
            with patch.object(worker.pipeline.library, 'youtube_metadata', return_value=metadata), \
                 patch.object(worker.pipeline.gemini, 'transcribe_youtube', return_value='transcript') as transcribe, \
                 patch.object(worker.pipeline, '_download_via_downloader_service') as download, \
                 patch.object(worker.pipeline.library, 'upload_media') as upload, \
                 patch.object(worker.pipeline.notion_store, 'create_entry', return_value={'id': 'page', 'url': 'https://example.com/page'}), \
                 patch.object(worker.pipeline.notion_store, 'append_text'), \
                 patch.object(worker.pipeline.notion_store, 'update_entry') as update, \
                 patch.object(worker, 'notify'):
                worker.process_job(db.claim_job())
            self.assertEqual(db.get_entry(entry)['status'], 'done')
            self.assertEqual(db.get_entry(entry)['youtube_mode'], 'direct')
            transcribe.assert_called_once()
            download.assert_not_called()
            upload.assert_not_called()
            self.assertEqual(update.call_args.args[-1], 'YouTube')

    def test_small_video_keeps_existing_download_path(self):
        entry = db.create_entry('wallet', 'url', URL, queued=True)
        path = os.path.join(self.temp.name, 'small.mp4')
        with open(path, 'wb') as f:
            f.write(b'video')
        with patch.object(worker.pipeline.library, 'youtube_metadata', return_value={'size': 5_000_000, 'duration': 19, 'title': 'Test'}), \
             patch.object(worker.pipeline, '_download_via_downloader_service', return_value=path) as download, \
             patch.object(worker.pipeline.gemini, 'transcribe', return_value='transcript'), \
             patch.object(worker.pipeline.library, 'describe', return_value=('title', 'summary', [], '')), \
             patch.object(worker.pipeline.library, 'upload_media') as upload, \
             patch.object(worker.pipeline.notion_store, 'create_entry', return_value={'id': 'page', 'url': 'https://example.com/page'}), \
             patch.object(worker.pipeline.notion_store, 'append_text'), \
             patch.object(worker.pipeline.notion_store, 'update_entry'), patch.object(worker, 'notify'):
            worker.process_job(db.claim_job())
        self.assertEqual(db.get_entry(entry)['youtube_mode'], 'download')
        self.assertEqual(db.get_entry(entry)['status'], 'done')
        download.assert_called_once()
        upload.assert_called_once()


if __name__ == '__main__':
    unittest.main()
