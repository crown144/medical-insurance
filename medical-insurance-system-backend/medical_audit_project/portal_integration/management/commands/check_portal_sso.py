"""Check the loaded deployment settings without consuming a portal ticket."""
from urllib.parse import urlsplit

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.http.request import split_domain_port, validate_host

from portal_integration.services.crypto import PortalCrypto
from portal_integration.services.exceptions import PortalIntegrationError


class Command(BaseCommand):
    help = '检查实际加载的门户 SSO 设置；默认不连接网络或数据库，也不输出密钥。'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--ticket-callback-only', action='store_true', help='仅检查已携带 ticket 的回调，允许不配置 CAS 登录地址。')
        parser.add_argument('--database', action='store_true', help='只读检查默认数据库的账号和门户迁移是否全部应用。')

    def handle(self, *args, **options):
        errors, warnings = [], []
        mode = getattr(settings, 'PORTAL_AUTH_MODE', 'existing')
        if mode not in ('existing', 'synced'):
            errors.append('PORTAL_AUTH_MODE 必须为 existing 或 synced。')
        if mode == 'existing':
            warnings.append('已有账号登录模式：只读取同名有效本地账号；不自动创建用户，不使用门户绑定/交换码表，不支持权限同步回调。')
        parsed_urls = {}
        required_urls = ['PORTAL_BASE_URL', 'PORTAL_FRONTEND_URL', 'PORTAL_LOGIN_CALLBACK_URL']
        if not options['ticket_callback_only']:
            required_urls.append('PORTAL_CAS_LOGIN_URL')
        elif getattr(settings, 'PORTAL_CAS_LOGIN_URL', ''):
            required_urls.append('PORTAL_CAS_LOGIN_URL')
        for name in required_urls:
            value = str(getattr(settings, name, '')).strip()
            if not value:
                errors.append(f'缺少 {name}。')
                continue
            try:
                parsed = urlsplit(value)
                if (parsed.scheme not in ('http', 'https') or not parsed.hostname
                        or parsed.username or parsed.password or any(c.isspace() for c in value)):
                    raise ValueError()
                parsed.port  # Reject an invalid/out-of-range port before deployment.
                if name in ('PORTAL_BASE_URL', 'PORTAL_FRONTEND_URL') and (parsed.query or parsed.fragment):
                    raise ValueError()
                if name == 'PORTAL_CAS_LOGIN_URL' and parsed.fragment:
                    raise ValueError()
                parsed_urls[name] = parsed
            except ValueError:
                errors.append(f'{name} 必须是有效 HTTP(S) URL；基址不可含查询或片段，CAS 地址不可含片段。')
        app_id = str(getattr(settings, 'PORTAL_APP_ID', '')).strip()
        if not app_id or len(app_id) > 128:
            errors.append('PORTAL_APP_ID 缺失或超过 128 字符。')
        for name in ('PORTAL_SSO_VALIDATE_PATH', 'PORTAL_USER_DETAIL_PATH'):
            value = str(getattr(settings, name, '')).strip()
            try:
                parsed = urlsplit(value)
                if not value.startswith('/') or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
                    raise ValueError()
            except ValueError:
                errors.append(f'{name} 必须是以 / 开头的 API 路径，不是完整 URL。')
        for name in ('accounts', 'portal_integration'):
            if not apps.is_installed(name):
                errors.append(f'INSTALLED_APPS 缺少 {name}。')
        if 'accounts.middleware.ApiAccessMiddleware' not in settings.MIDDLEWARE:
            errors.append('MIDDLEWARE 缺少 accounts.middleware.ApiAccessMiddleware。')
        hosts = settings.ALLOWED_HOSTS
        if not hosts and settings.DEBUG:
            hosts = ['.localhost', '127.0.0.1', '[::1]']
        for name in ('PORTAL_FRONTEND_URL', 'PORTAL_LOGIN_CALLBACK_URL'):
            if name in parsed_urls:
                host, _port = split_domain_port(parsed_urls[name].netloc.lower())
                if not host or not validate_host(host, hosts):
                    errors.append(f'ALLOWED_HOSTS 不允许 {name} 的主机；设置 DJANGO_ALLOWED_HOSTS 或实际部署设置。')
        if settings.DEBUG:
            warnings.append('DEBUG=True；生产部署应关闭 DEBUG 并设置独立 DJANGO_SECRET_KEY。')
        elif not settings.SECRET_KEY or settings.SECRET_KEY.startswith('django-insecure-'):
            errors.append('生产环境缺少独立 DJANGO_SECRET_KEY，访问中间件会拒绝启动。')
        key_names = ('PORTAL_PUBLIC_KEY', 'PORTAL_APP_PUBLIC_KEY', 'PORTAL_APP_PRIVATE_KEY')
        encrypt_enabled = getattr(settings, 'PORTAL_ENCRYPT_ENABLED', False)
        missing_keys = [name for name in key_names if not str(getattr(settings, name, '')).strip()]
        if missing_keys:
            message = '缺少 SM2 配置：' + ', '.join(missing_keys) + '。'
            (errors if encrypt_enabled else warnings).append(message)
            warnings.append('ServiceValidate 响应若缺少 expired，需加密用户详情补查；缺少上述密钥时该登录无法完成。')
        else:
            try:
                PortalCrypto()
            except (PortalIntegrationError, ImportError, ValueError, TypeError):
                errors.append('SM2 密钥格式、应用公私钥配对或协议依赖校验失败；请检查密钥和 gmssl/pycryptodomex。')
        if not encrypt_enabled and mode == 'synced':
            warnings.append('门户权限回调加密未启用；生产用户权限同步需另行配置加密回调。')
        if options['database']:
            try:
                from django.db import connections
                from django.db.migrations.executor import MigrationExecutor

                executor = MigrationExecutor(connections['default'])
                executor.loader.check_consistent_history(connections['default'])
                if mode == 'existing':
                    targets = [('accounts', '0001_initial')]
                else:
                    targets = [node for node in executor.loader.graph.leaf_nodes() if node[0] in ('accounts', 'portal_integration')]
                if getattr(settings, 'LEGACY_DATABASE_COMPATIBILITY', True):
                    targets.append(('rules', '0005_remove_rule_rule_name_rule_drug_name'))
                else:
                    targets += [node for node in executor.loader.graph.leaf_nodes() if node[0] == 'rules']
                pending = [(migration, backwards) for migration, backwards in executor.migration_plan(targets) if not backwards]
                if pending:
                    errors.append('数据库存在未应用迁移：' + ', '.join(f'{migration.app_label}.{migration.name}' for migration, _ in pending) + '。')
            except Exception:
                errors.append('无法检查数据库迁移；请确认数据库连接及迁移历史。')
        else:
            warnings.append('未检查数据库迁移；使用 --database 只读检查当前模式所需的迁移，不会执行迁移。')
        self.stdout.write(f'实际设置模块：{settings.SETTINGS_MODULE}')
        self.stdout.write(f'门户账号模式：{mode}')
        for warning in warnings:
            self.stdout.write(self.style.WARNING(f'警告：{warning}'))
        if errors:
            raise CommandError('\n'.join(errors))
        self.stdout.write(self.style.SUCCESS('本地配置检查通过；未验证真实门户注册、网络连通性、ticket 或用户授权。'))
