import hashlib
import secrets
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.auth import build_access_token, has_portal_access, profile_payload
from .models import PortalLoginCode
from .services.exceptions import PortalClientError, PortalIntegrationError, PortalProtocolError
from .services.portal_client import PortalClient
from .services.user_sync import PortalUserSyncService


class LoginInput(serializers.Serializer):
    ticket = serializers.CharField(max_length=2048, required=False)
    appid = serializers.CharField(max_length=128, required=False)
    code = serializers.CharField(max_length=128, required=False)
    callback = serializers.CharField(max_length=4096, required=False, allow_blank=True)

    def validate(self, data):
        if data.get('code'):
            if data.get('ticket') or data.get('appid'):
                raise serializers.ValidationError('请只提交登录交换码或 ticket/appid。')
        elif not data.get('ticket') or not data.get('appid'):
            raise serializers.ValidationError('缺少门户 ticket 或 appid。')
        return data


def frontend_url():
    url = settings.PORTAL_FRONTEND_URL.rstrip('/')
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise PortalClientError('PORTAL_FRONTEND_URL 格式无效。') from exc
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.query or parsed.fragment:
        raise PortalClientError('请配置不含查询参数或片段的 PORTAL_FRONTEND_URL。')
    return url


def validate_callback(callback):
    if not callback:
        return ''
    try:
        parsed = urlsplit(callback)
        base = urlsplit(frontend_url())
    except ValueError as exc:
        raise PortalProtocolError('应用回跳地址无效。') from exc
    if callback.startswith('/') and not callback.startswith('//') and not parsed.netloc:
        return callback
    if parsed.scheme in ('http', 'https') and parsed.netloc == base.netloc and parsed.scheme == base.scheme:
        return callback
    raise PortalProtocolError('应用回跳地址必须属于医保前端。')


def authorization_url(callback):
    """v1.9 §3.1 step 2: service must exactly match the registered callback."""
    try:
        cas = urlsplit(settings.PORTAL_CAS_LOGIN_URL)
        service = urlsplit(settings.PORTAL_LOGIN_CALLBACK_URL)
    except ValueError as exc:
        raise PortalClientError('门户登录地址配置无效。') from exc
    if any(u.scheme not in ('http', 'https') or not u.netloc for u in (cas, service)) or cas.fragment:
        raise PortalClientError('请配置门户 CAS 登录地址和已注册的登录回调地址。')
    base = frontend_url()
    callback = validate_callback(callback)
    if not callback:
        callback = f'{base}/#/task/execution'
    elif callback.startswith('/'):
        callback = f'{base}/#{callback}'
    query = [(k, v) for k, v in parse_qsl(cas.query, keep_blank_values=True) if k not in ('service', 'callback')]
    query.extend([('service', settings.PORTAL_LOGIN_CALLBACK_URL), ('callback', callback)])
    return urlunsplit((cas.scheme, cas.netloc, cas.path, urlencode(query), ''))


class PortalSsoEntryView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    redirect_browser = False

    def get(self, request):
        if not settings.PORTAL_CAS_LOGIN_URL and not self.redirect_browser:
            return Response({'code': 0, 'result': {'enabled': False, 'authorizeUrl': ''}})
        try:
            url = authorization_url(request.query_params.get('callback', ''))
            if self.redirect_browser:
                return HttpResponseRedirect(url)
            return Response({'code': 0, 'result': {'enabled': True, 'authorizeUrl': url}}, headers={'Cache-Control': 'no-store'})
        except PortalIntegrationError as exc:
            return error_response(exc)


def login_result(user):
    if not user.is_active or not has_portal_access(user):
        raise PortalProtocolError('账号已停用、移除或应用权限已过期。', http_status=403)
    profile = user.audit_profile
    token = build_access_token(user)
    return {'code': 0, 'result': {'accessToken': token, 'token': token, **profile_payload(profile)}, 'message': '登录成功'}


def ticket_user(ticket, appid):
    detail = PortalClient().validate_ticket(ticket, appid)
    binding = PortalUserSyncService().sync_detail(detail, expected_id=detail['id'])
    return binding.user


def error_response(exc):
    # Callback business errors use HTTP 200; login endpoints use HTTP failures.
    status = exc.http_status if exc.http_status != 200 else {40901: 409, 40401: 404}.get(exc.code, 500)
    return Response({'code': exc.code, 'message': str(exc), 'result': None}, status=status, headers={'Cache-Control': 'no-store'})


class PortalSsoLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            # The frontend validates callbacks itself. Backend callbacks validate
            # before exchanging tickets, so no one-time credential is wasted.
            if data.get('code'):
                with transaction.atomic():
                    handoff = PortalLoginCode.objects.select_for_update().select_related('user').filter(
                        code_hash=hashlib.sha256(data['code'].encode()).hexdigest(),
                        expires_at__gt=timezone.now(),
                    ).first()
                    if not handoff:
                        raise PortalProtocolError('登录交换码无效或已过期，请从门户重新进入。')
                    result = login_result(handoff.user)
                    handoff.delete()
            else:
                result = login_result(ticket_user(data['ticket'], data['appid']))
            return Response(result, headers={'Cache-Control': 'no-store'})
        except PortalIntegrationError as exc:
            return error_response(exc)


class PortalSsoCallbackView(APIView):
    """Registered server login_callback: validate ticket, then HTTP 302 to the SPA."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        serializer = LoginInput(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data.get('code'):
            return Response({'message': '回调需要 ticket 和 appid。'}, status=400)
        try:
            base = frontend_url()
            callback = validate_callback(data.get('callback', ''))
            user = ticket_user(data['ticket'], data['appid'])
            login_result(user)
            code = secrets.token_urlsafe(32)
            now = timezone.now()
            with transaction.atomic():
                PortalLoginCode.objects.filter(expires_at__lte=now).delete()
                PortalLoginCode.objects.create(
                    code_hash=hashlib.sha256(code.encode()).hexdigest(), user=user,
                    expires_at=now + timedelta(minutes=2),
                )
            response = HttpResponseRedirect(f'{base}/#/oauth/login?{urlencode({"code": code, "callback": callback})}')
            response['Cache-Control'] = 'no-store'
            response['Referrer-Policy'] = 'no-referrer'
            return response
        except PortalIntegrationError as exc:
            return error_response(exc)
