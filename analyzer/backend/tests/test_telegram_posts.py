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
import library
import worker


class TelegramPostTests(unittest.TestCase):
    def response(self, content):
        return SimpleNamespace(content=content.encode(), raise_for_status=lambda: None)

    def test_extracts_post_text_and_images(self):
        html = '''<div data-post="publicchannel/42"><div class="tgme_widget_message_text">Текст<br/>статьи</div>
            <a class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn1.telesco.pe/file/image')"></a></div>'''
        media = MagicMock()
        media.__enter__.return_value.iter_bytes.return_value = [b'image']
        with tempfile.TemporaryDirectory() as directory, patch.object(library.httpx, 'get', return_value=self.response(html)), \
             patch.object(library.httpx, 'stream', return_value=media):
            text, paths = library.telegram_post('https://t.me/publicchannel/42', directory)
            self.assertEqual(text, 'Текст\nстатьи')
            self.assertEqual(len(paths), 1)
            with open(paths[0], 'rb') as image:
                self.assertEqual(image.read(), b'image')

    def test_unavailable_or_unsupported_posts_fail(self):
        for html in ('<div class="tgme_widget_message_error">Not found</div>',
                     '<div data-post="publicchannel/42"><div class="tgme_widget_message_text">text</div><div class="tgme_widget_message_document_wrap"></div></div>',
                     '<div data-post="publicchannel/42"><div class="tgme_widget_message_text">text</div><div class="tgme_widget_message_video_wrap"></div></div>'):
            with tempfile.TemporaryDirectory() as directory, patch.object(library.httpx, 'get', return_value=self.response(html)):
                with self.assertRaises(ValueError):
                    library.telegram_post('https://t.me/publicchannel/42', directory)
        self.assertEqual(library.source_for('https://t.me/publicchannel/42'), 'Telegram')
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            library.telegram_post('https://t.me/c/123/456', directory)

    def test_pipeline_saves_telegram_post(self):
        with tempfile.TemporaryDirectory() as directory:
            db.DB_PATH = os.path.join(directory, 'db')
            db.init_db()
            entry = db.create_entry('wallet', 'url', 'https://t.me/publicchannel/42', queued=True)
            with patch.object(worker.pipeline, 'FILES_DIR', directory), \
                 patch.object(library, 'telegram_post', return_value=('post text', [])), \
                 patch.object(library, 'describe', return_value=('title', 'summary', ['tag'], '')), \
                 patch.object(worker.pipeline.notion_store, 'create_entry', return_value={'id': 'page', 'url': 'https://example.com'}), \
                 patch.object(worker.pipeline.notion_store, 'append_text') as append, \
                 patch.object(worker.pipeline.notion_store, 'update_entry') as update, patch.object(worker, 'notify'):
                worker.process_job(db.claim_job())
            self.assertEqual(db.get_entry(entry)['status'], 'done')
            append.assert_called_once_with('page', 'Текст публикации', 'post text')
            self.assertEqual(update.call_args.args[-1], 'Telegram')


if __name__ == '__main__':
    unittest.main()
