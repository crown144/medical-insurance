import logging

import requests
from django.conf import settings

from .exceptions import PortalClientError, PortalProtocolError, PortalUserNotFoundError


logger = logging.getLogger(__name__)


class PortalClient:
    """Small client for portal API 3.7.1.

    The user-detail URL is configurable because portal deployments may expose a
    different gateway prefix. No secret or full response body is logged.
    """

    def __init__(self, *, session=None):
        self.session = session or requests.Session()
        self.base_url = str(getattr(settings, 'PORTAL_BASE_URL', '')).rstrip('/')
        self.app_id = str(getattr(settings, 'PORTAL_APP_ID', '')).strip()
        self.user_detail_path = str(
            getattr(
                settings,
                'PORTAL_USER_DETAIL_PATH',
                '/api/security-manage-permission/v1/user/info',
            )
        )
        self.timeout = float(getattr(settings, 'PORTAL_REQUEST_TIMEOUT_SECONDS', 10))

    def validate_ticket(self, ticket, app_id):
        """Exchange a CAS ticket on the server; never accept browser-supplied identities."""
        if not self.base_url or not self.app_id:
            raise PortalClientError('未配置门户地址或应用 ID。')
        if app_id != self.app_id:
            raise PortalProtocolError('门户应用 ID 不匹配。')
        path = settings.PORTAL_SSO_VALIDATE_PATH
        try:
            response = self.session.get(
                f'{self.base_url}/{path.lstrip("/")}',
                params={'ticket': ticket, 'appid': self.app_id},
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout,
                allow_redirects=False,
            )
            if response.status_code in (401, 403):
                raise PortalProtocolError('门户登录凭据无效或已过期，请从门户重新进入。')
            if response.status_code != 200:
                raise PortalClientError('门户登录校验服务暂不可用。')
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PortalClientError('连接门户登录校验服务失败。') from exc
        if not isinstance(payload, dict) or type(payload.get('code')) is not int:
            raise PortalClientError('门户登录校验响应格式无效。')
        if payload['code'] != 0:
            raise PortalProtocolError('门户登录凭据无效或已过期，请从门户重新进入。')
        data = payload.get('data')
        # v1.9 §3.4 explicitly specifies plaintext, independently of action encryption.
        if not isinstance(data, dict):
            raise PortalClientError('门户未返回有效的登录用户。')
        if not isinstance(data.get('id'), str) or not data['id'].strip() or len(data['id']) > 128:
            raise PortalClientError('门户登录资料缺少有效的用户 ID。')
        if not isinstance(data.get('username'), str) or not data['username'].strip():
            raise PortalClientError('门户登录资料缺少有效的登录名。')
        if type(data.get('status')) is not int or data['status'] not in (1, 2):
            raise PortalClientError('门户登录资料的用户状态无效。')
        if 'expired' not in data:
            # The §3.4 field table defines expired, but its example omits it.
            # Fetch §3.7.1 rather than overwriting a binding's expiry with None.
            detail = self.get_user_detail(data['id'])
            if data['status'] == 2:
                detail = {**detail, 'status': 2}
            return detail
        if type(data.get('expired')) is not int or not -1 <= data['expired'] <= 2 ** 63 - 1:
            raise PortalClientError('门户登录资料缺少有效的账号有效期。')
        return data

    def get_user_detail(self, portal_user_id):
        if not self.base_url or not self.app_id:
            raise PortalClientError('未配置门户地址或应用 ID，无法补齐用户资料。')

        url = f'{self.base_url}/{self.user_detail_path.lstrip("/")}'
        try:
            response = self.session.post(
                url,
                json={'id': portal_user_id},
                headers={'appid': self.app_id, 'Content-Type': 'application/json'},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning('Portal user detail request failed for user fingerprint suffix=%s', portal_user_id[-8:])
            raise PortalClientError('查询门户用户详情失败。') from exc

        if not isinstance(payload, dict):
            raise PortalClientError('门户用户详情响应格式无效。')
        if type(payload.get('code')) is not int or payload['code'] != 0:
            if payload.get('code') in (404, '404', 40401, '40401'):
                raise PortalUserNotFoundError('门户用户不存在。')
            raise PortalClientError(str(payload.get('message') or '门户拒绝了用户详情查询。'))

        data = payload.get('data')
        # 3.7.1 always encrypts its response, independently of actions.encrypt.
        from .crypto import PortalCrypto

        if not isinstance(data, str):
            raise PortalClientError('门户用户详情响应缺少加密数据。')
        try:
            crypto = PortalCrypto()
            crypto.verify_portal_signature(data, response.headers.get('eywa-signature'))
            data = crypto.decrypt_json(data)
        except PortalProtocolError as exc:
            raise PortalClientError('门户用户详情验签或解密失败。') from exc
        if not isinstance(data, dict):
            raise PortalUserNotFoundError('门户未返回有效的用户资料。')
        if not isinstance(data.get('id'), str) or data['id'] != portal_user_id:
            raise PortalClientError('门户用户详情缺少匹配的用户 ID。')
        if not isinstance(data.get('username'), str) or not data['username'].strip():
            raise PortalClientError('门户用户详情缺少有效的登录名。')
        if (
            type(data.get('expired')) is not int or not -1 <= data['expired'] <= 2 ** 63 - 1
            or type(data.get('status')) is not int or data['status'] not in (1, 2)
        ):
            raise PortalClientError('门户用户详情的有效期或状态无效。')
        return data
