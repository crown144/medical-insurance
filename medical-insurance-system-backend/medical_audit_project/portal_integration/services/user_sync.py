from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import AccountProfile
from portal_integration.models import PortalUserBinding

from .exceptions import PortalClientError, PortalMappingConflictError, PortalUserNotFoundError
from .portal_client import PortalClient


def _first_value(data, *keys):
    for key in keys:
        value = data.get(key)
        if value not in (None, ''):
            return value
    return None


def _normalise_expired_at(value):
    if value in (None, ''):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise PortalClientError('门户用户过期时间必须是整数时间戳或 -1。')
    try:
        timestamp = int(value)
    except (TypeError, ValueError) as exc:
        raise PortalClientError('门户用户过期时间格式无效。') from exc
    if not -1 <= timestamp <= 2 ** 63 - 1:
        raise PortalClientError('门户用户过期时间超出有效范围。')
    return timestamp


def _safe_profile_data(detail):
    allowed_keys = {
        'user_id', 'id', 'uuid', 'username', 'account', 'login_name', 'user_name',
        'fullname', 'real_name', 'name', 'display_name', 'nickname', 'email', 'email_address',
        'mobile', 'phone', 'telephone', 'organization', 'organization_id', 'org_id',
        'department', 'department_id', 'status', 'expired_at', 'expire_time',
        'expiration_time', 'expired', 'organization_code', 'organization_name',
        'create_time', 'update_time',
    }
    return {key: value for key, value in detail.items() if key in allowed_keys}


class PortalUserSyncService:
    def __init__(self, *, client=None):
        self.client = client or PortalClient()

    def ensure_binding(self, portal_user_id):
        binding = PortalUserBinding.objects.select_related('user').filter(
            portal_user_id=portal_user_id,
        ).first()
        if binding:
            return binding

        detail = self.client.get_user_detail(portal_user_id)
        return self.sync_detail(detail, expected_id=portal_user_id)

    def sync_detail(self, detail, *, expected_id=None):
        """Apply a verified detail response or a create/edit callback atomically.

        The immutable portal ID selects an existing binding even when its login
        name changes. Profile edits must not restore application access removed
        or disabled by a separate permission action.
        """
        portal_user_id = str(_first_value(detail, 'id', 'user_id', 'uuid') or expected_id or '').strip()
        if not portal_user_id or len(portal_user_id) > 128:
            raise PortalClientError('门户用户 ID 缺失或超出长度限制。')
        returned_id = str(_first_value(detail, 'user_id', 'id', 'uuid') or portal_user_id).strip()
        if expected_id is not None and returned_id != expected_id:
            raise PortalMappingConflictError('门户返回的用户 ID 与请求不一致。')

        username = str(_first_value(detail, 'username', 'account', 'login_name', 'user_name') or '').strip()
        if not username:
            raise PortalUserNotFoundError('门户用户缺少可用的登录账号。')

        User = get_user_model()
        if len(username) > User._meta.get_field(User.USERNAME_FIELD).max_length:
            raise PortalClientError('门户用户登录账号超过本地账号长度限制。')
        expired_at = _normalise_expired_at(
            _first_value(detail, 'expired', 'expired_at', 'expire_time', 'expiration_time')
        )
        status = detail.get('status', 1)
        if type(status) is not int or status not in (1, 2):
            raise PortalClientError('门户用户状态须为 1 或 2。')
        try:
            with transaction.atomic():
                existing_binding = PortalUserBinding.objects.select_for_update().filter(
                    portal_user_id=portal_user_id,
                ).first()
                if existing_binding:
                    user = User.objects.select_for_update().get(pk=existing_binding.user_id)
                    if User.objects.filter(username=username).exclude(pk=user.pk).exists():
                        raise PortalMappingConflictError('新的门户登录名已被其他本地账号占用。')
                    user.username = username
                else:
                    user = User.objects.select_for_update().filter(username=username).first()
                if user and PortalUserBinding.objects.filter(user=user).exclude(
                    portal_user_id=portal_user_id,
                ).exists():
                    raise PortalMappingConflictError('本地账号已绑定其他门户用户。')

                created = user is None
                if created:
                    user = User(username=username)
                    user.set_unusable_password()

                full_name = str(_first_value(detail, 'fullname', 'real_name', 'name', 'display_name', 'nickname') or '').strip()
                email = str(_first_value(detail, 'email', 'email_address') or '').strip()
                if full_name or 'fullname' in detail:
                    user.first_name = full_name[:150]
                    user.last_name = ''
                if email or 'email' in detail:
                    user.email = email[:254]
                user.is_active = status == 1 and (
                    not existing_binding
                    or existing_binding.access_status == PortalUserBinding.AccessStatus.ENABLED
                )
                user.save()

                profile, _ = AccountProfile.objects.get_or_create(
                    user=user,
                    defaults={'role': AccountProfile.Role.NORMAL},
                )
                if existing_binding:
                    existing_binding.portal_expired_at = expired_at
                    existing_binding.profile_data = _safe_profile_data(detail)
                    existing_binding.last_synced_at = timezone.now()
                    existing_binding.save(update_fields=['portal_expired_at', 'profile_data', 'last_synced_at', 'updated_at'])
                    return existing_binding
                binding = PortalUserBinding.objects.create(
                    portal_user_id=portal_user_id,
                    user=user,
                    access_status=PortalUserBinding.AccessStatus.ENABLED,
                    is_admin=profile.role == AccountProfile.Role.ADMIN,
                    portal_expired_at=expired_at,
                    profile_data=_safe_profile_data(detail),
                    last_synced_at=timezone.now(),
                )
                return binding
        except IntegrityError as exc:
            # A concurrent insert/rename may have won a unique constraint, but
            # the presence of a binding does not mean this update was applied.
            # Return an HTTP failure so the documented portal retry can recheck.
            raise PortalMappingConflictError('门户用户与本地账号并发映射冲突，请重试。', http_status=503) from exc
