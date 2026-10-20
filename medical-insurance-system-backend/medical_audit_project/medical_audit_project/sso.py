"""Legacy SSO logout configuration; all login identities use portal_integration."""

from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from django.conf import settings

from portal_integration.services.exceptions import PortalClientError, PortalProtocolError


def _http_url(value):
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise PortalClientError('门户退出地址配置无效。') from exc
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password:
        raise PortalClientError('请配置完整的门户退出地址。')
    return parsed


def logout_config():
    logout_url = settings.SSO_CAS_LOGOUT_URL.strip()
    # jicheng's portal identifies the application by its registered login
    # callback even during logout. Other deployments can override that service.
    service = settings.SSO_LOGOUT_SERVICE_URL.strip() or settings.PORTAL_LOGIN_CALLBACK_URL.strip()
    logout_callback = settings.SSO_LOGOUT_CALLBACK_URL.strip()
    home = settings.SSO_PORTAL_HOME_URL.strip()
    if not all((logout_url, service, logout_callback, home, settings.PORTAL_APP_ID, settings.PORTAL_FRONTEND_URL)):
        return {'logoutUrl': '', 'portalHomeUrl': ''}
    logout = _http_url(logout_url)
    _http_url(service)
    if logout.fragment or _http_url(logout_callback).fragment:
        raise PortalClientError('门户退出服务和后端退出回调地址不能包含片段。')
    _http_url(home)
    query = [(key, value) for key, value in parse_qsl(logout.query, keep_blank_values=True) if key not in ('service', 'callback')]
    query.extend([('service', service), ('callback', home)])
    return {
        'logoutUrl': urlunsplit((logout.scheme, logout.netloc, logout.path, urlencode(query), '')),
        'portalHomeUrl': home,
    }


def validate_logout_callback(appid, callback):
    if not settings.PORTAL_APP_ID or appid != settings.PORTAL_APP_ID:
        raise PortalProtocolError('appid 校验失败')
    config = logout_config()
    expected = config['portalHomeUrl']
    if not expected or not callback or unquote(callback) != unquote(expected):
        raise PortalProtocolError('callback 地址与门户首页配置不一致')
    # Redirect to the configured URL, never to a differently encoded input.
    return expected
