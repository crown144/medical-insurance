from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import AccountProfile
from portal_integration.models import PortalUserBinding

from .exceptions import PortalMappingConflictError, PortalUserNotFoundError
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


def _safe_profile_data(detail):
    allowed_keys = {
        'user_id', 'id', 'uuid', 'username', 'account', 'login_name', 'user_name',
        'real_name', 'name', 'display_name', 'nickname', 'email', 'email_address',
        'mobile', 'phone', 'telephone', 'organization', 'organization_id', 'org_id',
        'department', 'department_id', 'status', 'expired_at', 'expire_time',
        'expiration_time',
    }
    return {key: value for key, value in detail.items() if key in allowed_keys}
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
        returned_id = str(_first_value(detail, 'user_id', 'id', 'uuid') or portal_user_id).strip()
        if returned_id != portal_user_id:
            raise PortalMappingConflictError('门户返回的用户 ID 与请求不一致。')

        username = str(_first_value(detail, 'username', 'account', 'login_name', 'user_name') or '').strip()
        if not username:
            raise PortalUserNotFoundError('门户用户缺少可用的登录账号。')

        User = get_user_model()
        try:
            with transaction.atomic():
                existing_binding = PortalUserBinding.objects.select_for_update().filter(
                    portal_user_id=portal_user_id,
                ).first()
                if existing_binding:
                    return existing_binding

                user = User.objects.select_for_update().filter(username=username).first()
                if user and PortalUserBinding.objects.filter(user=user).exclude(
                    portal_user_id=portal_user_id,
                ).exists():
                    raise PortalMappingConflictError('本地账号已绑定其他门户用户。')

                created = user is None
                if created:
                    user = User(username=username)
                    user.set_unusable_password()

                full_name = str(_first_value(detail, 'real_name', 'name', 'display_name', 'nickname') or '').strip()
                email = str(_first_value(detail, 'email', 'email_address') or '').strip()
                if full_name:
                    user.first_name = full_name[:150]
                if email:
                    user.email = email[:254]
                user.is_active = True
                user.save()

                AccountProfile.objects.get_or_create(
                    user=user,
                    defaults={'role': AccountProfile.Role.NORMAL},
                )
                binding = PortalUserBinding.objects.create(
                    portal_user_id=portal_user_id,
                    user=user,
                    access_status=PortalUserBinding.AccessStatus.ENABLED,
                    portal_expired_at=_normalise_expired_at(
                        _first_value(detail, 'expired_at', 'expire_time', 'expiration_time')
                    ),
                    profile_data=_safe_profile_data(detail),
                    last_synced_at=timezone.now(),
                )
                return binding
        except IntegrityError as exc:
            binding = PortalUserBinding.objects.filter(portal_user_id=portal_user_id).first()
            if binding:
                return binding
            raise PortalMappingConflictError('门户用户与本地账号映射冲突。') from exc
