import logging

import requests
from django.conf import settings

from .exceptions import PortalClientError, PortalUserNotFoundError


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
                '/api/security-manage-permission/app/user/detail',
            )
        )
        self.timeout = float(getattr(settings, 'PORTAL_REQUEST_TIMEOUT_SECONDS', 10))

    def get_user_detail(self, portal_user_id):
        if not self.base_url or not self.app_id:
            raise PortalClientError('未配置门户地址或应用 ID，无法补齐用户资料。')

        url = f'{self.base_url}/{self.user_detail_path.lstrip("/")}'
        try:
            response = self.session.get(
                url,
                params={'user_id': portal_user_id, 'appid': self.app_id},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning('Portal user detail request failed for user fingerprint suffix=%s', portal_user_id[-8:])
            raise PortalClientError('查询门户用户详情失败。') from exc

        if not isinstance(payload, dict):
            raise PortalClientError('门户用户详情响应格式无效。')
        if payload.get('code') not in (None, 0, '0', 200, '200'):
            if payload.get('code') in (404, '404', 40401, '40401'):
                raise PortalUserNotFoundError('门户用户不存在。')
            raise PortalClientError(str(payload.get('message') or '门户拒绝了用户详情查询。'))

        data = payload.get('data', payload.get('result'))
        if bool(getattr(settings, 'PORTAL_ENCRYPT_ENABLED', False)) and isinstance(data, str):
            from .crypto import PortalCrypto

            crypto = PortalCrypto()
            crypto.verify_portal_signature(data, response.headers.get('eywa-signature'))
            data = crypto.decrypt_json(data)
        if isinstance(data, dict) and isinstance(data.get('user'), dict):
            data = data['user']
        if not isinstance(data, dict):
            raise PortalUserNotFoundError('门户未返回有效的用户资料。')
        return data
