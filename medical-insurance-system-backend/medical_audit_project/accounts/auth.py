from django.conf import settings
from django.core import signing
from django.contrib.auth import get_user_model
import time

from .models import AccountProfile


TOKEN_SALT = 'medical-audit.accounts.access-token'


def build_access_token(user, *, portal_expired_at=None) -> str:
    payload = {'user_id': user.pk}
    if portal_expired_at is not None:
        payload['portal_expired_at'] = portal_expired_at
    return signing.dumps(payload, salt=TOKEN_SALT, compress=True)


def portal_expiry_reached(value):
    if type(value) is not int or value < -1:
        return True
    if value == -1:
        return False
    timestamp = value / 1000 if value > 100_000_000_000 else value
    return timestamp <= time.time()


def has_portal_access(user) -> bool:
    if getattr(settings, 'PORTAL_AUTH_MODE', 'existing') == 'existing':
        return user.is_active
    if settings.PORTAL_AUTH_MODE != 'synced':
        return False
    from portal_integration.models import PortalUserBinding
    from portal_integration.services.actions import is_binding_expired

    binding = PortalUserBinding.objects.filter(user=user).first()
    return not binding or (
        binding.access_status == PortalUserBinding.AccessStatus.ENABLED
        and binding.profile_data.get('status') != 2
        and not is_binding_expired(binding)
    )


def get_request_profile(request):
    authorization = request.headers.get('Authorization', '') or request.headers.get('accessToken', '')
    token = authorization.removeprefix('Bearer ').strip()
    if not token:
        return None
    try:
        payload = signing.loads(
            token,
            salt=TOKEN_SALT,
            max_age=getattr(settings, 'MEDICAL_AUDIT_AUTH_TOKEN_MAX_AGE', 60 * 60 * 12),
        )
        user = get_user_model().objects.get(pk=payload['user_id'], is_active=True)
        if 'portal_expired_at' in payload and portal_expiry_reached(payload['portal_expired_at']):
            return None
        # A portal-bound account can also become invalid because its application
        # access expired. Check on every request so an already issued token is
        # blocked immediately without maintaining a token blacklist.
        if not has_portal_access(user):
            return None
        return AccountProfile.objects.select_related('user').get(user=user)
    except (signing.BadSignature, KeyError, TypeError, ValueError, get_user_model().DoesNotExist, AccountProfile.DoesNotExist):
        return None


def profile_payload(profile, token: str | None = None) -> dict:
    user = profile.user
    display = {
        AccountProfile.Role.DEVELOPER: ('开发用户', 'Developer'),
        AccountProfile.Role.ADMIN: ('应用管理员', 'Administrator'),
        AccountProfile.Role.NORMAL: ('普通用户', 'Normal User'),
    }[profile.role]
    return {
        'userId': str(user.pk),
        'username': user.username,
        'realName': user.get_full_name() or display[0],
        'avatar': '',
        'desc': display[1],
        'roles': [profile.role],
        **({'token': token} if token else {}),
    }
