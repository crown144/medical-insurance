from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse

from .auth import get_request_profile


class ApiAccessMiddleware:
    """Apply account and portal access checks before any business API view."""

    PUBLIC_PATHS = {
        '/api/auth/login',
        '/api/auth/logout',
        '/api/sso/login',
        '/api/sso/logout',
        '/api/sso/exchange',
        # Deployment readiness checks use this empty-menu response.
        '/api/menu/all',
    }

    def __init__(self, get_response):
        if not settings.DEBUG and (
            not settings.SECRET_KEY or settings.SECRET_KEY.startswith('django-insecure-')
        ):
            raise ImproperlyConfigured('生产环境必须配置独立的 DJANGO_SECRET_KEY，不能使用仓库中的开发密钥。')
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        if (
            path.startswith('/api/')
            and not path.startswith('/api/portal/')
            and path.rstrip('/') not in self.PUBLIC_PATHS
            and request.method != 'OPTIONS'
        ):
            profile = get_request_profile(request)
            if profile is None:
                return JsonResponse({
                    'code': 401,
                    'message': '登录状态无效、账号已停用或应用访问权限已过期。',
                    'detail': '登录状态无效或已过期。',
                }, status=401)
        return self.get_response(request)
