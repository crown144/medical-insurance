from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.auth import build_access_token, profile_payload
from medical_audit_project.sso import (
    SSOError,
    build_frontend_url,
    call_service_validate,
    validate_app_callback,
    validate_appid,
    validate_portal_callback,
)
from medical_audit_project.sso_local import resolve_local_profile


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
        access_token = build_access_token(profile.user)
        return Response({
            'code': 0,
            'result': {
                'accessToken': access_token,
                'token': access_token,
                'callback': callback,
                **profile_payload(profile, access_token),
            },
            'message': 'ok',
            'type': 'success',
        })
    except SSOError as exc:
        return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def sso_exchange(request):
    return Response({'message': 'deprecated'}, status=status.HTTP_410_GONE)


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
        return Response({
            'code': 0,
            'result': {
                'callback': build_frontend_url(settings.SSO_FRONTEND_LOGOUT_PATH, {'callback': callback}),
            },
            'message': 'ok',
            'type': 'success',
        })
    except SSOError as exc:
        return Response({'message': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
