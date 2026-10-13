from urllib.parse import urlencode

from django.http import HttpResponseRedirect
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from medical_audit_project.sso import validate_logout_callback
from portal_integration.services.exceptions import PortalIntegrationError, PortalProtocolError
from portal_integration.sso import error_response, frontend_url


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def sso_exchange(request):
    return Response({'message': 'deprecated'}, status=410, headers={'Cache-Control': 'no-store'})


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def sso_logout(request):
    try:
        if request.query_params.get('status') != 'server_logout':
            raise PortalProtocolError('status 校验失败')
        callback = validate_logout_callback(
            request.query_params.get('appid', '').strip(),
            request.query_params.get('callback', '').strip(),
        )
        response = HttpResponseRedirect(
            f'{frontend_url()}/#/auth/sso-logout?{urlencode({"callback": callback})}',
        )
        response['Cache-Control'] = 'no-store'
        response['Referrer-Policy'] = 'no-referrer'
        return response
    except PortalIntegrationError as exc:
        return error_response(exc)
