"""Provision portal users using only the original local account tables."""
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction

from accounts.models import AccountProfile
from .exceptions import PortalClientError, PortalProtocolError


def local_account_for_portal(detail):
    # Caller must validate the portal ticket, account status and expiry first.
    User = get_user_model()
    username = detail.get('username')
    field = User._meta.get_field('username')
    if not isinstance(username, str) or not username or username != username.strip():
        raise PortalProtocolError('门户登录名为空或包含首尾空白，请核对账号。', http_status=403)
    try:
        field.clean(username, None)
    except ValidationError as exc:
        raise PortalProtocolError('门户登录名格式或长度无效。', http_status=403) from exc
    fullname = detail.get('fullname')
    fullname = fullname if isinstance(fullname, str) else ''
    try:
        with transaction.atomic():
            user, _ = User.objects.select_for_update().get_or_create(
                username=username,
                defaults={
                    'password': make_password(None),
                    'first_name': fullname[:User._meta.get_field('first_name').max_length],
                    'is_active': True, 'is_staff': False, 'is_superuser': False,
                },
            )
            # MySQL collations can match a different case or trailing spaces.
            if user.username != username:
                raise PortalProtocolError('门户登录名与本地账号不完全一致，请核对账号映射。', http_status=403)
            if not user.is_active:
                raise PortalProtocolError('本地账号已停用，请联系管理员。', http_status=403)
            AccountProfile.objects.get_or_create(
                user=user, defaults={'role': AccountProfile.Role.NORMAL},
            )
            return user
    except DatabaseError as exc:
        raise PortalClientError('本地账号开通失败，请联系管理员检查用户表后重试。') from exc
