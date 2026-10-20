import logging
import uuid

from django.conf import settings
from django.db import transaction
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import PortalUserActionSerializer, PortalUserDetailSerializer, QueryUserStatusSerializer
from .services.actions import PortalActionService, record_action_log
from .services.crypto import PortalProtocol
from .services.exceptions import PortalIntegrationError


logger = logging.getLogger(__name__)


class PortalActionView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    action_type = None

    def post(self, request):
        if getattr(settings, 'PORTAL_AUTH_MODE', 'existing') != 'synced':
            return Response({
                'code': 40901,
                'message': '已有账号登录模式不支持门户用户权限同步；未修改本地账号或数据库。',
                'data': None,
            }, status=409)
        trace_id = str(request.headers.get('X-Trace-Id') or uuid.uuid4().hex)[:64]
        protocol = None
        payload = {}
        try:
            protocol = PortalProtocol()
            payload = protocol.parse_request(request)
            serializer_class = {
                'query_user_status': QueryUserStatusSerializer,
                'create_user_callback': PortalUserDetailSerializer,
                'edit_user_callback': PortalUserDetailSerializer,
            }.get(self.action_type, PortalUserActionSerializer)
            serializer = serializer_class(data=payload)
            if not serializer.is_valid():
                self._record_failure(payload, trace_id, 40001)
                body, headers = protocol.encode_response(
                    code=40001,
                    message=self._validation_message(serializer.errors),
                    data=None,
                )
                return Response(body, status=200, headers=headers)

            # Commit only after the success response has been encrypted/signed.
            # Otherwise an encoding failure would report failure after changing
            # the user, and a portal retry could apply the operation again.
            with transaction.atomic():
                service = PortalActionService()
                if self.action_type == 'query_user_status':
                    data = service.query_user_status(serializer.validated_data['user_ids'])
                elif self.action_type in ('create_user_callback', 'edit_user_callback'):
                    service.sync_user(serializer.validated_data, action_type=self.action_type, trace_id=trace_id)
                    data = None
                else:
                    portal_user_id = serializer.validated_data['user_id']
                    method = {
                        'app_admin_set': service.set_app_admin,
                        'remove_user': service.remove_user,
                        'disable_user': service.disable_user,
                        'enable_user': service.enable_user,
                        'default_role_callback': service.set_default_role,
                    }[self.action_type]
                    method(portal_user_id, trace_id=trace_id)
                    data = None

                body, headers = protocol.encode_response(data=data)
            return Response(body, status=200, headers=headers)
        except PortalIntegrationError as exc:
            self._record_failure(payload, trace_id, exc.code)
            if protocol is None:
                return Response(
                    {'code': exc.code, 'message': str(exc), 'data': None},
                    status=exc.http_status,
                )
            try:
                body, headers = protocol.encode_response(
                    code=exc.code,
                    message=str(exc),
                    data=None,
                )
            except PortalIntegrationError:
                body, headers = {'code': exc.code, 'message': str(exc), 'data': None}, {}
            return Response(body, status=exc.http_status, headers=headers)
        except Exception:
            logger.exception('Unhandled portal action error action=%s trace_id=%s', self.action_type, trace_id)
            self._record_failure(payload, trace_id, 50002)
            body = {'code': 50002, 'message': '本地状态更新失败。', 'data': None}
            headers = {}
            if protocol is not None:
                try:
                    body, headers = protocol.encode_response(
                        code=50002,
                        message='本地状态更新失败。',
                        data=None,
                    )
                except PortalIntegrationError:
                    pass
            return Response(body, status=500, headers=headers)

    @staticmethod
    def _validation_message(errors):
        for value in errors.values():
            if isinstance(value, (list, tuple)) and value:
                return str(value[0])
            return str(value)
        return '请求参数格式错误。'

    def _record_failure(self, payload, trace_id, result_code):
        if self.action_type == 'query_user_status' or not isinstance(payload, dict):
            return
        portal_user_id = str(payload.get('user_id') or payload.get('id') or '')[:128]
        try:
            record_action_log(
                self.action_type,
                portal_user_id,
                {'user_id': portal_user_id} if portal_user_id else {},
                trace_id=trace_id,
                result_code=result_code,
            )
        except Exception:
            logger.exception(
                'Failed to persist portal action failure audit action=%s trace_id=%s',
                self.action_type,
                trace_id,
            )
