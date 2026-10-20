"""Exercise real old tables, rather than mocks that hide schema dependencies.

Run this module in its own process with medical_audit_project.test_settings_legacy.
All migrations and fixtures below affect only Django's temporary test database.
"""

from contextlib import contextmanager
from io import StringIO
import re
import time
from unittest import skipUnless
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.state import ModelState
from django.db.models.query import QuerySet
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITransactionTestCase

from accounts.auth import build_access_token
from accounts.models import AccountProfile
from portal_integration.services.exceptions import PortalProtocolError
from results.models import Result
from rules.models import Rule
from tasks.models import Task


DETAIL = {
    'id': 'existing-portal-id',
    'username': 'existing-auditor',
    'fullname': '门户显示名不覆盖本地姓名',
    'status': 1,
    'expired': -1,
}
VALIDATE = 'portal_integration.services.portal_client.PortalClient.validate_ticket'
FRONTEND = 'https://10.130.76.47:8088/yibao'
WRITES = re.compile(r'^\s*(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|CREATE|DROP|TRUNCATE)\b', re.I)
ACCOUNT_INSERTS = re.compile(
    r'^\s*INSERT\s+INTO\s+["`]?(?:auth_user|accounts_accountprofile)["`]?\s*\(',
    re.I,
)


@skipUnless(
    settings.LEGACY_DATABASE_COMPATIBILITY and settings.PORTAL_AUTH_MODE == 'existing',
    'Run separately with --settings=medical_audit_project.test_settings_legacy.',
)
@override_settings(
    PORTAL_BASE_URL='http://10.130.76.194',
    PORTAL_APP_ID='existing-app',
    PORTAL_FRONTEND_URL=FRONTEND,
    PORTAL_CAS_LOGIN_URL='http://10.130.76.194/ucenter/uinfo/cas/js/login',
    PORTAL_LOGIN_CALLBACK_URL=f'{FRONTEND}/#/auth/sso',
    PORTAL_AUTO_CREATE_USERS=False,
)
class ExistingSchemaTests(APITransactionTestCase):
    """The application sees the same absent tables/column as the old server."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        executor = MigrationExecutor(connection)
        cls.latest_targets = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([
                ('rules', '0005_remove_rule_rule_name_rule_drug_name'),
                ('accounts', '0001_initial'),
                ('portal_integration', None),
            ])
        except Exception:
            MigrationExecutor(connection).migrate(cls.latest_targets)
            super().tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            MigrationExecutor(connection).migrate(cls.latest_targets)
        finally:
            super().tearDownClass()

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username=DETAIL['username'], password='existing-password',
            first_name='本地姓名', email='local@example.test',
        )
        self.profile = AccountProfile.objects.create(
            user=self.user, role=AccountProfile.Role.DEVELOPER,
        )
        self.rule = Rule.objects.create(
            rule_id='old-rule', drug_name='静脉注射', description='旧规则',
            type='重复收费', status=True, logic_expression='preserve-expression',
            rule_code='def execute_rule(record, item):\n    return []',
        )
        self.task = Task.objects.create(name='旧审核任务', hospitalization_ids=['old-case'])
        self.result = Result.objects.create(
            task=self.task, rule=self.rule, hospitalization_id='old-case',
        )

    def account_snapshot(self):
        return (
            list(get_user_model().objects.order_by('pk').values()),
            list(AccountProfile.objects.order_by('pk').values()),
        )

    @contextmanager
    def compatible_queries(self, *, allow_rule_writes=False, allow_account_inserts=False):
        with CaptureQueriesContext(connection) as captured:
            yield captured
        for query in captured:
            sql = query['sql']
            self.assertNotIn('portal_integration_', sql.lower(), sql)
            self.assertNotIn('is_deleted', sql.lower(), sql)
            if WRITES.match(sql):
                if allow_account_inserts and ACCOUNT_INSERTS.match(sql):
                    continue
                self.assertTrue(allow_rule_writes, sql)
                self.assertIn('rules_rule', sql.lower(), sql)

    def login(self, **data):
        return self.client.post(
            '/api/sso/login',
            {'ticket': 'ST-existing', 'appid': 'existing-app', **data},
            format='json',
        )

    def authenticate_business_requests(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {build_access_token(self.user)}')

    def test_schema_really_has_no_portal_tables_or_new_rule_column(self):
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
            columns = connection.introspection.get_table_description(cursor, 'rules_rule')
        self.assertFalse(any(name.startswith('portal_integration_') for name in tables))
        self.assertNotIn('is_deleted', {column.name for column in columns})
        self.assertFalse(Rule._meta.get_field('is_deleted').concrete)
        self.assertIs(self.rule.is_deleted, False)
        # Migration state must remain the ordinary field declared by 0006.
        self.assertIs(
            type(ModelState.from_model(Rule).fields['is_deleted']), models.BooleanField,
        )

    def test_password_login_and_business_reads_preserve_existing_accounts(self):
        before = self.account_snapshot()
        with self.compatible_queries():
            response = self.client.post('/api/auth/login', {
                'username': self.user.username, 'password': 'existing-password',
            }, format='json')
            self.assertEqual(response.status_code, 200)
            token = response.data['result']['accessToken']
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            for path in [
                '/api/user/info', '/api/auth/codes', '/api/tasks/',
                f'/api/tasks/{self.task.pk}/', '/api/rules/',
                f'/api/rules/{self.rule.pk}/', '/api/results/',
            ]:
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.account_snapshot(), before)

    @override_settings(
        ALLOWED_HOSTS=['10.130.76.47'],
        PORTAL_ENCRYPT_ENABLED=False,
        PORTAL_PUBLIC_KEY='', PORTAL_APP_PUBLIC_KEY='', PORTAL_APP_PRIVATE_KEY='',
    )
    def test_portal_preflight_accepts_real_old_schema_without_executing_migrations(self):
        before = self.account_snapshot()
        output = StringIO()
        with self.compatible_queries():
            call_command('check_portal_sso', database=True, stdout=output)
        self.assertIn('门户账号模式：existing', output.getvalue())
        self.assertIn('本地配置检查通过', output.getvalue())
        self.assertNotIn('数据库存在未应用迁移', output.getvalue())
        self.assertEqual(self.account_snapshot(), before)
        with connection.cursor() as cursor:
            self.assertFalse(any(
                name.startswith('portal_integration_')
                for name in connection.introspection.table_names(cursor)
            ))
            self.assertNotIn('is_deleted', {
                column.name
                for column in connection.introspection.get_table_description(cursor, 'rules_rule')
            })

    @patch(VALIDATE, return_value=DETAIL)
    def test_sso_maps_existing_username_without_creating_or_editing_accounts(self, validate):
        before = self.account_snapshot()
        with self.compatible_queries():
            response = self.login()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['result']['roles'], ['developer'])
            self.assertEqual(response.data['result']['realName'], '本地姓名')
            self.client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {response.data['result']['accessToken']}",
            )
            self.assertEqual(self.client.get('/api/user/info').status_code, 200)
            self.assertEqual(self.client.get('/api/tasks/').status_code, 200)
        validate.assert_called_once_with('ST-existing', 'existing-app')
        self.assertEqual(self.account_snapshot(), before)

    @patch(VALIDATE, return_value={**DETAIL, 'username': 'unknown-portal-user'})
    def test_unknown_portal_user_is_denied_without_provisioning(self, _validate):
        before = self.account_snapshot()
        with self.compatible_queries():
            self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.account_snapshot(), before)

    @override_settings(PORTAL_AUTO_CREATE_USERS=True)
    @patch(VALIDATE, return_value={
        **DETAIL, 'username': 'new-portal-user',
        'role': 'admin', 'roles': ['admin'], 'is_staff': True, 'is_superuser': True,
    })
    def test_auto_create_provisions_only_a_normal_account_and_reuses_it_on_retry(self, validate):
        before = self.account_snapshot()
        with self.compatible_queries(allow_account_inserts=True):
            response = self.login()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['result']['roles'], ['normal'])
            user = get_user_model().objects.get(username='new-portal-user')
            self.assertTrue(user.is_active)
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertFalse(user.has_usable_password())
            self.assertEqual(user.audit_profile.role, AccountProfile.Role.NORMAL)
            self.assertEqual(get_user_model().objects.count(), len(before[0]) + 1)
            self.assertEqual(AccountProfile.objects.count(), len(before[1]) + 1)
        after_first_login = self.account_snapshot()
        with self.compatible_queries():
            retry = self.login()
            self.assertEqual(retry.status_code, 200)
            self.assertEqual(retry.data['result']['userId'], str(user.pk))
            self.client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {retry.data['result']['accessToken']}",
            )
            self.assertEqual(self.client.get('/api/user/info').status_code, 200)
            self.assertEqual(self.client.get('/api/tasks/').status_code, 200)
        self.assertEqual(self.account_snapshot(), after_first_login)
        self.assertEqual(after_first_login[0][0], before[0][0])
        self.assertEqual(after_first_login[1][0], before[1][0])
        self.assertEqual(validate.call_count, 2)

    @override_settings(PORTAL_AUTO_CREATE_USERS=True)
    @patch(VALIDATE, return_value={**DETAIL, 'username': 'existing-without-profile'})
    def test_auto_create_adds_missing_normal_profile_without_overwriting_existing_user(self, validate):
        user = get_user_model().objects.create_user(
            username='existing-without-profile', password='keep-this-password',
            first_name='已有名字', last_name='已有姓氏', email='keep@example.test',
        )
        before_user = get_user_model().objects.filter(pk=user.pk).values().get()
        profiles_before = AccountProfile.objects.count()
        with self.compatible_queries(allow_account_inserts=True):
            response = self.login()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['result']['roles'], ['normal'])
            self.assertEqual(AccountProfile.objects.get(user=user).role, AccountProfile.Role.NORMAL)
            self.assertEqual(AccountProfile.objects.count(), profiles_before + 1)
        self.assertEqual(get_user_model().objects.filter(pk=user.pk).values().get(), before_user)
        user.refresh_from_db()
        self.assertTrue(user.check_password('keep-this-password'))
        after_first_login = self.account_snapshot()
        with self.compatible_queries():
            self.assertEqual(self.login().status_code, 200)
        self.assertEqual(self.account_snapshot(), after_first_login)
        self.assertEqual(validate.call_count, 2)

    @override_settings(PORTAL_AUTO_CREATE_USERS=True)
    @patch(VALIDATE)
    def test_auto_create_keeps_existing_developer_and_admin_passwords_roles_and_names(self, validate):
        admin = get_user_model().objects.create_user(
            username='existing-app-admin', password='admin-password', first_name='本地管理员',
        )
        AccountProfile.objects.create(user=admin, role=AccountProfile.Role.ADMIN)
        before = self.account_snapshot()
        with self.compatible_queries():
            for user, role, name in [
                (self.user, 'developer', '本地姓名'), (admin, 'admin', '本地管理员'),
            ]:
                with self.subTest(role=role):
                    validate.return_value = {**DETAIL, 'username': user.username}
                    response = self.login()
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data['result']['roles'], [role])
                    self.assertEqual(response.data['result']['realName'], name)
        self.assertEqual(self.account_snapshot(), before)
        self.user.refresh_from_db()
        admin.refresh_from_db()
        self.assertTrue(self.user.check_password('existing-password'))
        self.assertTrue(admin.check_password('admin-password'))

    @override_settings(PORTAL_AUTO_CREATE_USERS=True)
    @patch(VALIDATE)
    def test_auto_create_cannot_reactivate_inactive_users_or_repair_their_roles(self, validate):
        inactive = get_user_model().objects.create_user(
            username='disabled-with-profile', password='keep-disabled-password', is_active=False,
        )
        AccountProfile.objects.create(user=inactive, role=AccountProfile.Role.DEVELOPER)
        get_user_model().objects.create_user(username='disabled-no-profile', is_active=False)
        before = self.account_snapshot()
        with self.compatible_queries():
            for username in ['disabled-with-profile', 'disabled-no-profile']:
                with self.subTest(username=username):
                    validate.return_value = {**DETAIL, 'username': username}
                    self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.account_snapshot(), before)

    @override_settings(PORTAL_AUTO_CREATE_USERS=True)
    @patch(VALIDATE)
    def test_auto_create_rejects_portal_disabled_or_expired_users_before_any_insert(self, validate):
        before = self.account_snapshot()
        with self.compatible_queries():
            for username in [self.user.username, 'unknown-invalid-user']:
                for changes in [
                    {'status': 2}, {'expired': int(time.time()) - 10},
                    {'expired': int((time.time() - 10) * 1000)},
                    {'expired': None}, {'expired': True}, {'expired': -2},
                ]:
                    with self.subTest(username=username, changes=changes):
                        validate.return_value = {**DETAIL, 'username': username, **changes}
                        self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.account_snapshot(), before)

    @override_settings(PORTAL_AUTO_CREATE_USERS=True)
    @patch(VALIDATE, side_effect=PortalProtocolError('无效票据'))
    def test_auto_create_does_not_provision_any_account_when_ticket_validation_fails(self, validate):
        before = self.account_snapshot()
        with self.compatible_queries():
            self.assertEqual(self.login().status_code, 401)
        validate.assert_called_once_with('ST-existing', 'existing-app')
        self.assertEqual(self.account_snapshot(), before)

    @override_settings(PORTAL_AUTO_CREATE_USERS=True)
    @patch('requests.Session.get')
    def test_auto_create_does_not_provision_for_another_app_id(self, portal_get):
        before = self.account_snapshot()
        with self.compatible_queries():
            self.assertEqual(self.login(appid='another-app').status_code, 401)
        portal_get.assert_not_called()
        self.assertEqual(self.account_snapshot(), before)

    @override_settings(PORTAL_AUTO_CREATE_USERS=True)
    @patch(VALIDATE)
    def test_auto_create_validates_empty_and_oversized_usernames_before_database_writes(self, validate):
        max_length = get_user_model()._meta.get_field('username').max_length
        before = self.account_snapshot()
        with self.compatible_queries():
            for username in ['', ' \t\n ', 'x' * (max_length + 1)]:
                with self.subTest(username=username):
                    validate.return_value = {**DETAIL, 'username': username}
                    self.assertIn(self.login().status_code, (400, 401, 403))
        self.assertEqual(self.account_snapshot(), before)

    @override_settings(PORTAL_AUTO_CREATE_USERS=True)
    @patch(VALIDATE)
    def test_auto_create_rejects_username_whitespace_without_creating_or_aliasing_accounts(self, validate):
        before = self.account_snapshot()
        with self.compatible_queries():
            for username in ['  unknown-portal-user\t ', f' {self.user.username}\t']:
                with self.subTest(username=username):
                    validate.return_value = {**DETAIL, 'username': username}
                    self.assertEqual(self.login().status_code, 403)
                    self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.account_snapshot(), before)
        self.assertEqual(validate.call_count, 4)

    @override_settings(PORTAL_AUTO_CREATE_USERS=True)
    @patch(VALIDATE)
    def test_auto_create_rejects_case_insensitive_database_alias_without_changing_existing_account(self, validate):
        username = self.user.username.upper()
        validate.return_value = {**DETAIL, 'username': username}
        before = self.account_snapshot()
        original_get = QuerySet.get

        def get_with_case_insensitive_username(queryset, *args, **kwargs):
            if queryset.model is get_user_model() and kwargs.get('username') == username:
                return self.user
            return original_get(queryset, *args, **kwargs)

        with patch.object(QuerySet, 'get', get_with_case_insensitive_username):
            with self.compatible_queries():
                self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.account_snapshot(), before)

    @patch(VALIDATE)
    @patch('portal_integration.sso.AccountProfile.objects.select_related')
    def test_case_insensitive_database_match_cannot_alias_another_exact_username(self, profiles, validate):
        # MySQL's common case-insensitive collations can return this profile
        # for a differently cased or space-padded username. Verify Python-level
        # identity equality even though SQLite would not reproduce that lookup.
        profiles.return_value.get.return_value = self.profile
        before = self.account_snapshot()
        with self.compatible_queries():
            for username in [self.user.username.upper(), f'{self.user.username} ']:
                with self.subTest(username=username):
                    validate.return_value = {**DETAIL, 'username': username}
                    self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.account_snapshot(), before)

    @patch(VALIDATE)
    def test_inactive_or_unconfigured_local_user_is_denied_without_repairs(self, validate):
        inactive = get_user_model().objects.create_user(username='inactive', is_active=False)
        AccountProfile.objects.create(user=inactive)
        get_user_model().objects.create_user(username='no-profile')
        before = self.account_snapshot()
        with self.compatible_queries():
            for username in ['inactive', 'no-profile']:
                with self.subTest(username=username):
                    validate.return_value = {**DETAIL, 'username': username}
                    self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.account_snapshot(), before)

    @patch(VALIDATE)
    def test_portal_disabled_expired_or_invalid_expiry_cannot_login(self, validate):
        before = self.account_snapshot()
        with self.compatible_queries():
            for changes in [
                {'status': 2}, {'expired': int(time.time()) - 5},
                {'expired': int((time.time() - 5) * 1000)},
                {'expired': None}, {'expired': True}, {'expired': -2},
            ]:
                with self.subTest(changes=changes):
                    validate.return_value = {**DETAIL, **changes}
                    self.assertEqual(self.login().status_code, 403)
        self.assertEqual(self.account_snapshot(), before)

    @patch(VALIDATE)
    def test_issued_portal_token_stops_working_at_verified_portal_expiry(self, validate):
        now = int(time.time())
        validate.return_value = {**DETAIL, 'expired': now + 60}
        with self.compatible_queries():
            response = self.login()
            self.assertEqual(response.status_code, 200)
            self.client.credentials(
                HTTP_AUTHORIZATION=f"Bearer {response.data['result']['accessToken']}",
            )
            self.assertEqual(self.client.get('/api/user/info').status_code, 200)
            with patch('accounts.auth.time.time', return_value=now + 120):
                self.assertEqual(self.client.get('/api/user/info').status_code, 401)

    @patch(VALIDATE, return_value=DETAIL)
    def test_backend_callbacks_redirect_to_spa_then_consume_ticket_only_once(self, validate):
        callback = f'{FRONTEND}/#/task/manage/execution?search=a%26b'
        before = self.account_snapshot()
        with self.compatible_queries():
            for endpoint in ['/api/sso/login', '/api/portal/sso/callback']:
                with self.subTest(endpoint=endpoint):
                    response = self.client.get(endpoint, {
                        'ticket': 'ST-existing', 'appid': 'existing-app', 'callback': callback,
                    })
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response.url.startswith(f'{FRONTEND}/#/auth/sso?'))
                    self.assertNotIn('accessToken', response.url)
                    self.assertEqual(response['Cache-Control'], 'no-store')
                    self.assertEqual(response['Referrer-Policy'], 'no-referrer')
                    params = parse_qs(urlsplit(response.url).fragment.split('?', 1)[1])
                    self.assertEqual(params['callback'], [callback])
                    self.assertEqual(params['ticket'], ['ST-existing'])
            validate.assert_not_called()
            response = self.login(callback=callback)
            self.assertEqual(response.status_code, 200)
        validate.assert_called_once_with('ST-existing', 'existing-app')
        self.assertEqual(self.account_snapshot(), before)

    @patch(VALIDATE)
    def test_backend_callback_rejects_wrong_app_and_unsafe_destinations_before_validation(self, validate):
        with self.compatible_queries():
            for endpoint in ['/api/sso/login', '/api/portal/sso/callback']:
                response = self.client.get(endpoint, {
                    'ticket': 'ST-existing', 'appid': 'different-app',
                })
                self.assertEqual(response.status_code, 401)
                for callback in [
                    'https://other.example.test/#/task', '//other.example.test',
                    'http://10.130.76.47:8088/yibao/#/task',
                    'https://10.130.76.47:8080/yibao/#/task',
                    'javascript:alert(1)',
                ]:
                    with self.subTest(endpoint=endpoint, callback=callback):
                        response = self.client.get(endpoint, {
                            'ticket': 'ST-existing', 'appid': 'existing-app', 'callback': callback,
                        })
                        self.assertEqual(response.status_code, 401)
        validate.assert_not_called()

    @patch('requests.Session.get')
    def test_wrong_app_post_is_rejected_without_any_portal_network_call(self, portal_get):
        before = self.account_snapshot()
        with self.compatible_queries():
            self.assertEqual(self.login(appid='different-app').status_code, 401)
        portal_get.assert_not_called()
        self.assertEqual(self.account_snapshot(), before)

    def test_database_exchange_codes_and_user_sync_actions_are_explicitly_disabled(self):
        before = self.account_snapshot()
        with self.compatible_queries():
            response = self.client.post('/api/sso/login', {'code': 'old-db-code'}, format='json')
            self.assertEqual(response.status_code, 401)
            for action in [
                'app-admin-set', 'query-user-status', 'remove-user', 'disable-user',
                'enable-user', 'default-role', 'create-user', 'edit-user',
            ]:
                with self.subTest(action=action):
                    response = self.client.post(
                        f'/api/portal/actions/{action}', {'user_id': DETAIL['id']}, format='json',
                    )
                    self.assertEqual(response.status_code, 409)
        self.assertEqual(self.account_snapshot(), before)

    def test_rule_create_edit_and_disable_work_without_the_soft_delete_column(self):
        self.authenticate_business_requests()
        before = self.account_snapshot()
        with self.compatible_queries(allow_rule_writes=True):
            response = self.client.post('/api/rules/', {
                'ruleId': 'new-rule', 'drugName': '新药品', 'description': '新增规则',
                'enabled': True, 'type': '重复收费',
                'logicExpression': 'keep-this-expression',
                'rule_code': 'def execute_rule(record, item):\n    return []',
            }, format='json')
            self.assertEqual(response.status_code, 201)
            pk = response.data['id']
            response = self.client.patch(
                f'/api/rules/{pk}/', {'description': '仅修改描述'}, format='json',
            )
            self.assertEqual(response.status_code, 200)
            rule = Rule.objects.get(pk=pk)
            self.assertEqual(rule.rule_id, 'new-rule')
            self.assertTrue(rule.status)
            self.assertEqual(rule.logic_expression, 'keep-this-expression')
            response = self.client.patch(f'/api/rules/{pk}/', {'enabled': False}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertFalse(Rule.objects.get(pk=pk).status)
        self.assertEqual(self.account_snapshot(), before)

    def test_rule_import_upsert_uses_only_existing_columns(self):
        self.authenticate_business_requests()
        with self.compatible_queries(allow_rule_writes=True):
            for description in ['首次入库', '更新已有规则']:
                response = self.client.post('/api/rules/agenta/import/', {
                    'rule_id': 'upserted-rule', 'drug_name': '收费项目',
                    'description': description, 'type': '重复收费', 'status': True,
                    'rule_code': 'def execute_rule(record, item):\n    return []',
                }, format='json')
                self.assertEqual(response.status_code, 200)
            self.assertEqual(Rule.objects.filter(rule_id='upserted-rule').count(), 1)
            self.assertEqual(Rule.objects.get(rule_id='upserted-rule').description, '更新已有规则')

    def test_rule_delete_returns_conflict_and_preserves_enabled_rule_and_history(self):
        self.authenticate_business_requests()
        before = list(Rule.objects.filter(pk=self.rule.pk).values())
        with self.compatible_queries():
            response = self.client.delete(f'/api/rules/{self.rule.pk}/')
            self.assertEqual(response.status_code, 409)
            self.assertEqual(list(Rule.objects.filter(pk=self.rule.pk).values()), before)
            self.assertTrue(Result.objects.filter(pk=self.result.pk, rule_id=self.rule.pk).exists())
