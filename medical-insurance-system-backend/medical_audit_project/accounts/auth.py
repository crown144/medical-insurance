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
        return AccountProfile.objects.select_related('user').get(user=user)
    except (signing.BadSignature, KeyError, TypeError, ValueError, get_user_model().DoesNotExist, AccountProfile.DoesNotExist):
        return None


def profile_payload(profile, token: str | None = None) -> dict:
    user = profile.user
    return {
        'userId': str(user.pk),
        'username': user.username,
        'realName': user.get_full_name() or ('开发用户' if profile.role == AccountProfile.Role.DEVELOPER else '普通用户'),
        'avatar': '',
        'desc': 'Developer' if profile.role == AccountProfile.Role.DEVELOPER else 'Normal User',
        'roles': [profile.role],
        **({'token': token} if token else {}),
    }
