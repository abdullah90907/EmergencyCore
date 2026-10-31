import unittest
from unittest.mock import Mock, patch
import requests
from backend.emergencycore.services.analysis import complete, ProviderError


class ProviderFallbackTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(AI_PROVIDER='groq', GROQ_API_KEY='primary-secret', GEMINI_API_KEY='backup-secret',
            GROQ_MODEL='qwen/qwen3.8-27b', GROQ_VISION_MODEL='qwen/qwen3.8-27b',
            GEMINI_MODEL='gemini-3.8-flash', GEMINI_VISION_MODEL='gemini-3.8-flash', AI_FALLBACK_ENABLED='true')
        self.messages = [{'role': 'user', 'content': 'Summarize this report.'}]

    def answer(self, content='Advisory', reason='stop'):
        return Mock(json=lambda: {'choices': [{'message': {'content': content}, 'finish_reason': reason}]})

    @patch('backend.emergencycore.services.analysis.requests.post')
    def test_primary_success_does_not_call_backup(self, post):
        post.return_value = self.answer()
        result = complete(self.config, self.messages, metadata=True)
        self.assertEqual(result['provider'], 'groq')
        self.assertFalse(result['fallback_used'])
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer primary-secret')

    @patch('backend.emergencycore.services.analysis.requests.post')
    def test_timeout_falls_back_with_separate_key(self, post):
        post.side_effect = [requests.Timeout(), self.answer()]
        result = complete(self.config, self.messages, metadata=True)
        self.assertEqual(result['provider'], 'gemini')
        self.assertTrue(result['fallback_used'])
        self.assertEqual(result['attempted_providers'], ['groq', 'gemini'])
        call = post.call_args
        self.assertIn('generativelanguage.googleapis.com', call.args[0])
        self.assertEqual(call.kwargs['headers']['Authorization'], 'Bearer backup-secret')

    @patch('backend.emergencycore.services.analysis.requests.post')
    def test_image_messages_forwarded_to_backup(self, post):
        post.side_effect = [requests.ConnectionError(), self.answer()]
        messages = [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,abc'}}]}]
        result = complete(self.config, messages, vision=True, metadata=True)
        self.assertEqual(result['model'], 'gemini-3.8-flash')
        self.assertEqual(post.call_args.kwargs['json']['messages'], messages)

    @patch('backend.emergencycore.services.analysis.requests.post')
    def test_empty_or_truncated_answer_uses_backup(self, post):
        for first in [self.answer(''), self.answer('Partial', 'length')]:
            post.side_effect = [first, self.answer('Complete')]
            self.assertEqual(complete(self.config, self.messages, metadata=True)['provider'], 'gemini')

    @patch('backend.emergencycore.services.analysis.requests.post')
    def test_missing_primary_key_and_both_failed(self, post):
        self.config['GROQ_API_KEY'] = ''
        post.return_value = self.answer()
        self.assertEqual(complete(self.config, self.messages, metadata=True)['provider'], 'gemini')
        post.side_effect = requests.Timeout()
        with self.assertRaises(ProviderError):
            complete(self.config, self.messages)
        self.config['GEMINI_API_KEY'] = ''
        post.reset_mock()
        with self.assertRaises(ProviderError):
            complete(self.config, self.messages)
        post.assert_not_called()

    @patch('backend.emergencycore.services.analysis.requests.post')
    def test_disabled_fallback_and_provider_refusal(self, post):
        self.config['AI_FALLBACK_ENABLED'] = 'false'
        post.side_effect = requests.Timeout()
        with self.assertRaises(ProviderError):
            complete(self.config, self.messages)
        self.assertEqual(post.call_count, 1)
        post.reset_mock(); post.side_effect = None
        self.config['AI_FALLBACK_ENABLED'] = 'true'
        post.return_value = self.answer('', 'content_filter')
        with self.assertRaises(ProviderError):
            complete(self.config, self.messages)
        self.assertEqual(post.call_count, 1)
