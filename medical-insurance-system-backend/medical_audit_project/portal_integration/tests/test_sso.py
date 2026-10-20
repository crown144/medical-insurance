import hashlib
from io import BytesIO
import os
from pathlib import Path
import runpy
import time
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch

import requests
from docx import Document
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import AccountProfile
from tasks.models import Task
from portal_integration.models import PortalLoginCode, PortalUserBinding
from portal_integration.services.exceptions import PortalClientError, PortalProtocolError
from portal_integration.services.portal_client import PortalClient
from portal_integration.services.user_sync import PortalUserSyncService
from .test_document_contract import CALLBACK_DETAIL


@override_settings(PORTAL_BASE_URL='https://portal.example.test', PORTAL_APP_ID='test-app')
class TicketClientTests(SimpleTestCase):
    def make_client(self, data=CALLBACK_DETAIL, code=0, status=200):
        response = Mock(status_code=status, headers={})
        response.json.return_value = {'code': code, 'data': data}
        session = Mock()
        session.get.return_value = response
        return PortalClient(session=session), session

    @override_settings(PORTAL_SSO_VALIDATE_PATH='/custom/cas/serviceValidate')
    def test_get_uses_query_parameters_and_configured_gateway(self):
        client, session = self.make_client()
        self.assertEqual(client.validate_ticket('ST-a+b&c', 'test-app'), CALLBACK_DETAIL)
        session.get.assert_called_once_with(
            'https://portal.example.test/custom/cas/serviceValidate',
            params={'ticket': 'ST-a+b&c', 'appid': 'test-app'},
            headers={'Content-Type': 'application/json'}, timeout=10, allow_redirects=False,
        )

    def test_wrong_app_id_never_contacts_portal(self):
        client, session = self.make_client()
        with self.assertRaises(PortalProtocolError): client.validate_ticket('ST-1', 'other-app')
        session.get.assert_not_called()

    def test_invalid_ticket_and_upstream_failures_are_distinct(self):
        for code, status, error in [(1, 200, PortalProtocolError), (0, 401, PortalProtocolError), (0, 302, PortalClientError), (0, 500, PortalClientError)]:
            with self.subTest(code=code, status=status), self.assertRaises(error):
                self.make_client(code=code, status=status)[0].validate_ticket('ST-1', 'test-app')
        client, session = self.make_client()
        session.get.side_effect = requests.Timeout()
        with self.assertRaises(PortalClientError): client.validate_ticket('ST-1', 'test-app')

    def test_malformed_success_never_supplies_an_identity(self):
        for data in [None, [], {**CALLBACK_DETAIL, 'id': ''}, {**CALLBACK_DETAIL, 'username': None}, {**CALLBACK_DETAIL, 'status': True}, {**CALLBACK_DETAIL, 'expired': None}]:
            with self.subTest(data=data), self.assertRaises(PortalClientError):
                self.make_client(data)[0].validate_ticket('ST-1', 'test-app')

    def test_encrypted_cas_data_is_rejected_per_plaintext_contract(self):
        with self.assertRaises(PortalClientError): self.make_client('ciphertext')[0].validate_ticket('ST-1', 'test-app')

    def test_document_example_missing_expiry_uses_verified_detail(self):
        data = {k: v for k, v in CALLBACK_DETAIL.items() if k != 'expired'}
        client, _session = self.make_client(data)
        with patch.object(client, 'get_user_detail', return_value=CALLBACK_DETAIL) as detail:
            self.assertEqual(client.validate_ticket('ST-1', 'test-app'), CALLBACK_DETAIL)
        detail.assert_called_once_with(CALLBACK_DETAIL['id'])


@override_settings(PORTAL_APP_ID='test-app', PORTAL_FRONTEND_URL='https://insurance.example.test/medical')
class SsoFlowTests(APITestCase):
    def login(self, **kwargs):
        return self.client.post('/api/sso/login', {'ticket': 'ST-1', 'appid': 'test-app', **kwargs}, format='json')

    @patch('portal_integration.services.portal_client.PortalClient.validate_ticket', return_value=CALLBACK_DETAIL)
    def test_new_portal_user_can_login_and_call_business_apis_with_local_token(self, validate):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        token = response.data['result']['accessToken']
        self.assertEqual(response['Cache-Control'], 'no-store')
        binding = PortalUserBinding.objects.get()
        self.assertFalse(binding.user.has_usable_password())
        self.assertEqual(binding.user.audit_profile.role, AccountProfile.Role.NORMAL)
        for path in ['/api/user/info', '/api/auth/codes', '/api/tasks/', '/api/rules/', '/api/results/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, HTTP_AUTHORIZATION=f'Bearer {token}').status_code, 200)
                self.assertEqual(self.client.get(path, HTTP_ACCESSTOKEN=token).status_code, 200)
                self.assertEqual(self.client.get(path).status_code, 401)
        validate.assert_called_once_with('ST-1', 'test-app')

    @patch('portal_integration.services.portal_client.PortalClient.validate_ticket', return_value=CALLBACK_DETAIL)
    def test_sso_preserves_existing_admin_and_local_password(self, _validate):
        user = get_user_model().objects.create_user(username=CALLBACK_DETAIL['username'], password='local-password')
        AccountProfile.objects.create(user=user, role=AccountProfile.Role.ADMIN)
        response = self.login()
        user.refresh_from_db()
        self.assertEqual(response.data['result']['roles'], ['admin'])
        self.assertTrue(user.check_password('local-password'))
        self.assertEqual(get_user_model().objects.count(), 1)

    @patch('portal_integration.services.portal_client.PortalClient.validate_ticket', return_value=CALLBACK_DETAIL)
    def test_sso_token_can_download_a_real_word_report(self, _validate):
        token = self.login().data['result']['accessToken']
        task = Task.objects.create(name='SSO报告验证', hospitalization_ids=[], status='completed')
        path = f'/api/tasks/{task.pk}/download-report/'
        self.assertEqual(self.client.get(path).status_code, 401)
        response = self.client.get(path, {'issue_number': '3'}, HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('wordprocessingml', response['Content-Type'])
        self.assertIn('filename*=', response['Content-Disposition'])
        report = Document(BytesIO(response.content))
        self.assertTrue(any('第3期' in p.text for p in report.paragraphs))

    @patch('portal_integration.services.portal_client.PortalClient.validate_ticket')
    def test_disabled_removed_expired_and_globally_disabled_users_cannot_login(self, validate):
        binding = PortalUserSyncService().sync_detail(CALLBACK_DETAIL)
        for access in ['DISABLED', 'REMOVED']:
            binding.access_status = access; binding.save()
            validate.return_value = CALLBACK_DETAIL
            self.assertEqual(self.login().status_code, 403)
        binding.access_status = 'ENABLED'; binding.save()
        for detail in [{**CALLBACK_DETAIL, 'status': 2}, {**CALLBACK_DETAIL, 'expired': int(time.time()) - 5}]:
            validate.return_value = detail
            self.assertEqual(self.login().status_code, 403)

    @patch('portal_integration.services.portal_client.PortalClient.validate_ticket', side_effect=PortalProtocolError('无效凭据'))
    def test_rejected_ticket_cannot_create_a_local_user(self, _validate):
        self.assertEqual(self.login().status_code, 401)
        self.assertFalse(get_user_model().objects.exists())

    @patch('portal_integration.services.portal_client.PortalClient.validate_ticket', return_value=CALLBACK_DETAIL)
    def test_http_callback_handoff_is_single_use_and_keeps_requested_page(self, validate):
        callback = 'https://insurance.example.test/medical/#/task/execution?search=a%26b'
        response = self.client.get('/api/portal/sso/callback', {'ticket': 'ST-1', 'appid': 'test-app', 'callback': callback})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('https://insurance.example.test/medical/#/oauth/login?'))
        params = parse_qs(urlsplit(response.url).fragment.split('?', 1)[1])
        self.assertEqual(params['callback'], [callback])
        code = params['code'][0]
        self.assertNotIn('accessToken', response.url)
        handoff = PortalLoginCode.objects.get()
        self.assertEqual(handoff.code_hash, hashlib.sha256(code.encode()).hexdigest())
        login = self.client.post('/api/sso/login', {'code': code}, format='json')
        self.assertEqual(login.status_code, 200)
        self.assertFalse(PortalLoginCode.objects.exists())
        self.assertEqual(self.client.post('/api/sso/login', {'code': code}, format='json').status_code, 401)
        validate.assert_called_once()

    @patch('portal_integration.services.portal_client.PortalClient.validate_ticket', return_value=CALLBACK_DETAIL)
    def test_legacy_get_login_uses_same_binding_and_single_use_exchange(self, validate):
        response = self.client.get('/api/sso/login', {
            'ticket': 'ST-legacy', 'appid': 'test-app', 'callback': '/task/execution',
        })
        self.assertEqual(response.status_code, 302)
        params = parse_qs(urlsplit(response.url).fragment.split('?', 1)[1])
        self.assertEqual(params['callback'], ['/task/execution'])
        self.assertEqual(PortalUserBinding.objects.get().portal_user_id, CALLBACK_DETAIL['id'])
        code = params['code'][0]
        self.assertEqual(self.client.post('/api/sso/login', {'code': code}, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/sso/login', {'code': code}, format='json').status_code, 401)
        validate.assert_called_once_with('ST-legacy', 'test-app')

    @patch('portal_integration.services.portal_client.PortalClient.validate_ticket')
    def test_legacy_get_login_cannot_restore_removed_or_expired_access(self, validate):
        binding = PortalUserSyncService().sync_detail(CALLBACK_DETAIL)
        for access, detail in [
            ('DISABLED', CALLBACK_DETAIL),
            ('REMOVED', CALLBACK_DETAIL),
            ('ENABLED', {**CALLBACK_DETAIL, 'expired': int(time.time()) - 5}),
            ('ENABLED', {**CALLBACK_DETAIL, 'status': 2}),
        ]:
            with self.subTest(access=access, detail=detail):
                binding.access_status = access
                binding.save(update_fields=['access_status'])
                validate.return_value = detail
                response = self.client.get('/api/sso/login', {'ticket': 'ST-1', 'appid': 'test-app'})
                self.assertEqual(response.status_code, 403)
                self.assertFalse(PortalLoginCode.objects.exists())

    @patch('portal_integration.services.portal_client.PortalClient.validate_ticket')
    def test_bad_callback_is_rejected_before_ticket_exchange(self, validate):
        for endpoint in ['/api/portal/sso/callback', '/api/sso/login']:
            for callback in ['https://other.example.test/#/task', '//other.example.test', 'javascript:alert(1)']:
                response = self.client.get(endpoint, {'ticket': 'ST-1', 'appid': 'test-app', 'callback': callback})
                self.assertEqual(response.status_code, 401)
        validate.assert_not_called()

    def test_expired_handoff_and_missing_parameters_are_rejected(self):
        user = get_user_model().objects.create_user(username='expired-code')
        AccountProfile.objects.create(user=user)
        PortalLoginCode.objects.create(code_hash=hashlib.sha256(b'expired').hexdigest(), user=user, expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post('/api/sso/login', {'code': 'expired'}, format='json').status_code, 401)
        for data in [{}, {'ticket': 'ST-1'}, {'code': 'x', 'ticket': 'ST-1', 'appid': 'test-app'}]:
            self.assertEqual(self.client.post('/api/sso/login', data, format='json').status_code, 400)


@override_settings(PORTAL_FRONTEND_URL='https://insurance.example.test', PORTAL_CAS_LOGIN_URL='https://portal.example.test/cas/login?lang=zh', PORTAL_LOGIN_CALLBACK_URL='https://insurance.example.test/api/portal/sso/callback')
class SsoEntryTests(APITestCase):
    def test_app_entry_redirects_to_cas_with_exact_service_and_requested_page(self):
        response = self.client.get('/api/portal/sso/start', {'callback': '/task/manage/execution?search=a%26b'})
        self.assertEqual(response.status_code, 302)
        params = parse_qs(urlsplit(response.url).query)
        self.assertEqual(params['service'], ['https://insurance.example.test/api/portal/sso/callback'])
        self.assertEqual(params['callback'], ['https://insurance.example.test/#/task/manage/execution?search=a%26b'])
        self.assertEqual(params['lang'], ['zh'])

    @override_settings(PORTAL_CAS_LOGIN_URL='')
    def test_unconfigured_portal_keeps_local_login(self):
        response = self.client.get('/api/portal/sso/config')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['result']['enabled'])

    def test_config_supports_frontend_entry_and_rejects_external_callback(self):
        response = self.client.get('/api/portal/sso/config', {'callback': '/task/execution'})
        self.assertTrue(response.data['result']['enabled'])
        self.assertTrue(response.data['result']['authorizeUrl'].startswith('https://portal.example.test/cas/login?'))
        self.assertEqual(self.client.get('/api/portal/sso/config', {'callback': 'https://other.example.test/'}).status_code, 401)

    @override_settings(PORTAL_LOGIN_CALLBACK_URL='')
    def test_incomplete_deployment_reports_configuration_failure(self):
        self.assertEqual(self.client.get('/api/portal/sso/start').status_code, 503)


@override_settings(
    PORTAL_APP_ID='test-app', PORTAL_FRONTEND_URL='https://insurance.example.test/medical',
    PORTAL_CAS_LOGIN_URL='', SSO_CAS_LOGOUT_URL='https://portal.example.test/cas/logout?lang=zh&service=old',
    PORTAL_LOGIN_CALLBACK_URL='https://insurance.example.test/api/sso/login',
    SSO_LOGOUT_CALLBACK_URL='https://insurance.example.test/api/sso/logout',
    SSO_LOGOUT_SERVICE_URL='',
    SSO_PORTAL_HOME_URL='https://portal.example.test/home/%E6%97%A0#/home-page',
)
class SsoLogoutTests(APITestCase):
    callback = 'https://portal.example.test/home/%E6%97%A0#/home-page'

    def test_config_preserves_registered_login_service_for_logout(self):
        response = self.client.get('/api/portal/sso/config')
        self.assertEqual(response.status_code, 200)
        config = response.data['result']
        self.assertFalse(config['enabled'])
        self.assertEqual(config['portalHomeUrl'], self.callback)
        query = parse_qs(urlsplit(config['logoutUrl']).query)
        self.assertEqual(query['service'], ['https://insurance.example.test/api/sso/login'])
        self.assertEqual(query['callback'], [self.callback])
        self.assertEqual(query['lang'], ['zh'])

    @override_settings(SSO_LOGOUT_SERVICE_URL='https://insurance.example.test/api/sso/logout')
    def test_logout_service_can_be_overridden_for_other_portal_deployments(self):
        config = self.client.get('/api/portal/sso/config').data['result']
        query = parse_qs(urlsplit(config['logoutUrl']).query)
        self.assertEqual(query['service'], ['https://insurance.example.test/api/sso/logout'])

    @override_settings(PORTAL_LOGIN_CALLBACK_URL='https://insurance.example.test/#/oauth/login')
    def test_logout_preserves_frontend_login_callback_fragment(self):
        config = self.client.get('/api/portal/sso/config').data['result']
        query = parse_qs(urlsplit(config['logoutUrl']).query)
        self.assertEqual(query['service'], ['https://insurance.example.test/#/oauth/login'])

    def test_logout_callback_without_token_redirects_browser_to_clear_session(self):
        response = self.client.get('/api/sso/logout', {
            'status': 'server_logout', 'appid': 'test-app', 'callback': self.callback,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('https://insurance.example.test/medical/#/auth/sso-logout?'))
        self.assertEqual(parse_qs(urlsplit(response.url).fragment.split('?', 1)[1])['callback'], [self.callback])
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_logout_rejects_wrong_app_status_and_external_callback(self):
        valid = {'status': 'server_logout', 'appid': 'test-app', 'callback': self.callback}
        for invalid in [
            {'appid': 'other'}, {'status': 'login'}, {'callback': ''},
            {'callback': 'https://attacker.example.test'},
            {'callback': 'https://portal.example.test/another-page'},
        ]:
            with self.subTest(invalid=invalid):
                response = self.client.get('/api/sso/logout', {**valid, **invalid})
                self.assertEqual(response.status_code, 401)
                self.assertNotIn('Location', response)

    @override_settings(SSO_LOGOUT_CALLBACK_URL='')
    def test_incomplete_logout_keeps_local_fallback(self):
        config = self.client.get('/api/portal/sso/config').data['result']
        self.assertEqual(config['logoutUrl'], '')
        self.assertEqual(config['portalHomeUrl'], '')

    def test_legacy_exchange_is_explicitly_deprecated_without_authentication(self):
        self.assertEqual(self.client.get('/api/sso/exchange').status_code, 410)


class SsoSettingsCompatibilityTests(SimpleTestCase):
    def load_settings(self, env):
        settings_path = Path(__file__).parents[2] / 'medical_audit_project' / 'settings.py'
        with patch.dict(os.environ, env, clear=True):
            return runpy.run_path(str(settings_path))

    def test_legacy_environment_configures_canonical_portal_client(self):
        config = self.load_settings({
            'SSO_APP_ID': 'legacy-app', 'SSO_APP_BASE_URL': 'https://insurance.example.test/medical',
            'SSO_SERVICE_VALIDATE_URL': 'https://portal.example.test/custom/cas/serviceValidate',
            'SSO_LOGIN_CALLBACK_URL': 'https://insurance.example.test/api/sso/login',
            'SSO_HTTP_TIMEOUT_SECONDS': '6',
        })
        self.assertEqual(config['PORTAL_APP_ID'], 'legacy-app')
        self.assertEqual(config['PORTAL_FRONTEND_URL'], 'https://insurance.example.test/medical')
        self.assertEqual(config['PORTAL_BASE_URL'], 'https://portal.example.test')
        self.assertEqual(config['PORTAL_SSO_VALIDATE_PATH'], '/custom/cas/serviceValidate')
        self.assertEqual(config['PORTAL_LOGIN_CALLBACK_URL'], 'https://insurance.example.test/api/sso/login')
        self.assertEqual(config['PORTAL_REQUEST_TIMEOUT_SECONDS'], 6)

    def test_credentials_require_environment_values_and_have_no_shared_defaults(self):
        config = self.load_settings({})
        self.assertEqual(config['SECRET_KEY'], '')
        self.assertEqual(config['DATABASES']['default']['PASSWORD'], '')
        self.assertEqual(config['RULE_IMPORT_LLM_API_KEY'], '')
        env = {
            'DJANGO_SECRET_KEY': 'isolated-signing-test-value',
            'DB_PASSWORD': 'isolated-database-test-value',
            'RULE_IMPORT_LLM_API_KEY': 'isolated-llm-test-value',
        }
        config = self.load_settings(env)
        self.assertEqual(config['SECRET_KEY'], env['DJANGO_SECRET_KEY'])
        self.assertEqual(config['DATABASES']['default']['PASSWORD'], env['DB_PASSWORD'])
        self.assertEqual(config['RULE_IMPORT_LLM_API_KEY'], env['RULE_IMPORT_LLM_API_KEY'])

    def test_explicit_portal_values_take_precedence_and_local_defaults_are_empty(self):
        config = self.load_settings({'PORTAL_APP_ID': 'current-app', 'SSO_APP_ID': 'legacy-app'})
        self.assertEqual(config['PORTAL_APP_ID'], 'current-app')
        config = self.load_settings({})
        for key in ['PORTAL_APP_ID', 'PORTAL_BASE_URL', 'PORTAL_FRONTEND_URL', 'SSO_CAS_LOGOUT_URL', 'SSO_PORTAL_HOME_URL']:
            with self.subTest(key=key):
                self.assertEqual(config[key], '')

    def test_allowed_hosts_can_be_configured_for_the_deployment(self):
        config = self.load_settings({'DJANGO_ALLOWED_HOSTS': ' 10.130.76.47, insurance.example.test, , localhost '})
        self.assertEqual(config['ALLOWED_HOSTS'], ['10.130.76.47', 'insurance.example.test', 'localhost'])
