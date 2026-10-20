"""A valid portal ticket must never undo a local account suspension."""

import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from accounts.models import AccountProfile
from portal_integration.models import PortalLoginCode, PortalUserBinding


DETAIL = {
    'id': 'locally-disabled-portal-id',
    'username': 'locally-disabled-user',
    'fullname': 'Different portal display name',
    'email': 'portal@example.test',
    'status': 1,
    'expired': -1,
}
VALIDATE = 'portal_integration.services.portal_client.PortalClient.validate_ticket'
WRITES = re.compile(r'^\s*(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|CREATE|DROP|TRUNCATE)\b', re.I)


@override_settings(
    PORTAL_AUTH_MODE='synced',
    PORTAL_APP_ID='test-app',
    PORTAL_FRONTEND_URL='https://insurance.example.test/yibao',
)
class SyncedLoginLocalSuspensionTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username=DETAIL['username'], password='keep-existing-password',
            is_active=False, first_name='Local display name', email='local@example.test',
        )
        AccountProfile.objects.create(user=self.user, role=AccountProfile.Role.DEVELOPER)

    def bind_existing_user(self):
        return PortalUserBinding.objects.create(
            portal_user_id=DETAIL['id'], user=self.user,
            access_status=PortalUserBinding.AccessStatus.ENABLED,
            profile_data={'status': 1, 'username': self.user.username},
            portal_expired_at=-1,
        )

    def snapshot(self):
        return (
            list(get_user_model().objects.order_by('pk').values()),
            list(AccountProfile.objects.order_by('pk').values()),
            list(PortalUserBinding.objects.order_by('pk').values()),
            list(PortalLoginCode.objects.order_by('pk').values()),
        )

    def assert_ticket_login_preserves_suspension(self, *, endpoint='/api/sso/login', method='post'):
        before = self.snapshot()
        data = {'ticket': 'ST-valid-portal-ticket', 'appid': 'test-app'}
        with CaptureQueriesContext(connection) as queries:
            if method == 'post':
                response = self.client.post(endpoint, data, format='json')
            else:
                response = self.client.get(endpoint, data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.snapshot(), before)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        for query in queries:
            self.assertFalse(WRITES.match(query['sql']), query['sql'])

    @patch(VALIDATE, return_value=DETAIL)
    def test_existing_unbound_inactive_user_cannot_be_reactivated_or_bound_by_login(self, validate):
        self.assert_ticket_login_preserves_suspension()
        validate.assert_called_once_with('ST-valid-portal-ticket', 'test-app')

    @patch(VALIDATE, return_value=DETAIL)
    def test_existing_bound_inactive_user_cannot_be_reactivated_by_login(self, validate):
        self.bind_existing_user()
        self.assert_ticket_login_preserves_suspension()
        validate.assert_called_once_with('ST-valid-portal-ticket', 'test-app')

    @patch(VALIDATE, return_value={**DETAIL, 'username': 'portal-renamed-disabled-user'})
    def test_portal_id_match_cannot_rename_or_reactivate_suspended_user_on_server_callback(self, validate):
        self.bind_existing_user()
        self.assert_ticket_login_preserves_suspension(
            endpoint='/api/portal/sso/callback', method='get',
        )
        validate.assert_called_once_with('ST-valid-portal-ticket', 'test-app')
