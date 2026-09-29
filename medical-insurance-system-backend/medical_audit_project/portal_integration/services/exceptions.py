class PortalIntegrationError(Exception):
    code = 50002
    http_status = 200

    def __init__(self, message=None, *, code=None, http_status=None):
        super().__init__(message or '门户集成处理失败。')
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status


class PortalProtocolError(PortalIntegrationError):
    code = 40101
    http_status = 401


class PortalUserNotFoundError(PortalIntegrationError):
    code = 40401


class PortalMappingConflictError(PortalIntegrationError):
    code = 40901


class PortalClientError(PortalIntegrationError):
    code = 50001
