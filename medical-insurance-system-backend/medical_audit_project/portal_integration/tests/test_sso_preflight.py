from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from .test_document_contract import DOCUMENT_KEYS


@override_settings(
    DEBUG=False, SECRET_KEY='isolated-test-key', ALLOWED_HOSTS=['insurance.example.test'],
    PORTAL_BASE_URL='https://portal.example.test', PORTAL_APP_ID='app-1',
    PORTAL_FRONTEND_URL='https://insurance.example.test/yibao',
    PORTAL_LOGIN_CALLBACK_URL='https://insurance.example.test/api/sso/login',
    PORTAL_CAS_LOGIN_URL='https://portal.example.test/cas/login',
    PORTAL_SSO_VALIDATE_PATH='/api/security-manage-permission/app/cas/serviceValidate',
    PORTAL_USER_DETAIL_PATH='/api/security-manage-permission/v1/user/info',
    PORTAL_ENCRYPT_ENABLED=False, PORTAL_PUBLIC_KEY='', PORTAL_APP_PUBLIC_KEY='', PORTAL_APP_PRIVATE_KEY='',
)
class SsoPreflightTests(SimpleTestCase):
    def check(self, *args):
        output = StringIO()
        call_command('check_portal_sso', *args, stdout=output, stderr=output, no_color=True)
        return output.getvalue()

    def test_default_check_never_contacts_database_or_portal(self):
        with patch('django.db.migrations.executor.MigrationExecutor') as database, patch('requests.Session.request') as network:
            output = self.check()
        database.assert_not_called()
        network.assert_not_called()
        self.assertIn('本地配置检查通过', output)
        self.assertIn('缺少 expired', output)
        self.assertIn('未检查数据库迁移', output)

    @override_settings(PORTAL_CAS_LOGIN_URL='')
    def test_plain_portal_card_requires_cas_but_ticket_callback_mode_does_not(self):
        with self.assertRaisesMessage(CommandError, '缺少 PORTAL_CAS_LOGIN_URL'):
            self.check()
        self.assertIn('本地配置检查通过', self.check('--ticket-callback-only'))

    def test_missing_login_identity_and_invalid_urls_are_rejected(self):
        invalid_settings = [
            {'PORTAL_BASE_URL': ''}, {'PORTAL_APP_ID': ''},
            {'PORTAL_FRONTEND_URL': 'https://insurance.example.test/#/task/execution'},
            {'PORTAL_CAS_LOGIN_URL': 'https://portal.example.test/#/home'},
            {'PORTAL_LOGIN_CALLBACK_URL': 'javascript:alert(1)'},
            {'PORTAL_BASE_URL': 'https://portal.example.test:invalid'},
            {'PORTAL_SSO_VALIDATE_PATH': 'https://portal.example.test/validate'},
        ]
        for invalid in invalid_settings:
            with self.subTest(setting=next(iter(invalid))), override_settings(**invalid):
                with self.assertRaisesMessage(CommandError, next(iter(invalid))):
                    self.check()

    def test_django_host_matching_and_frontend_login_callback_are_supported(self):
        with override_settings(ALLOWED_HOSTS=['.example.test'], PORTAL_LOGIN_CALLBACK_URL='https://insurance.example.test/yibao/#/oauth/login'):
            self.assertIn('本地配置检查通过', self.check())
        with override_settings(ALLOWED_HOSTS=['portal.example.test']):
            with self.assertRaisesMessage(CommandError, 'ALLOWED_HOSTS 不允许 PORTAL_FRONTEND_URL'):
                self.check()

    def test_missing_access_middleware_or_apps_fail(self):
        without_access = [item for item in settings.MIDDLEWARE if item != 'accounts.middleware.ApiAccessMiddleware']
        with override_settings(MIDDLEWARE=without_access), self.assertRaisesMessage(CommandError, 'MIDDLEWARE 缺少'):
            self.check()
        with patch('portal_integration.management.commands.check_portal_sso.apps.is_installed', return_value=False):
            with self.assertRaisesMessage(CommandError, 'INSTALLED_APPS 缺少 accounts'):
                self.check()

    @override_settings(PORTAL_ENCRYPT_ENABLED=True)
    def test_missing_keys_block_encrypted_permission_callbacks(self):
        with self.assertRaisesMessage(CommandError, 'PORTAL_APP_PRIVATE_KEY'):
            self.check()

    @override_settings(**DOCUMENT_KEYS, PORTAL_ENCRYPT_ENABLED=True)
    def test_real_crypto_configuration_validates_offline(self):
        output = self.check()
        self.assertIn('本地配置检查通过', output)
        for key in DOCUMENT_KEYS.values():
            self.assertNotIn(key, output)

    def test_malformed_key_or_url_cannot_leak_secret_values(self):
        secret = 'never-output-this-secret-value'
        for invalid in [
            {**DOCUMENT_KEYS, 'PORTAL_APP_PRIVATE_KEY': secret},
            {'PORTAL_BASE_URL': f'https://user:{secret}@portal.example.test'},
        ]:
            output = StringIO()
            with self.subTest(invalid=list(invalid)), override_settings(**invalid), self.assertRaises(CommandError) as raised:
                call_command('check_portal_sso', stdout=output, no_color=True)
            self.assertNotIn(secret, output.getvalue() + str(raised.exception))

    @patch('django.db.migrations.executor.MigrationExecutor')
    def test_database_option_reports_pending_migrations_without_applying_them(self, executor_class):
        executor = executor_class.return_value
        executor.loader.graph.leaf_nodes.return_value = [
            ('accounts', '0001_initial'), ('portal_integration', '0003_portallogincode'), ('tasks', '0001_initial'),
        ]
        executor.migration_plan.return_value = [(SimpleNamespace(app_label='portal_integration', name='0003_portallogincode'), False)]
        with self.assertRaisesMessage(CommandError, 'portal_integration.0003_portallogincode'):
            self.check('--database')
        executor.migrate.assert_not_called()
        executor.migration_plan.assert_called_once_with([
            ('accounts', '0001_initial'), ('portal_integration', '0003_portallogincode'),
        ])
        executor.migration_plan.return_value = []
        self.assertIn('本地配置检查通过', self.check('--database'))

    @patch('django.db.migrations.executor.MigrationExecutor', side_effect=RuntimeError('database-password-must-not-leak'))
    def test_database_connection_error_is_sanitized(self, _executor_class):
        with self.assertRaisesMessage(CommandError, '无法检查数据库迁移') as raised:
            self.check('--database')
        self.assertNotIn('database-password-must-not-leak', str(raised.exception))

    @override_settings(PORTAL_AUTH_MODE='existing', LEGACY_DATABASE_COMPATIBILITY=True)
    @patch('django.db.migrations.executor.MigrationExecutor')
    def test_existing_mode_accepts_an_already_upgraded_database_without_downgrade(self, executor_class):
        executor = executor_class.return_value
        executor.migration_plan.return_value = [
            (SimpleNamespace(app_label='accounts', name='0002_alter_accountprofile_role'), True),
            (SimpleNamespace(app_label='rules', name='0006_rule_is_deleted'), True),
        ]
        self.assertIn('本地配置检查通过', self.check('--database'))
        executor.migrate.assert_not_called()
