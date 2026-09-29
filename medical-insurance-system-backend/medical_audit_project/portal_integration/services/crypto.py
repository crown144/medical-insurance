import base64
import json
import re
import secrets

from django.conf import settings

from .exceptions import PortalProtocolError


_HEX_RE = re.compile(r'^[0-9a-fA-F]+$')


def _normalise_hex_key(value, *, public=False):
    key = ''.join(str(value or '').split())
    if key.startswith('-----BEGIN'):
        raise PortalProtocolError('当前 SM2 实现要求密钥使用原始十六进制格式。')
    key = key.removeprefix('0x')
    if public and key.startswith('04') and len(key) == 130:
        key = key[2:]
    if not key or not _HEX_RE.fullmatch(key):
        raise PortalProtocolError('SM2 密钥配置无效。')
    return key.lower()


def _decode_binary(value):
    text = str(value or '').strip()
    if text and len(text) % 2 == 0 and _HEX_RE.fullmatch(text):
        return bytes.fromhex(text)
    try:
        return base64.b64decode(text, validate=True)
    except (ValueError, TypeError) as exc:
        raise PortalProtocolError('密文编码无效。') from exc


def _signature_hex(value):
    text = str(value or '').strip()
    if text and len(text) % 2 == 0 and _HEX_RE.fullmatch(text):
        return text.lower()
    try:
        return base64.b64decode(text, validate=True).hex()
    except (ValueError, TypeError) as exc:
        raise PortalProtocolError('签名编码无效。') from exc


class PortalCrypto:
    """SM2/SM3 adapter for the portal's C1C2C3 wire format."""

    def __init__(self):
        try:
            from gmssl import sm2
        except ImportError as exc:
            raise PortalProtocolError('服务端未安装 SM2 协议依赖。', http_status=500) from exc

        private_key = _normalise_hex_key(getattr(settings, 'PORTAL_APP_PRIVATE_KEY', ''))
        app_public_key = _normalise_hex_key(
            getattr(settings, 'PORTAL_APP_PUBLIC_KEY', ''),
            public=True,
        )
        portal_public_key = _normalise_hex_key(
            getattr(settings, 'PORTAL_PUBLIC_KEY', ''),
            public=True,
        )
        # gmssl mode=0 is C1C2C3, which is required by the portal specification.
        self._application = sm2.CryptSM2(
            private_key=private_key,
            public_key=app_public_key,
            mode=0,
        )
        self._portal = sm2.CryptSM2(
            private_key='',
            public_key=portal_public_key,
            mode=0,
        )

    def verify_portal_signature(self, content, signature):
        if not signature:
            raise PortalProtocolError('请求缺少 eywa-signature 签名。')
        try:
            valid = self._portal.verify_with_sm3(
                _signature_hex(signature),
                str(content).encode('utf-8'),
            )
        except Exception as exc:
            raise PortalProtocolError('门户请求验签失败。') from exc
        if not valid:
            raise PortalProtocolError('门户请求验签失败。')

    def decrypt_json(self, encrypted_data):
        try:
            plaintext = self._application.decrypt(_decode_binary(encrypted_data))
            payload = json.loads(plaintext.decode('utf-8'))
        except PortalProtocolError:
            raise
        except Exception as exc:
            raise PortalProtocolError('门户请求解密失败。') from exc
        if not isinstance(payload, dict):
            raise PortalProtocolError('解密后的请求必须是 JSON 对象。')
        return payload

    def encrypt_json(self, value):
        try:
            plaintext = json.dumps(
                value,
                ensure_ascii=False,
                separators=(',', ':'),
            ).encode('utf-8')
            # Responses are encrypted for the portal, while requests are
            # decrypted with the application's private key.
            ciphertext = self._portal.encrypt(plaintext)
            return base64.b64encode(ciphertext).decode('ascii')
        except Exception as exc:
            raise PortalProtocolError('门户响应加密失败。', http_status=500) from exc

    def sign_application_content(self, content):
        try:
            return self._application.sign_with_sm3(
                str(content).encode('utf-8'),
                secrets.token_hex(32),
            )
        except Exception as exc:
            raise PortalProtocolError('门户响应签名失败。', http_status=500) from exc


class PortalProtocol:
    def __init__(self):
        self.encrypted = bool(getattr(settings, 'PORTAL_ENCRYPT_ENABLED', False))
        self.crypto = PortalCrypto() if self.encrypted else None

    def parse_request(self, request):
        payload = request.data
        if not self.encrypted:
            if not isinstance(payload, dict):
                raise PortalProtocolError('请求体必须是 JSON 对象。', code=40001, http_status=200)
            return payload

        if not isinstance(payload, dict) or not isinstance(payload.get('data'), str):
            raise PortalProtocolError('加密请求缺少 data 密文。')
        encrypted_data = payload['data']
        self.crypto.verify_portal_signature(
            encrypted_data,
            request.headers.get('eywa-signature'),
        )
        return self.crypto.decrypt_json(encrypted_data)

    def encode_response(self, *, code=0, message='操作成功', data=None):
        body = {'code': code, 'message': message, 'data': data}
        headers = {}
        if self.encrypted:
            encrypted_data = self.crypto.encrypt_json(data)
            body['data'] = encrypted_data
            headers['App-Signature'] = self.crypto.sign_application_content(encrypted_data)
        return body, headers
