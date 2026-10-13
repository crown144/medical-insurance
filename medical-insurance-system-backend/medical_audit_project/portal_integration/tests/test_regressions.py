import base64
import json
import time
from importlib import import_module
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.apps import apps
from django.db import transaction
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APITestCase

from accounts.auth import build_access_token
from accounts.models import AccountProfile
from portal_integration.models import PortalActionLog, PortalUserBinding
from portal_integration.services.exceptions import PortalClientError, PortalProtocolError
from portal_integration.services.portal_client import PortalClient
from portal_integration.services.user_sync import _normalise_expired_at

from .test_actions import DETAIL


class ExpirationParsingTests(SimpleTestCase):
    def test_seconds_milliseconds_and_never_expiring_are_preserved(self):
        for value in (1_800_000_000, 1_800_000_000_000, -1, '1800000000', '1800000000000', '-1'):
            with self.subTest(value=value):
                self.assertEqual(_normalise_expired_at(value), int(value))

    def test_missing_expiration_is_allowed(self):
        for value in (None, ''):
            self.assertIsNone(_normalise_expired_at(value))

    def test_invalid_expiration_is_rejected(self):
        for value in ('tomorrow', True, 1.5, -2, 2 ** 63, [], {}):
            with self.subTest(value=value):
                with self.assertRaises(PortalClientError):
                    _normalise_expired_at(value)


class HistoricalExpirationTests(TestCase):
    def create_binding(self, name, detail, expires=None):
        user = get_user_model().objects.create_user(username=name)
        return PortalUserBinding.objects.create(portal_user_id=name, user=user, profile_data=detail, portal_expired_at=expires)

    def test_migration_restores_historical_expiration_without_overwriting_current_values(self):
        repair = import_module('portal_integration.migrations.0002_restore_expiration').restore_expiration
        past = int(time.time()) - 60
        missing = self.create_binding('old', {'expire_time': str(past)})
        never = self.create_binding('never', {'expired_at': -1})
        existing = self.create_binding('existing', {'expired_at': past}, expires=-1)
        empty = self.create_binding('empty', {})
        repair(apps, None)
        for binding in (missing, never, existing, empty):
            binding.refresh_from_db()
        self.assertEqual(missing.portal_expired_at, past)
        self.assertEqual(never.portal_expired_at, -1)
        self.assertEqual(existing.portal_expired_at, -1)
        self.assertIsNone(empty.portal_expired_at)

    def test_bad_historical_expiration_stops_repair_and_rolls_back(self):
        repair = import_module('portal_integration.migrations.0002_restore_expiration').restore_expiration
        valid = self.create_binding('valid', {'expired_at': 1800000000})
        self.create_binding('invalid', {'expired_at': 'tomorrow'})
        with self.assertRaises(RuntimeError), transaction.atomic():
            repair(apps, None)
        valid.refresh_from_db()
        self.assertIsNone(valid.portal_expired_at)


@override_settings(PORTAL_ENCRYPT_ENABLED=False, PORTAL_ALLOW_PLAINTEXT=True, DEBUG=True)
class PortalRegressionTests(APITestCase):
    def post_action(self, action, user_id='portal-user-1'):
        return self.client.post(f'/api/portal/actions/{action}', {'user_id': user_id}, format='json')

    def assert_success(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 0)

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail')
    def test_expiration_from_portal_blocks_access(self, get_detail):
        expires = int((time.time() - 60) * 1000)
        get_detail.return_value = {**DETAIL, 'expired_at': str(expires)}
        self.assert_success(self.post_action('default-role'))
        binding = PortalUserBinding.objects.get()
        self.assertEqual(binding.portal_expired_at, expires)
        response = self.client.get('/api/user/info', HTTP_AUTHORIZATION=f'Bearer {build_access_token(binding.user)}')
        self.assertEqual(response.status_code, 401)

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail', return_value=DETAIL)
    def test_enable_does_not_revoke_admin_and_retries_keep_state(self, _get_detail):
        self.assert_success(self.post_action('app-admin-set'))
        for _ in range(3):
            self.assert_success(self.post_action('enable-user'))
            binding = PortalUserBinding.objects.select_related('user').get()
            self.assertTrue(binding.is_admin)
            self.assertEqual(binding.user.audit_profile.role, AccountProfile.Role.ADMIN)

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail', return_value=DETAIL)
    def test_admin_regrant_after_disable_does_not_restore_stale_role(self, _get_detail):
        self.assert_success(self.post_action('default-role'))
        self.assert_success(self.post_action('disable-user'))
        self.assert_success(self.post_action('app-admin-set'))
        self.assert_success(self.post_action('enable-user'))
        binding = PortalUserBinding.objects.select_related('user').get()
        self.assertTrue(binding.is_admin)
        self.assertEqual(binding.user.audit_profile.role, AccountProfile.Role.ADMIN)

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail', return_value=DETAIL)
    def test_audit_failure_rolls_back_first_user_creation(self, _get_detail):
        with patch('portal_integration.services.actions._audit', side_effect=RuntimeError('audit failure')):
            with self.assertLogs('portal_integration.views', level='ERROR'):
                response = self.post_action('app-admin-set')
        self.assertEqual(response.status_code, 500)
        self.assertFalse(PortalUserBinding.objects.exists())
        self.assertFalse(get_user_model().objects.filter(username=DETAIL['username']).exists())
        self.assertEqual(PortalActionLog.objects.get().result_code, 50002)

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail')
    def test_bad_portal_detail_leaves_no_partial_user(self, get_detail):
        for detail in ({**DETAIL, 'username': 'x' * 151}, {**DETAIL, 'expired_at': 'tomorrow'}):
            with self.subTest(detail=detail):
                get_detail.return_value = detail
                response = self.post_action('default-role')
                self.assertEqual(response.data['code'], 50001)
                self.assertFalse(PortalUserBinding.objects.exists())
                self.assertFalse(get_user_model().objects.exists())

    def test_malformed_json_uses_portal_error_envelope(self):
        response = self.client.post('/api/portal/actions/disable-user', '{broken', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 40001)

    @override_settings(PORTAL_ALLOW_PLAINTEXT=False)
    def test_plaintext_without_explicit_opt_in_cannot_change_roles(self):
        user = get_user_model().objects.create_user(username='existing')
        AccountProfile.objects.create(user=user)
        PortalUserBinding.objects.create(portal_user_id='existing-id', user=user)
        response = self.post_action('app-admin-set', 'existing-id')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['code'], 50001)
        self.assertEqual(AccountProfile.objects.get(user=user).role, AccountProfile.Role.NORMAL)

    @override_settings(DEBUG=False, SECRET_KEY='test-only-portal-key')
    def test_plaintext_is_rejected_outside_debug_even_with_opt_in(self):
        response = self.post_action('disable-user')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['code'], 50001)

    def test_expired_user_cannot_receive_successful_login(self):
        user = get_user_model().objects.create_user(username='expired', password='test-password')
        AccountProfile.objects.create(user=user)
        PortalUserBinding.objects.create(portal_user_id='expired-id', user=user, portal_expired_at=int(time.time()) - 60)
        response = self.client.post('/api/auth/login', {'username': 'expired', 'password': 'test-password'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('result', response.data)

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail', return_value=DETAIL)
    def test_response_encoding_failure_rolls_back_user_and_success_log(self, _get_detail):
        error = PortalProtocolError('response signing failed', http_status=500)
        with patch('portal_integration.views.PortalProtocol.encode_response', side_effect=[
            error, ({'code': 40101, 'message': str(error), 'data': None}, {}),
        ]):
            response = self.post_action('app-admin-set')
        self.assertEqual(response.status_code, 500)
        self.assertFalse(PortalUserBinding.objects.exists())
        self.assertFalse(get_user_model().objects.exists())
        self.assertEqual(list(PortalActionLog.objects.values_list('result_code', flat=True)), [40101])

    def test_invalid_ids_are_rejected_for_every_write_action(self):
        for action in ('app-admin-set', 'disable-user', 'enable-user', 'remove-user', 'default-role'):
            for user_id in ('', ' ', None, {}, []):
                with self.subTest(action=action, user_id=user_id):
                    response = self.post_action(action, user_id)
                    self.assertEqual(response.data['code'], 40001)
        self.assertFalse(PortalUserBinding.objects.exists())

    def test_query_rejects_more_than_500_users(self):
        response = self.client.post('/api/portal/actions/query-user-status', {'user_ids': ['id'] * 501}, format='json')
        self.assertEqual(response.data['code'], 40001)

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail', return_value=DETAIL)
    def test_repeated_disable_remove_and_enable_preserve_role_and_local_user(self, _get_detail):
        self.assert_success(self.post_action('app-admin-set'))
        for action, expected_status in (
            ('disable-user', PortalUserBinding.AccessStatus.DISABLED),
            ('enable-user', PortalUserBinding.AccessStatus.ENABLED),
            ('remove-user', PortalUserBinding.AccessStatus.REMOVED),
            ('enable-user', PortalUserBinding.AccessStatus.ENABLED),
        ):
            for _ in range(3):
                self.assert_success(self.post_action(action))
                binding = PortalUserBinding.objects.get()
                self.assertEqual(binding.access_status, expected_status)
                self.assertEqual(binding.user.audit_profile.role, AccountProfile.Role.ADMIN)
                self.assertEqual(binding.user.is_active, expected_status == PortalUserBinding.AccessStatus.ENABLED)
        self.assertEqual(get_user_model().objects.count(), 1)

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail', return_value=DETAIL)
    def test_default_role_preserves_existing_developer_and_password(self, _get_detail):
        user = get_user_model().objects.create_user(username=DETAIL['username'], password='local-password')
        AccountProfile.objects.create(user=user, role=AccountProfile.Role.DEVELOPER)
        self.assert_success(self.post_action('default-role'))
        user.refresh_from_db()
        self.assertEqual(user.audit_profile.role, AccountProfile.Role.DEVELOPER)
        self.assertTrue(user.check_password('local-password'))

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail')
    def test_user_mapping_conflicts_are_rejected(self, get_detail):
        user = get_user_model().objects.create_user(username=DETAIL['username'])
        AccountProfile.objects.create(user=user)
        PortalUserBinding.objects.create(portal_user_id='another-id', user=user)
        for detail in (DETAIL, {**DETAIL, 'user_id': 'wrong-returned-id'}):
            with self.subTest(detail=detail):
                get_detail.return_value = detail
                self.assertEqual(self.post_action('app-admin-set').data['code'], 40901)
        self.assertEqual(PortalUserBinding.objects.count(), 1)
        self.assertEqual(user.audit_profile.role, AccountProfile.Role.NORMAL)


@override_settings(PORTAL_ENCRYPT_ENABLED=True)
class EncryptedRegressionTests(APITestCase):
    APP_PRIVATE = '1' * 64
    PORTAL_PRIVATE = '2' * 64

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from gmssl import sm2
        helper = sm2.CryptSM2(private_key='', public_key='')
        cls.app_public = helper._kg(int(cls.APP_PRIVATE, 16), helper.ecc_table['g'])
        cls.portal_public = helper._kg(int(cls.PORTAL_PRIVATE, 16), helper.ecc_table['g'])

    def setUp(self):
        self.settings_override = override_settings(
            PORTAL_APP_PRIVATE_KEY=self.APP_PRIVATE,
            PORTAL_APP_PUBLIC_KEY=self.app_public,
            PORTAL_PUBLIC_KEY=self.portal_public,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def post_encrypted(self, action, payload, corrupt_digest=False):
        from gmssl import sm2
        ciphertext = b'\x04' + sm2.CryptSM2(private_key='', public_key=self.app_public, mode=0).encrypt(json.dumps(payload).encode())
        if corrupt_digest:
            ciphertext = ciphertext[:-1] + bytes([ciphertext[-1] ^ 1])
        encrypted = base64.b64encode(ciphertext).decode('ascii')
        signer = sm2.CryptSM2(private_key=self.PORTAL_PRIVATE, public_key=self.portal_public, mode=0, asn1=True)
        signature = base64.b64encode(bytes.fromhex(signer.sign_with_sm3(ciphertext, '3' * 64))).decode('ascii')
        return self.client.post(f'/api/portal/actions/{action}', {'data': encrypted}, format='json', HTTP_EYWA_SIGNATURE=signature)

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail', return_value=DETAIL)
    def test_all_six_actions_work_with_signed_encrypted_responses(self, _get_detail):
        from gmssl import sm2
        receiver = sm2.CryptSM2(private_key=self.PORTAL_PRIVATE, public_key=self.app_public, mode=0, asn1=True)
        for action in ('app-admin-set', 'disable-user', 'enable-user', 'remove-user', 'default-role', 'query-user-status'):
            with self.subTest(action=action):
                payload = {'user_ids': ['portal-user-1']} if action == 'query-user-status' else {'user_id': 'portal-user-1'}
                response = self.post_encrypted(action, payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['code'], 0)
                ciphertext = base64.b64decode(response.data['data'])
                self.assertEqual(ciphertext[0], 4)
                self.assertTrue(receiver.verify_with_sm3(base64.b64decode(response['App-Signature']).hex(), ciphertext))
                data = json.loads(receiver.decrypt(ciphertext[1:]))
                if action == 'query-user-status':
                    self.assertEqual(data[0]['status'], 1)
                else:
                    self.assertIsNone(data)

    def test_missing_signature_and_plaintext_are_rejected(self):
        for payload in ({'data': 'ciphertext'}, {'user_id': 'portal-user-1'}):
            response = self.client.post('/api/portal/actions/app-admin-set', payload, format='json')
            self.assertEqual(response.status_code, 401)
            self.assertFalse(PortalUserBinding.objects.exists())

    def test_corrupt_c3_is_rejected_even_with_a_valid_signature(self):
        response = self.post_encrypted('app-admin-set', {'user_id': 'portal-user-1'}, corrupt_digest=True)
        self.assertEqual(response.status_code, 401)
        self.assertFalse(PortalUserBinding.objects.exists())

    def test_invalid_key_configuration_cannot_mutate_users(self):
        for keys in (
            {'PORTAL_APP_PRIVATE_KEY': ''},
            {'PORTAL_APP_PRIVATE_KEY': '0' * 64},
            {'PORTAL_APP_PUBLIC_KEY': 'f' * 128},
            {'PORTAL_APP_PUBLIC_KEY': self.portal_public},
            {'PORTAL_PUBLIC_KEY': '04'},
        ):
            with self.subTest(keys=keys), override_settings(**keys):
                response = self.client.post('/api/portal/actions/app-admin-set', {'data': 'ciphertext'}, format='json')
                self.assertEqual(response.status_code, 503)
                self.assertFalse(PortalUserBinding.objects.exists())

    def test_invalid_encrypted_business_parameters_return_signed_error(self):
        response = self.post_encrypted('enable-user', {'user_id': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 40001)
        self.assertIn('App-Signature', response)
        self.assertEqual(PortalActionLog.objects.get().result_code, 40001)

    def test_response_encryption_does_not_use_standard_random(self):
        from portal_integration.services.crypto import PortalCrypto
        crypto = PortalCrypto()
        with patch('gmssl.func.choice', side_effect=AssertionError('insecure randomness')):
            ciphertext = crypto.encrypt_json({'status': 1})
        self.assertTrue(ciphertext)


@override_settings(PORTAL_BASE_URL='https://portal.example.test', PORTAL_APP_ID='test-app')
class PortalClientRegressionTests(SimpleTestCase):
    def make_client(self, payload):
        response = Mock()
        response.json.return_value = payload
        session = Mock()
        session.post.return_value = response
        return PortalClient(session=session), response

    @override_settings(PORTAL_ENCRYPT_ENABLED=True)
    def test_encrypted_mode_rejects_unsigned_plaintext_detail(self):
        client, _response = self.make_client({'code': 0, 'data': DETAIL})
        with self.assertRaises(PortalClientError):
            client.get_user_detail('portal-user-1')

    @override_settings(PORTAL_ENCRYPT_ENABLED=True)
    def test_bad_detail_signature_becomes_upstream_error(self):
        client, _response = self.make_client({'code': 0, 'data': 'ciphertext'})
        with patch('portal_integration.services.crypto.PortalCrypto') as crypto:
            crypto.return_value.verify_portal_signature.side_effect = PortalProtocolError('bad signature')
            with self.assertRaises(PortalClientError):
                client.get_user_detail('portal-user-1')

    def test_timeout_and_invalid_json_become_upstream_errors(self):
        client, response = self.make_client({})
        for failure in (requests.Timeout('timeout'), requests.ConnectionError('offline')):
            client.session.post.side_effect = failure
            with self.assertLogs('portal_integration.services.portal_client', level='WARNING'):
                with self.assertRaises(PortalClientError):
                    client.get_user_detail('portal-user-1')
        client.session.post.side_effect = None
        response.json.side_effect = ValueError('invalid json')
        with self.assertLogs('portal_integration.services.portal_client', level='WARNING'):
            with self.assertRaises(PortalClientError):
                client.get_user_detail('portal-user-1')
