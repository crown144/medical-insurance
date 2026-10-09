import base64
import json
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.auth import build_access_token
from accounts.models import AccountProfile
from portal_integration.models import PortalActionLog, PortalUserBinding


DETAIL = {
    'user_id': 'portal-user-1',
    'username': 'portal_account',
    'real_name': '门户用户',
    'email': 'portal@example.test',
    'department': '医保科',
    'expired_at': -1,
}


@override_settings(PORTAL_ENCRYPT_ENABLED=False, PORTAL_ALLOW_PLAINTEXT=True, DEBUG=True)
class PortalActionApiTests(APITestCase):
    def post(self, path, payload):
        return self.client.post(path, payload, format='json')

    def test_query_preserves_order_duplicates_and_unknown_users(self):
        user = get_user_model().objects.create_user(username='known')
        AccountProfile.objects.create(user=user)
        PortalUserBinding.objects.create(portal_user_id='known-id', user=user)

        response = self.post(
            '/api/portal/actions/query-user-status',
            {'user_ids': ['missing-id', 'known-id', 'missing-id']},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 0)
        self.assertEqual(
            [item['user_id'] for item in response.data['data']],
            ['missing-id', 'known-id', 'missing-id'],
        )
        self.assertEqual(response.data['data'][0]['exists'], 0)
        self.assertEqual(response.data['data'][1]['status'], 1)
        self.assertEqual(PortalUserBinding.objects.count(), 1)

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail', return_value=DETAIL)
    def test_default_role_creates_user_and_is_idempotent(self, get_detail):
        for _ in range(6):
            response = self.post(
                '/api/portal/actions/default-role',
                {'user_id': 'portal-user-1'},
            )
            self.assertEqual(response.data['code'], 0)

        self.assertEqual(get_user_model().objects.filter(username='portal_account').count(), 1)
        self.assertEqual(PortalUserBinding.objects.count(), 1)
        self.assertEqual(PortalActionLog.objects.filter(action_type='default_role_callback').count(), 6)
        binding = PortalUserBinding.objects.get()
        self.assertTrue(binding.user.is_active)
        self.assertEqual(binding.user.audit_profile.role, AccountProfile.Role.NORMAL)
        self.assertEqual(binding.profile_data['department'], '医保科')

    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail', return_value=DETAIL)
    def test_admin_disable_enable_and_remove_have_distinct_states(self, _get_detail):
        self.post('/api/portal/actions/app-admin-set', {'user_id': 'portal-user-1'})
        binding = PortalUserBinding.objects.get()
        self.assertEqual(binding.user.audit_profile.role, AccountProfile.Role.ADMIN)
        self.assertTrue(binding.is_admin)

        token = build_access_token(binding.user)
        self.post('/api/portal/actions/disable-user', {'user_id': 'portal-user-1'})
        disabled = self.post(
            '/api/portal/actions/query-user-status',
            {'user_ids': ['portal-user-1']},
        ).data['data'][0]
        self.assertEqual(disabled, {
            'user_id': 'portal-user-1',
            'status': 0,
            'admin': True,
            'expired': False,
            'exists': 1,
        })
        auth_response = self.client.get(
            '/api/user/info',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(auth_response.status_code, 401)

        self.post('/api/portal/actions/enable-user', {'user_id': 'portal-user-1'})
        binding.refresh_from_db()
        self.assertTrue(binding.user.is_active)
        self.assertEqual(binding.user.audit_profile.role, AccountProfile.Role.ADMIN)

        self.post('/api/portal/actions/remove-user', {'user_id': 'portal-user-1'})
        removed = self.post(
            '/api/portal/actions/query-user-status',
            {'user_ids': ['portal-user-1']},
        ).data['data'][0]
        self.assertEqual(removed['exists'], 0)
        self.assertEqual(removed['status'], 0)
        self.assertFalse(removed['admin'])

    def test_remove_and_disable_unknown_user_are_idempotent_noops(self):
        for path in ('remove-user', 'disable-user'):
            response = self.post(
                f'/api/portal/actions/{path}',
                {'user_id': 'never-seen'},
            )
            self.assertEqual(response.data['code'], 0)
        self.assertFalse(PortalUserBinding.objects.exists())

    def test_expired_binding_is_inactive_and_blocks_existing_token(self):
        user = get_user_model().objects.create_user(username='expired')
        AccountProfile.objects.create(user=user)
        PortalUserBinding.objects.create(
            portal_user_id='expired-id',
            user=user,
            portal_expired_at=int((time.time() - 60) * 1000),
        )
        token = build_access_token(user)

        status = self.post(
            '/api/portal/actions/query-user-status',
            {'user_ids': ['expired-id']},
        ).data['data'][0]
        self.assertTrue(status['expired'])
        self.assertEqual(status['status'], 0)
        self.assertEqual(
            self.client.get('/api/user/info', HTTP_AUTHORIZATION=f'Bearer {token}').status_code,
            401,
        )

    def test_empty_query_list_returns_business_error(self):
        response = self.post('/api/portal/actions/query-user-status', {'user_ids': []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], 40001)


class EncryptedPortalProtocolTests(APITestCase):
    APP_PRIVATE = '1' * 64
    PORTAL_PRIVATE = '2' * 64

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from gmssl import sm2

        helper = sm2.CryptSM2(private_key='', public_key='')
        cls.app_public = helper._kg(int(cls.APP_PRIVATE, 16), helper.ecc_table['g'])
        cls.portal_public = helper._kg(int(cls.PORTAL_PRIVATE, 16), helper.ecc_table['g'])

    @override_settings(PORTAL_ENCRYPT_ENABLED=True)
    @patch('portal_integration.services.portal_client.PortalClient.get_user_detail', return_value=DETAIL)
    def test_encrypted_request_and_signed_encrypted_response(self, _get_detail):
        from gmssl import sm2

        with override_settings(
            PORTAL_APP_PRIVATE_KEY=self.APP_PRIVATE,
            PORTAL_APP_PUBLIC_KEY=self.app_public,
            PORTAL_PUBLIC_KEY=self.portal_public,
        ):
            portal_sender = sm2.CryptSM2(
                private_key='',
                public_key=self.app_public,
                mode=0,
            )
            portal_signer = sm2.CryptSM2(
                private_key=self.PORTAL_PRIVATE,
                public_key=self.portal_public,
                mode=0,
                asn1=True,
            )
            plaintext = json.dumps({'user_id': 'portal-user-1'}).encode('utf-8')
            ciphertext = b'\x04' + portal_sender.encrypt(plaintext)
            encrypted = base64.b64encode(ciphertext).decode('ascii')
            signature = base64.b64encode(bytes.fromhex(portal_signer.sign_with_sm3(ciphertext, '3' * 64))).decode('ascii')

            response = self.client.post(
                '/api/portal/actions/default-role',
                encrypted,
                content_type='application/json',
                HTTP_EYWA_SIGNATURE=signature,
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['code'], 0)
            response_ciphertext = response.data['data']
            portal_receiver = sm2.CryptSM2(
                private_key=self.PORTAL_PRIVATE,
                public_key=self.app_public,
                mode=0,
                asn1=True,
            )
            decrypted = portal_receiver.decrypt(base64.b64decode(response_ciphertext)[1:])
            self.assertIsNone(json.loads(decrypted.decode('utf-8')))
            self.assertTrue(
                portal_receiver.verify_with_sm3(
                    base64.b64decode(response['App-Signature']).hex(),
                    base64.b64decode(response_ciphertext),
                )
            )

    @override_settings(PORTAL_ENCRYPT_ENABLED=True)
    def test_invalid_signature_is_rejected(self):
        with override_settings(
            PORTAL_APP_PRIVATE_KEY=self.APP_PRIVATE,
            PORTAL_APP_PUBLIC_KEY=self.app_public,
            PORTAL_PUBLIC_KEY=self.portal_public,
        ):
            response = self.client.post(
                '/api/portal/actions/default-role',
                {'data': base64.b64encode(b'broken').decode('ascii')},
                format='json',
                HTTP_EYWA_SIGNATURE='00' * 64,
            )
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.data['code'], 40101)
