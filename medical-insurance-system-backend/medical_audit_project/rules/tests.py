from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient


class AgentAViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @mock.patch('rules.views.AgentAService.build')
    def test_generate_returns_json_timeout_error(self, mock_build):
        mock_build.side_effect = TimeoutError('request timed out')

        response = self.client.post(
            '/api/rules/agenta/generate/',
            {'rule_text': '规则名称：测试\n规则描述：测试规则'},
            format='json',
        )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.data['code'], 1)
        self.assertIn('超时', response.data['message'])
        self.assertEqual(response.data['result']['error_type'], 'TimeoutError')

    @mock.patch('rules.views.AgentAService.build')
    def test_generate_returns_json_model_error(self, mock_build):
        mock_build.side_effect = RuntimeError('model unavailable')

        response = self.client.post(
            '/api/rules/agenta/generate/',
            {'rule_text': '规则名称：测试\n规则描述：测试规则'},
            format='json',
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data['code'], 1)
        self.assertEqual(response.data['message'], '规则编译模型调用失败')
        self.assertEqual(response.data['result']['error_type'], 'RuntimeError')
