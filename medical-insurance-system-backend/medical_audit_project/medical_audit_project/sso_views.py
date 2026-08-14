from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.auth import build_access_token, profile_payload
from medical_audit_project.sso import (
    SSOError,
    build_frontend_url,
    build_handoff_token,
    call_service_validate,
    load_handoff_token,
    resolve_local_profile,
    validate_app_callback,
    validate_appid,
    validate_portal_callback,
)


def _set_sso_handoff_cookie(response: Response | HttpResponseRedirect, token: str) -> None:
    response.set_cookie(
        settings.SSO_HANDOFF_COOKIE_NAME,
        token,
        max_age=settings.SSO_HANDOFF_TOKEN_MAX_AGE,
        httponly=True,
        samesite='Lax',
        secure=settings.SSO_COOKIE_SECURE,
        path='/',
    )


def _clear_sso_handoff_cookie(response: Response | HttpResponseRedirect) -> None:
    response.delete_cookie(
        settings.SSO_HANDOFF_COOKIE_NAME,
        path='/',
        samesite='Lax',
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def sso_login(request):
    ticket = str(request.query_params.get('ticket') or '').strip()
    appid = str(request.query_params.get('appid') or '').strip()
    callback = str(request.query_params.get('callback') or '').strip()

    try:
        if not ticket:
            raise SSOError('缺少 ticket 参数')
        validate_appid(appid)
        callback = validate_app_callback(callback)
        portal_user = call_service_validate(ticket, appid)
        profile = resolve_local_profile(portal_user.username)
        handoff_token = build_handoff_token(profile, callback)
        response = HttpResponseRedirect(build_frontend_url(settings.SSO_FRONTEND_LOGIN_PATH))
        _set_sso_handoff_cookie(response, handoff_token)
        return response
    except SSOError as exc:
        return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def sso_exchange(request):
    handoff_token = request.COOKIES.get(settings.SSO_HANDOFF_COOKIE_NAME, '')
    if not handoff_token:
        return Response({'message': 'SSO 临时凭证不存在或已失效'}, status=status.HTTP_401_UNAUTHORIZED)

    try:
        payload = load_handoff_token(handoff_token)
        user = get_user_model().objects.get(pk=payload['user_id'], is_active=True)
        profile = resolve_local_profile(user.username)
        access_token = build_access_token(profile.user)
        response = Response({
            'code': 0,
            'result': {
                'accessToken': access_token,
                'token': access_token,
                'callback': payload['callback'],
                **profile_payload(profile),
            },
            'message': 'ok',
            'type': 'success',
        })
        _clear_sso_handoff_cookie(response)
        return response
    except get_user_model().DoesNotExist:
        response = Response({'message': '本系统不存在该用户或用户已停用'}, status=status.HTTP_400_BAD_REQUEST)
        _clear_sso_handoff_cookie(response)
        return response
    except SSOError as exc:
        response = Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        _clear_sso_handoff_cookie(response)
        return response


@api_view(['GET'])
@permission_classes([AllowAny])
def sso_logout(request):
    status_value = str(request.query_params.get('status') or '').strip()
    appid = str(request.query_params.get('appid') or '').strip()
    callback = str(request.query_params.get('callback') or '').strip()

    try:
        if status_value != 'server_logout':
            raise SSOError('status 校验失败')
        validate_appid(appid)
        validate_portal_callback(callback)
        response = HttpResponseRedirect(
            build_frontend_url(settings.SSO_FRONTEND_LOGOUT_PATH, {'callback': callback}),
        )
        _clear_sso_handoff_cookie(response)
        return response
    except SSOError as exc:
        return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
