"""Regression checks against v1.9's published examples, not live credentials."""
import base64
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

from Cryptodome.Util.asn1 import DerBitString, DerObjectId, DerSequence
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from accounts.auth import build_access_token
from accounts.models import AccountProfile
from portal_integration.models import PortalActionLog, PortalUserBinding
from portal_integration.services.crypto import PortalCrypto, _normalise_hex_key
from portal_integration.services.exceptions import PortalClientError, PortalConfigurationError, PortalProtocolError
from portal_integration.services.portal_client import PortalClient


VECTORS = json.loads((Path(__file__).parent / 'fixtures' / 'portal_v19_public_examples.json').read_text())
BC_CALLBACK = json.loads((Path(__file__).parent / 'fixtures' / 'bouncycastle_170_callback.json').read_text())
DOCUMENT_KEYS = {
    'PORTAL_APP_PRIVATE_KEY': VECTORS['app_private'],
    'PORTAL_APP_PUBLIC_KEY': VECTORS['app_public'],
    'PORTAL_PUBLIC_KEY': VECTORS['portal_public'],
}
CALLBACK_DETAIL = {
    'id': 'portal-user-1', 'username': 'portal_account', 'fullname': '门户用户',
    'phone': '', 'email': 'portal@example.test', 'organization_code': 'hospital-1',
    'department': '医保科', 'create_time': '2026-09-01 12:00:00',
    'update_time': '2026-10-02 12:00:00', 'expired': -1, 'status': 1,
}


@override_settings(**DOCUMENT_KEYS)
class DocumentCryptoTests(SimpleTestCase):
    def test_reference_java_request_signature_and_ciphertext(self):
        # This ciphertext/signature pair was generated outside this codebase.
        with override_settings(
            PORTAL_APP_PRIVATE_KEY=VECTORS['portal_private'],
            PORTAL_APP_PUBLIC_KEY=VECTORS['portal_public'],
            PORTAL_PUBLIC_KEY=VECTORS['app_public'],
        ):
            crypto = PortalCrypto()
            crypto.verify_portal_signature(VECTORS['request_ciphertext'], VECTORS['request_signature'])
            plaintext = crypto.decrypt_json(VECTORS['request_ciphertext'])
        self.assertEqual(plaintext['page_no'], 1)
        self.assertEqual(plaintext['data']['begin_time'], '2021-12-14 22:07:25')

    def test_reference_response_c3_and_data(self):
        plaintext = PortalCrypto().decrypt_json(VECTORS['response_ciphertext'])
        self.assertEqual(plaintext['data'][0]['id'], 'c819f3e1-4d30-46ce-9372-ec2543a3d482')

    def test_unmatched_response_signature_in_reference_is_rejected(self):
        # The appendix's response signature does not match its ciphertext with
        # the provided portal public key. Never bypass verification to accept it.
        with self.assertRaises(PortalProtocolError):
            PortalCrypto().verify_portal_signature(VECTORS['response_ciphertext'], VECTORS['response_signature'])

    def test_public_key_pem_and_private_key_without_base64_padding(self):
        public_pem = f"-----BEGIN PUBLIC KEY-----\n{VECTORS['app_public']}\n-----END PUBLIC KEY-----"
        with override_settings(PORTAL_APP_PUBLIC_KEY=public_pem, PORTAL_APP_PRIVATE_KEY=VECTORS['app_private'].rstrip('=')):
            self.assertIsInstance(PortalCrypto(), PortalCrypto)

    def test_different_named_curve_is_rejected(self):
        algorithm = DerSequence([DerObjectId('1.2.840.10045.2.1'), DerObjectId('1.2.840.10045.3.1.7')]).encode()
        point = b'\x04' + bytes.fromhex(_normalise_hex_key(VECTORS['app_public'], public=True))
        key = base64.b64encode(DerSequence([algorithm, DerBitString(point)]).encode()).decode()
        with override_settings(PORTAL_APP_PUBLIC_KEY=key), self.assertRaises(PortalConfigurationError):
            PortalCrypto()

    def test_zero_negative_or_oversized_signature_integers_are_rejected(self):
        for integers in ([0, 1], [-1, 1], [1, 2 ** 256], [1, 2, 3]):
            signature = base64.b64encode(DerSequence(integers).encode()).decode()
            with self.subTest(integers=integers), self.assertRaises(PortalProtocolError):
                PortalCrypto().verify_portal_signature(VECTORS['request_ciphertext'], signature)


@override_settings(PORTAL_BASE_URL='https://portal.example.test', PORTAL_APP_ID='test-app', **DOCUMENT_KEYS)
class DocumentClientTests(SimpleTestCase):
    def test_independent_java_signed_user_detail_is_accepted(self):
        response = Mock(headers={'eywa-signature': BC_CALLBACK['signature']})
        response.json.return_value = {'code': 0, 'data': BC_CALLBACK['ciphertext']}
        session = Mock()
        session.post.return_value = response
        detail = PortalClient(session=session).get_user_detail('bc-user-1')
        self.assertEqual(detail['username'], 'bc_account')
        self.assertEqual(detail['fullname'], '门户互通测试')
        self.assertEqual(detail['expired'], -1)

    def test_user_detail_uses_post_id_and_header_even_for_plaintext_actions(self):
        response = Mock(headers={'eywa-signature': 'signature'})
        response.json.return_value = {'code': 0, 'data': 'ciphertext'}
        session = Mock()
        session.post.return_value = response
        with override_settings(PORTAL_ENCRYPT_ENABLED=False), patch(
            'portal_integration.services.crypto.PortalCrypto',
        ) as crypto:
            crypto.return_value.decrypt_json.return_value = CALLBACK_DETAIL
            self.assertEqual(PortalClient(session=session).get_user_detail('portal-user-1'), CALLBACK_DETAIL)
        session.post.assert_called_once_with(
            'https://portal.example.test/api/security-manage-permission/v1/user/info',
            json={'id': 'portal-user-1'}, headers={'appid': 'test-app', 'Content-Type': 'application/json'}, timeout=10,
        )
        crypto.return_value.verify_portal_signature.assert_called_once_with('ciphertext', 'signature')
        session.get.assert_not_called()

    def test_nonzero_missing_or_wrong_type_business_codes_do_not_supply_users(self):
        for code in (None, True, '0', 200, 1):
            response = Mock()
            response.json.return_value = {'code': code, 'data': CALLBACK_DETAIL}
            session = Mock()
            session.post.return_value = response
            with self.subTest(code=code), self.assertRaises(PortalClientError):
                PortalClient(session=session).get_user_detail('portal-user-1')

    def test_signed_detail_with_missing_identity_or_expiry_is_rejected(self):
        for update in ({'id': 'other'}, {'expired': None}, {'status': True}, {'username': ''}):
            response = Mock(headers={'eywa-signature': 'signature'})
            response.json.return_value = {'code': 0, 'data': 'ciphertext'}
            session = Mock()
            session.post.return_value = response
            with patch('portal_integration.services.crypto.PortalCrypto') as crypto:
                crypto.return_value.decrypt_json.return_value = {**CALLBACK_DETAIL, **update}
                with self.subTest(update=update), self.assertRaises(PortalClientError):
                    PortalClient(session=session).get_user_detail('portal-user-1')


@override_settings(PORTAL_ENCRYPT_ENABLED=False, PORTAL_ALLOW_PLAINTEXT=True, DEBUG=True)
class UserCallbackTests(APITestCase):
    def callback(self, action='create-user', **updates):
        return self.client.post(f'/api/portal/actions/{action}', {**CALLBACK_DETAIL, **updates}, format='json')

    def action(self, name):
        return self.client.post(f'/api/portal/actions/{name}', {'user_id': CALLBACK_DETAIL['id']}, format='json')

    def test_create_retry_uses_callback_fields_without_an_upstream_query(self):
        with patch('portal_integration.services.portal_client.PortalClient.get_user_detail') as query:
            for _ in range(3):
                self.assertEqual(self.callback().data['code'], 0)
        query.assert_not_called()
        binding = PortalUserBinding.objects.select_related('user').get()
        self.assertEqual(binding.portal_expired_at, -1)
        self.assertEqual(binding.user.first_name, CALLBACK_DETAIL['fullname'])
        self.assertEqual(binding.profile_data['organization_code'], 'hospital-1')
        self.assertFalse(binding.user.has_usable_password())
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_edit_renames_same_user_updates_expiration_and_preserves_password_and_role(self):
        user = get_user_model().objects.create_user(username=CALLBACK_DETAIL['username'], password='local-password')
        AccountProfile.objects.create(user=user, role=AccountProfile.Role.ADMIN)
        self.callback()
        expiry = int(time.time()) - 10
        response = self.callback('edit-user', username='new_portal_name', fullname='新姓名', email='', expired=expiry)
        self.assertEqual(response.data['code'], 0)
        binding = PortalUserBinding.objects.get()
        self.assertEqual(binding.user_id, user.pk)
        self.assertEqual(binding.portal_expired_at, expiry)
        user.refresh_from_db()
        self.assertEqual(user.username, 'new_portal_name')
        self.assertEqual(user.first_name, '新姓名')
        self.assertEqual(user.email, '')
        self.assertTrue(user.check_password('local-password'))
        self.assertEqual(user.audit_profile.role, AccountProfile.Role.ADMIN)
        self.assertEqual(self.client.get('/api/user/info', HTTP_AUTHORIZATION=f'Bearer {build_access_token(user)}').status_code, 401)
        self.assertEqual(self.callback('edit-user', username='new_portal_name', expired=-1).data['code'], 0)
        self.assertEqual(self.client.get('/api/user/info', HTTP_AUTHORIZATION=f'Bearer {build_access_token(user)}').status_code, 200)

    def test_global_disable_survives_application_enable_and_admin_grant(self):
        self.callback(status=2)
        for action in ('app-admin-set', 'enable-user', 'default-role'):
            self.assertEqual(self.action(action).data['code'], 0)
            self.assertFalse(PortalUserBinding.objects.get().user.is_active)
        query = self.client.post('/api/portal/actions/query-user-status', {'user_ids': [CALLBACK_DETAIL['id']]}, format='json')
        self.assertEqual(query.data['data'][0]['status'], 0)
        self.assertEqual(self.callback('edit-user', status=1).data['code'], 0)
        self.assertTrue(PortalUserBinding.objects.get().user.is_active)

    def test_edit_does_not_restore_disabled_or_removed_application_access(self):
        for action, expected in (('disable-user', 'DISABLED'), ('remove-user', 'REMOVED')):
            self.callback()
            self.action(action)
            self.assertEqual(self.callback('edit-user', status=1, expired=-1).data['code'], 0)
            binding = PortalUserBinding.objects.get()
            self.assertEqual(binding.access_status, expected)
            self.assertFalse(binding.user.is_active)

    def test_edit_unknown_user_synchronizes_full_record(self):
        self.assertEqual(self.callback('edit-user').data['code'], 0)
        self.assertEqual(PortalUserBinding.objects.count(), 1)

    def test_edit_cannot_take_another_local_login_name(self):
        self.callback()
        get_user_model().objects.create_user(username='occupied')
        response = self.callback('edit-user', username='occupied', expired=0)
        self.assertEqual(response.data['code'], 40901)
        binding = PortalUserBinding.objects.get()
        self.assertEqual(binding.user.username, CALLBACK_DETAIL['username'])
        self.assertEqual(binding.portal_expired_at, -1)

    def test_invalid_detail_is_rejected_without_a_partial_user(self):
        for update in ({'expired': True}, {'expired': -2}, {'status': 3}, {'status': '1'}, {'id': 123}, {'username': 'x' * 151}):
            with self.subTest(update=update):
                self.assertEqual(self.callback(**update).data['code'], 40001)
        self.assertFalse(PortalUserBinding.objects.exists())
        self.assertFalse(get_user_model().objects.exists())

    def test_each_documented_required_field_is_checked(self):
        for name in CALLBACK_DETAIL.keys() - {'email'}:
            payload = {k: v for k, v in CALLBACK_DETAIL.items() if k != name}
            response = self.client.post('/api/portal/actions/create-user', payload, format='json')
            with self.subTest(field=name):
                self.assertEqual(response.data['code'], 40001)
        self.assertFalse(get_user_model().objects.exists())

    def test_callback_response_failure_rolls_back_new_and_existing_records(self):
        for exists in (False, True):
            if exists:
                self.callback()
            error = PortalProtocolError('response failure', http_status=500)
            with patch('portal_integration.views.PortalProtocol.encode_response', side_effect=[
                error, ({'code': 40101, 'message': str(error), 'data': None}, {}),
            ]):
                response = self.callback('edit-user', expired=0)
            self.assertEqual(response.status_code, 500)
            if exists:
                self.assertEqual(PortalUserBinding.objects.get().portal_expired_at, -1)
            else:
                self.assertFalse(PortalUserBinding.objects.exists())
        self.assertEqual(PortalActionLog.objects.filter(result_code=40101).count(), 2)

    def test_database_conflict_does_not_acknowledge_an_unapplied_profile_edit(self):
        self.callback()
        with patch('django.contrib.auth.models.User.save', side_effect=IntegrityError('concurrent rename')):
            response = self.callback('edit-user', expired=0)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['code'], 40901)
        self.assertEqual(PortalUserBinding.objects.get().portal_expired_at, -1)

    def test_upstream_timeout_returns_http_failure_for_portal_retry(self):
        with patch('portal_integration.services.portal_client.PortalClient.get_user_detail', side_effect=PortalClientError('timeout')):
            response = self.action('app-admin-set')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['code'], 50001)
        self.assertFalse(PortalUserBinding.objects.exists())


@override_settings(PORTAL_ENCRYPT_ENABLED=True, **DOCUMENT_KEYS)
class EncryptedCallbackTests(APITestCase):
    def test_admin_action_fetches_and_synchronizes_independent_java_user_detail(self):
        upstream = Mock(headers={'eywa-signature': BC_CALLBACK['signature']})
        upstream.json.return_value = {'code': 0, 'data': BC_CALLBACK['ciphertext']}
        session = Mock()
        session.post.return_value = upstream
        with override_settings(PORTAL_BASE_URL='https://portal.example.test', PORTAL_APP_ID='test-app'):
            with patch('portal_integration.services.portal_client.requests.Session', return_value=session):
                response = self.encrypted_request({'user_id': 'bc-user-1'}, action='app-admin-set')
        self.assertEqual(response.data['code'], 0)
        binding = PortalUserBinding.objects.get(portal_user_id='bc-user-1')
        self.assertTrue(binding.is_admin)
        self.assertEqual(binding.portal_expired_at, -1)
        self.assertEqual(binding.user.first_name, '门户互通测试')

    def test_independent_java_callback_creates_local_user(self):
        response = self.client.post(
            '/api/portal/actions/create-user', BC_CALLBACK['ciphertext'],
            content_type='application/json', HTTP_EYWA_SIGNATURE=BC_CALLBACK['signature'],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 0)
        binding = PortalUserBinding.objects.get(portal_user_id='bc-user-1')
        self.assertEqual(binding.user.username, 'bc_account')
        self.assertEqual(binding.user.first_name, '门户互通测试')

    def encrypted_request(self, detail, *, action='create-user', body_format='raw'):
        from gmssl import sm2

        app_public = _normalise_hex_key(VECTORS['app_public'], public=True)
        portal_public = _normalise_hex_key(VECTORS['portal_public'], public=True)
        sender = sm2.CryptSM2(private_key='', public_key=app_public, mode=0)
        signer = sm2.CryptSM2(private_key=_normalise_hex_key(VECTORS['portal_private']), public_key=portal_public, asn1=True)
        ciphertext = b'\x04' + sender.encrypt(json.dumps(detail).encode())
        content = base64.b64encode(ciphertext).decode()
        signature = base64.b64encode(bytes.fromhex(signer.sign_with_sm3(ciphertext, '3' * 64))).decode()
        body = content if body_format == 'raw' else json.dumps(content if body_format == 'string' else {'data': content})
        return self.client.post(f'/api/portal/actions/{action}', body, content_type='application/json', HTTP_EYWA_SIGNATURE=signature)

    def test_both_callbacks_support_documented_raw_base64_and_compatible_json_forms(self):
        for action in ('create-user', 'edit-user'):
            for body_format in ('raw', 'string', 'wrapper'):
                with self.subTest(action=action, body_format=body_format):
                    response = self.encrypted_request(CALLBACK_DETAIL, action=action, body_format=body_format)
                    self.assertEqual(response.data['code'], 0)
                    self.assertEqual(response.status_code, 200)
                    with override_settings(
                        PORTAL_APP_PRIVATE_KEY=VECTORS['portal_private'],
                        PORTAL_APP_PUBLIC_KEY=VECTORS['portal_public'],
                        PORTAL_PUBLIC_KEY=VECTORS['app_public'],
                    ):
                        PortalCrypto().verify_portal_signature(response.data['data'], response['App-Signature'])
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_bad_encrypted_callback_does_not_create_user(self):
        response = self.encrypted_request({'id': 'missing-other-fields'})
        self.assertEqual(response.data['code'], 40001)
        self.assertFalse(PortalUserBinding.objects.exists())
