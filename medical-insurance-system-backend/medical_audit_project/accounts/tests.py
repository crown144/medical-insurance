import time

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from accounts.auth import build_access_token
from accounts.models import AccountProfile
from accounts.middleware import ApiAccessMiddleware
from portal_integration.models import PortalUserBinding


@override_settings(PORTAL_ENCRYPT_ENABLED=False, PORTAL_ALLOW_PLAINTEXT=True, DEBUG=True)
class BusinessApiAccessTests(APITestCase):
    paths = ('/api/tasks/', '/api/rules/', '/api/results/')

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='access-test', password='test-password')
        AccountProfile.objects.create(user=self.user)
        self.binding = PortalUserBinding.objects.create(portal_user_id='access-id', user=self.user)
        self.token = build_access_token(self.user)

    def assert_business_status(self, expected):
        for path in self.paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, expected)

    def test_anonymous_and_invalid_token_cannot_access_business_data(self):
        self.assert_business_status(401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        self.assert_business_status(401)

    def test_active_normal_user_can_access_business_data(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assert_business_status(200)

    def test_disabling_and_reenabling_controls_existing_token(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assert_business_status(200)
        response = self.client.post('/api/portal/actions/disable-user', {'user_id': 'access-id'}, format='json')
        self.assertEqual(response.data['code'], 0)
        self.assert_business_status(401)
        response = self.client.post('/api/portal/actions/enable-user', {'user_id': 'access-id'}, format='json')
        self.assertEqual(response.data['code'], 0)
        self.assert_business_status(200)

    def test_removed_user_cannot_access_business_data(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.client.post('/api/portal/actions/remove-user', {'user_id': 'access-id'}, format='json')
        self.assert_business_status(401)

    def test_expired_binding_cannot_access_business_data(self):
        self.binding.portal_expired_at = int(time.time()) - 60
        self.binding.save(update_fields=['portal_expired_at'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assert_business_status(401)

    def test_local_unbound_user_can_still_login_and_access_business_data(self):
        local = get_user_model().objects.create_user(username='local-test', password='local-password')
        AccountProfile.objects.create(user=local)
        response = self.client.post('/api/auth/login', {'username': 'local-test', 'password': 'local-password'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['result']['accessToken']}")
        self.assert_business_status(200)

    def test_health_menu_and_logout_remain_available_without_token(self):
        self.assertEqual(self.client.get('/api/menu/all').status_code, 200)
        self.assertEqual(self.client.post('/api/auth/logout', {}, format='json').status_code, 200)


class ProductionKeyTests(SimpleTestCase):
    @override_settings(DEBUG=False, SECRET_KEY='django-insecure-public-development-key')
    def test_production_rejects_the_public_development_key(self):
        with self.assertRaises(ImproperlyConfigured):
            ApiAccessMiddleware(lambda request: None)

    @override_settings(DEBUG=False, SECRET_KEY='test-only-private-key')
    def test_production_accepts_an_explicit_private_key(self):
        ApiAccessMiddleware(lambda request: None)
