from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import transaction

from accounts.models import AccountProfile


SSO_HANDOFF_SALT = 'medical-audit.sso.handoff'


class SSOError(Exception):
    pass


@dataclass
class PortalUser:
    username: str
    fullname: str
    raw: dict[str, Any]


def _configured_hosts() -> set[str]:
    hosts = set(getattr(settings, 'SSO_ALLOWED_CALLBACK_HOSTS', []))
    app_base_url = getattr(settings, 'SSO_APP_BASE_URL', '')
    if app_base_url:
        parsed = urlparse(app_base_url)
        if parsed.hostname:
            hosts.add(parsed.hostname)
    return {host.lower() for host in hosts if host}


def validate_app_callback(callback: str) -> str:
    if not callback:
        raise SSOError('缺少 callback 参数')
    parsed = urlparse(callback)
    if parsed.scheme not in {'http', 'https'}:
        raise SSOError('callback 协议不合法')
    if not parsed.hostname or parsed.hostname.lower() not in _configured_hosts():
        raise SSOError('callback 地址不在允许范围内')
    return callback


def validate_portal_callback(callback: str) -> str:
    if not callback:
        raise SSOError('缺少 callback 参数')
    expected = getattr(settings, 'SSO_PORTAL_HOME_URL', '').strip()
    if callback != expected and unquote(callback) != unquote(expected):
        raise SSOError('callback 地址与门户首页配置不一致')
    return callback


def validate_appid(appid: str) -> str:
    expected = getattr(settings, 'SSO_APP_ID', '').strip()
    if not appid:
        raise SSOError('缺少 appid 参数')
    if not expected or appid != expected:
        raise SSOError('appid 校验失败')
    return appid


def build_frontend_url(path: str, query: dict[str, Any] | None = None) -> str:
    base_url = getattr(settings, 'SSO_APP_BASE_URL', '').rstrip('/')
    if not base_url:
        raise SSOError('未配置 SSO_APP_BASE_URL')
    target = urljoin(f'{base_url}/', path.lstrip('/'))
    if not query:
        return target
    return f'{target}?{urlencode(query)}'


def sanitize_service_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))


def build_logout_redirect_url() -> str:
    logout_url = getattr(settings, 'SSO_CAS_LOGOUT_URL', '').strip()
    login_callback = getattr(settings, 'SSO_LOGIN_CALLBACK_URL', '').strip()
    portal_home = getattr(settings, 'SSO_PORTAL_HOME_URL', '').strip()
    if not logout_url or not login_callback or not portal_home:
        raise SSOError('SSO 登出配置不完整')
    return f'{logout_url}?{urlencode({"service": login_callback, "callback": portal_home})}'


def call_service_validate(ticket: str, appid: str) -> PortalUser:
    service_validate_url = getattr(settings, 'SSO_SERVICE_VALIDATE_URL', '').strip()
    if not service_validate_url:
        raise SSOError('未配置 SSO_SERVICE_VALIDATE_URL')
    query = urlencode({'ticket': ticket, 'appid': appid})
    request = Request(
        f'{service_validate_url}?{query}',
        headers={'Content-Type': 'application/json'},
        method='GET',
    )
    timeout = int(getattr(settings, 'SSO_HTTP_TIMEOUT_SECONDS', 10))
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        raise SSOError(f'ServiceValidate 请求失败: HTTP {exc.code}') from exc
    except URLError as exc:
        raise SSOError('ServiceValidate 请求失败: 网络错误') from exc
    except (OSError, ValueError) as exc:
        raise SSOError('ServiceValidate 响应解析失败') from exc

    if payload.get('code') != 0:
        raise SSOError(payload.get('message') or 'ServiceValidate 返回失败')
    data = payload.get('data') or {}
    username = str(data.get('username') or '').strip()
    if not username:
        raise SSOError('ServiceValidate 未返回 username')
    status = data.get('status')
    if status not in (None, 1):
        raise SSOError('门户用户状态不可登录')
    return PortalUser(
        username=username,
        fullname=str(data.get('fullname') or '').strip(),
        raw=data,
    )
# def call_service_validate(ticket: str, appid: str) -> PortalUser:
#     return PortalUser(
#         username='test_user',
#         fullname='测试用户',
#         raw={
#             'id': 'test-id',
#             'username': 'test_user',
#             'fullname': '测试用户',
#             'status': 1,
#         },
#     )
def resolve_local_profile(username: str) -> AccountProfile:
    user_model = get_user_model()
    try:
        user = user_model.objects.get(username=username, is_active=True)
    except user_model.DoesNotExist as exc:
        raise SSOError('本系统不存在该用户或用户已停用') from exc
    try:
        return AccountProfile.objects.select_related('user').get(user=user)
    except AccountProfile.DoesNotExist as exc:
        raise SSOError('该用户未开通本系统账号角色') from exc


def build_handoff_token(profile: AccountProfile, callback: str) -> str:
    return signing.dumps(
        {
            'user_id': profile.user_id,
            'callback': callback,
        },
        salt=SSO_HANDOFF_SALT,
        compress=True,
    )


def load_handoff_token(token: str) -> dict[str, Any]:
    try:
        payload = signing.loads(
            token,
            salt=SSO_HANDOFF_SALT,
            max_age=int(getattr(settings, 'SSO_HANDOFF_TOKEN_MAX_AGE', 60)),
        )
    except signing.BadSignature as exc:
        raise SSOError('SSO 临时凭证无效或已过期') from exc
    if not isinstance(payload, dict):
        raise SSOError('SSO 临时凭证格式不正确')
    callback = str(payload.get('callback') or '').strip()
    validate_app_callback(callback)
    return payload
