import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault('GEMINI_API_KEY', 'test')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test')
os.environ.setdefault('NOTION_TOKEN', 'test')
os.environ.setdefault('NOTION_DATABASE_ID', 'test')

import db
import gemini
import library
import worker
from google.genai import errors as genai_errors


class MediaTests(unittest.TestCase):
    def test_video_without_speech_is_still_analyzed_and_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            db.DB_PATH = os.path.join(directory, 'test.db')
            db.init_db()
            path = os.path.join(directory, 'video.mp4')
            with open(path, 'wb') as f:
                f.write(b'video')
            entry = db.create_entry('wallet', 'web_upload', file_path=path, queued=True)
            with patch.object(worker.pipeline, 'FILES_DIR', directory), \
                 patch.object(gemini, 'transcribe', return_value=''), \
                 patch.object(library, 'describe', return_value=('title', 'summary', ['tag'], 'visible')) as describe, \
                 patch.object(worker.pipeline.notion_store, 'create_entry', return_value={'id': 'page', 'url': 'https://example.com/page'}), \
                 patch.object(worker.pipeline.notion_store, 'append_text'), \
                 patch.object(worker.pipeline.notion_store, 'append_file'), \
                 patch.object(worker.pipeline.notion_store, 'update_entry'), patch.object(worker, 'notify'):
                worker.process_job(db.claim_job())
            row = db.get_entry(entry)
            self.assertEqual(row['status'], 'done')
            self.assertEqual(row['transcript'], 'Речь не обнаружена.')
            self.assertEqual(describe.call_args.args[1], [path])

    def test_quota_error_uses_fallback_model(self):
        quota = genai_errors.ClientError(429, {'error': {'message': 'quota exhausted'}})
        response = SimpleNamespace(text='ok')
        with patch.object(gemini._client.models, 'generate_content', side_effect=[quota, response]) as generate:
            self.assertIs(gemini.generate(['input'], {}), response)
        self.assertEqual(generate.call_count, 2)

    def test_other_client_error_does_not_use_fallback(self):
        error = genai_errors.ClientError(400, {'error': {'message': 'invalid request'}})
        with patch.object(gemini._client.models, 'generate_content', side_effect=error) as generate:
            with self.assertRaises(genai_errors.ClientError):
                gemini.generate(['input'], {})
        generate.assert_called_once()

    def test_short_tiktok_url_resolves_to_photo_post(self):
        with patch.object(library.httpx, 'head', return_value=SimpleNamespace(url='https://www.tiktok.com/@u/photo/123')):
            self.assertEqual(library.tiktok_photo_url('https://vt.tiktok.com/test'), 'https://www.tiktok.com/@u/photo/123')
        self.assertIsNone(library.tiktok_photo_url('https://www.tiktok.com/@u/video/123'))

    def test_photo_post_downloads_image_and_audio(self):
        records = [[2, {'desc': 'caption'}], [3, 'https://cdn.example/a', {'extension': 'jpeg'}],
                   [3, 'https://cdn.example/b', {'extension': 'mp3'}]]
        response = MagicMock()
        response.__enter__.return_value.iter_bytes.return_value = [b'media']
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(library.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps(records))), \
             patch.object(library.httpx, 'stream', return_value=response):
            text, paths = library.tiktok_photos('https://www.tiktok.com/@u/photo/123', directory)
            self.assertEqual(text, 'caption')
            self.assertEqual([os.path.splitext(p)[1] for p in paths], ['.jpg', '.mp3'])
            self.assertTrue(all(os.path.getsize(p) == 5 for p in paths))

    def test_description_includes_video_and_removes_temporary_upload(self):
        uploaded = SimpleNamespace(name='file-id', state=SimpleNamespace(name='ACTIVE'))
        response = SimpleNamespace(text=json.dumps({'title': 'title', 'summary': 'summary', 'tags': ['tag'], 'visual_text': 'visible'}))
        with patch.object(gemini._client.files, 'upload', return_value=uploaded) as upload, \
             patch.object(gemini._client.files, 'delete') as delete, patch.object(gemini, 'generate', return_value=response) as generate:
            result = library.describe('[Music]', ['/tmp/video.mp4'])
        self.assertEqual(result, ('title', 'summary', ['tag'], 'visible'))
        upload.assert_called_once_with(file='/tmp/video.mp4')
        self.assertIn(uploaded, generate.call_args.kwargs['contents'])
        delete.assert_called_once_with(name='file-id')

    def test_photo_post_passes_images_and_audio_to_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            db.DB_PATH = os.path.join(directory, 'test.db')
            db.init_db()
            entry = db.create_entry('wallet', 'url', 'https://www.tiktok.com/@u/photo/123', queued=True)
            def fetch(_url, tempdir):
                paths = []
                for name in ('slide.jpg', 'sound.mp3'):
                    path = os.path.join(tempdir, name)
                    with open(path, 'wb') as f:
                        f.write(b'media')
                    paths.append(path)
                return 'caption', paths
            with patch.object(worker.pipeline, 'FILES_DIR', directory), \
                 patch.object(library, 'tiktok_photos', side_effect=fetch), \
                 patch.object(gemini, 'transcribe', return_value='[Music]') as transcribe, \
                 patch.object(library, 'describe', return_value=('title', 'summary', ['tag'], 'visible text')) as describe, \
                 patch.object(worker.pipeline.notion_store, 'create_entry', return_value={'id': 'page', 'url': 'https://example.com/page'}), \
                 patch.object(worker.pipeline.notion_store, 'append_text') as append, \
                 patch.object(worker.pipeline.notion_store, 'append_file'), \
                 patch.object(worker.pipeline.notion_store, 'update_entry'), patch.object(worker, 'notify'):
                worker.process_job(db.claim_job())
            self.assertEqual(db.get_entry(entry)['status'], 'done')
            self.assertTrue(transcribe.call_args.args[0].endswith('.mp3'))
            self.assertEqual({os.path.splitext(p)[1] for p in describe.call_args.args[1]}, {'.jpg', '.mp3'})
            self.assertTrue(any(c.args[1] == 'Текст на экране' for c in append.call_args_list))


if __name__ == '__main__':
    unittest.main()
