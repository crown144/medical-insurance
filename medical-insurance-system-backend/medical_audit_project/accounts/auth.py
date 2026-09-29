from django.conf import settings
from django.core import signing
from django.contrib.auth import get_user_model

from .models import AccountProfile


TOKEN_SALT = 'medical-audit.accounts.access-token'


def build_access_token(user) -> str:
    return signing.dumps({'user_id': user.pk}, salt=TOKEN_SALT, compress=True)


def get_request_profile(request):
    authorization = request.headers.get('Authorization', '')
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
        # A portal-bound account can also become invalid because its application
        # access expired. Check on every request so an already issued token is
        # blocked immediately without maintaining a token blacklist.
        from portal_integration.models import PortalUserBinding
        from portal_integration.services.actions import is_binding_expired

        binding = PortalUserBinding.objects.filter(user=user).first()
        if binding and (
            binding.access_status != PortalUserBinding.AccessStatus.ENABLED
            or is_binding_expired(binding)
        ):
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
