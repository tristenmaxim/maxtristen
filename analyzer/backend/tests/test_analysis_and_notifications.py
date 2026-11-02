import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

os.environ.setdefault('GEMINI_API_KEY', 'test')
os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'test')
os.environ.setdefault('NOTION_TOKEN', 'test')
os.environ.setdefault('NOTION_DATABASE_ID', 'test')

import gemini
import library
import telegram


class AnalysisAndNotificationTests(unittest.TestCase):
    def test_model_json_array_preserves_all_descriptions_and_tags(self):
        data = [{'title': 'Тема', 'summary': 'Первая часть', 'tags': ['тег'], 'visual_text': 'Первый текст'},
                {'summary': 'Вторая часть', 'tags': ['тег', 'другой'], 'visual_text': 'Второй текст'}]
        with patch.object(gemini, 'generate', return_value=SimpleNamespace(text=json.dumps(data))):
            self.assertEqual(library.describe('материал'), ('Тема', 'Первая часть\n\nВторая часть',
                             ['тег', 'другой'], 'Первый текст\n\nВторой текст'))

    def test_invalid_model_array_fails(self):
        for data in ([], ['text'], None):
            with patch.object(gemini, 'generate', return_value=SimpleNamespace(text=json.dumps(data))):
                with self.assertRaisesRegex(ValueError, 'некорректный результат'):
                    library.describe('материал')

    def test_send_message_checks_success_and_rejects_http_error_without_token(self):
        request = httpx.Request('POST', telegram.API_BASE + '/sendMessage')
        success = httpx.Response(200, json={'ok': True}, request=request)
        with patch.object(telegram.httpx, 'post', return_value=success):
            telegram.send_message(1, 'text')
        for response in (httpx.Response(400, json={'ok': False}, request=request),
                         httpx.Response(200, json={'ok': False}, request=request)):
            with patch.object(telegram.httpx, 'post', return_value=response), self.assertRaises(RuntimeError) as raised:
                telegram.send_message(1, 'text')
            self.assertNotIn(telegram.TELEGRAM_BOT_TOKEN, str(raised.exception))

    def test_send_message_sanitizes_network_errors(self):
        request = httpx.Request('POST', telegram.API_BASE + '/sendMessage')
        with patch.object(telegram.httpx, 'post', side_effect=httpx.ConnectError(str(request.url), request=request)), \
             self.assertRaises(RuntimeError) as raised:
            telegram.send_message(1, 'text')
        self.assertNotIn(telegram.TELEGRAM_BOT_TOKEN, str(raised.exception))


if __name__ == '__main__':
    unittest.main()
