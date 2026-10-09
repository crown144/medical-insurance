import base64
import json
import re
import secrets

from django.conf import settings
from rest_framework.exceptions import ParseError, UnsupportedMediaType

from .exceptions import PortalConfigurationError, PortalProtocolError


_HEX_RE = re.compile(r'^[0-9a-fA-F]+$')


def _secure_random_hex(length):
    return secrets.token_hex((length + 1) // 2)[:length]


def _is_curve_point(public_key, curve):
    x, y = int(public_key[:64], 16), int(public_key[64:], 16)
    prime = int(curve['p'], 16)
    return x < prime and y < prime and (
        y * y - x * x * x - int(curve['a'], 16) * x - int(curve['b'], 16)
    ) % prime == 0


def _normalise_hex_key(value, *, public=False):
    key = ''.join(str(value or '').split())
    if key.startswith('-----BEGIN'):
        label = 'PUBLICKEY' if public else 'PRIVATEKEY'
        prefix, suffix = f'-----BEGIN{label}-----', f'-----END{label}-----'
        if not key.startswith(prefix) or not key.endswith(suffix):
            raise PortalConfigurationError('SM2 PEM 密钥类型无效。')
        key = key[len(prefix):-len(suffix)]
    key = key.removeprefix('0x')
    if public and key.startswith('04') and len(key) == 130:
        key = key[2:]
    if len(key) == (128 if public else 64) and _HEX_RE.fullmatch(key):
        return key.lower()
    try:
        from Cryptodome.Util.asn1 import DerBitString, DerObjectId, DerOctetString, DerSequence

        # v1.9 / Bouncy Castle: URL-safe Base64 SPKI public keys and PKCS#8
        # private keys, with id-ecPublicKey and the sm2p256v1 named curve.
        encoded = base64.b64decode(key + '=' * (-len(key) % 4), altchars=b'-_', validate=True)
        outer = DerSequence().decode(encoded, strict=True, nr_elements=2 if public else 3)
        if not public and outer[0] != 0:
            raise ValueError('PKCS#8 version')
        algorithm = DerSequence().decode(outer[0 if public else 1], strict=True, nr_elements=2)
        if (
            DerObjectId().decode(algorithm[0], strict=True).value != '1.2.840.10045.2.1'
            or DerObjectId().decode(algorithm[1], strict=True).value != '1.2.156.10197.1.301'
        ):
            raise ValueError('SM2 curve required')
        if public:
            point = DerBitString().decode(outer[1], strict=True).value
            if len(point) != 65 or point[0] != 4:
                raise ValueError('Uncompressed public key required')
            return point[1:].hex()
        ec_key = DerSequence().decode(
            DerOctetString().decode(outer[2], strict=True).payload,
            strict=True, nr_elements=(2, 3, 4),
        )
        scalar = DerOctetString().decode(ec_key[1], strict=True).payload
        if ec_key[0] != 1 or len(scalar) != 32:
            raise ValueError('EC private key format')
        return scalar.hex()
    except (ValueError, TypeError, IndexError) as exc:
        raise PortalConfigurationError('SM2 密钥须为 sm2p256v1 的 Base64 编码或原始十六进制。') from exc


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
    if len(text) == 128 and _HEX_RE.fullmatch(text):
        return text.lower()
    try:
        signature = base64.b64decode(text, validate=True)
    except (ValueError, TypeError) as exc:
        raise PortalProtocolError('签名编码无效。') from exc
    if len(signature) == 64:
        return signature.hex()
    try:
        from Cryptodome.Util.asn1 import DerSequence

        values = DerSequence().decode(signature, strict=True, nr_elements=2, only_ints_expected=True)
        if any(not 0 < v < 2 ** 256 for v in values):
            raise ValueError('Signature integer out of range')
        return ''.join(f'{v:064x}' for v in values)
    except (ValueError, TypeError) as exc:
        raise PortalProtocolError('SM2 DER 签名格式无效。') from exc


class PortalCrypto:
    """SM2/SM3 adapter for the portal's C1C2C3 wire format."""

    def __init__(self):
        try:
            from gmssl import func, sm2
        except ImportError as exc:
            raise PortalProtocolError('服务端未安装 SM2 协议依赖。', http_status=500) from exc

        # gmssl 3.2.2 encryption draws its ephemeral secret from random.choice.
        # Replace its shared helper with an OS-backed source, preserving the
        # expected hex-string interface for every gmssl call in this process.
        func.random_hex = _secure_random_hex

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
        # gmssl 3.2.2 uses lstrip('04') in its constructor, which can strip
        # actual coordinate digits from a raw public key. Restore the exact key.
        self._application.public_key = app_public_key
        self._portal.public_key = portal_public_key
        order = int(self._application.ecc_table['n'], 16)
        if not 1 <= int(private_key, 16) < order - 1:
            raise PortalConfigurationError('SM2 私钥超出有效范围。')
        for public_key in (app_public_key, portal_public_key):
            if not _is_curve_point(public_key, self._application.ecc_table):
                raise PortalConfigurationError('SM2 公钥不在有效曲线上。')
        expected_public = self._application._kg(int(private_key, 16), self._application.ecc_table['g'])
        if expected_public.lower() != app_public_key:
            raise PortalConfigurationError('SM2 应用公钥与私钥不匹配。')

    def verify_portal_signature(self, content, signature):
        if not signature:
            raise PortalProtocolError('请求缺少 eywa-signature 签名。')
        try:
            raw_signature = _signature_hex(signature)
            order = int(self._portal.ecc_table['n'], 16)
            if not all(0 < int(raw_signature[i:i + 64], 16) < order for i in (0, 64)):
                raise ValueError('Signature scalar out of range')
            # The Java reference signs decoded ciphertext bytes, not Base64 text.
            valid = self._portal.verify_with_sm3(raw_signature, _decode_binary(content))
        except Exception as exc:
            raise PortalProtocolError('门户请求验签失败。') from exc
        if not valid:
            raise PortalProtocolError('门户请求验签失败。')

    def decrypt_json(self, encrypted_data):
        try:
            from gmssl import sm3

            ciphertext = _decode_binary(encrypted_data)
            # Bouncy Castle encodes C1 as the 65-byte uncompressed curve point.
            # Retain support for the previous gmssl 64-byte C1 representation.
            if len(ciphertext) > 97 and ciphertext[0] == 4 and _is_curve_point(
                ciphertext[1:65].hex(), self._application.ecc_table,
            ):
                ciphertext = ciphertext[1:]
            if len(ciphertext) <= 96 or not _is_curve_point(ciphertext[:64].hex(), self._application.ecc_table):
                raise PortalProtocolError('门户请求密文格式无效。')
            plaintext = self._application.decrypt(ciphertext)
            # gmssl 3.2.2 computes C3 but does not compare it when decrypting.
            shared_point = bytes.fromhex(self._application._kg(
                int(self._application.private_key, 16), ciphertext[:64].hex(),
            ))
            digest = bytes.fromhex(sm3.sm3_hash(list(shared_point[:32] + plaintext + shared_point[32:])))
            if not secrets.compare_digest(digest, ciphertext[-32:]):
                raise PortalProtocolError('门户请求密文完整性校验失败。')
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
            return base64.b64encode(b'\x04' + ciphertext).decode('ascii')
        except Exception as exc:
            raise PortalProtocolError('门户响应加密失败。', http_status=500) from exc

    def sign_application_content(self, content):
        try:
            order = int(self._application.ecc_table['n'], 16)
            for _ in range(3):
                signature = self._application.sign_with_sm3(
                    _decode_binary(content),
                    f'{secrets.randbelow(order - 1) + 1:064x}',
                )
                if signature:
                    from Cryptodome.Util.asn1 import DerSequence

                    der = DerSequence([int(signature[:64], 16), int(signature[64:], 16)]).encode()
                    return base64.b64encode(der).decode('ascii')
            raise ValueError('SM2 signing did not produce a signature')
        except Exception as exc:
            raise PortalProtocolError('门户响应签名失败。', http_status=500) from exc


class PortalProtocol:
    def __init__(self):
        self.encrypted = bool(getattr(settings, 'PORTAL_ENCRYPT_ENABLED', False))
        if not self.encrypted and not (
            getattr(settings, 'DEBUG', False)
            and getattr(settings, 'PORTAL_ALLOW_PLAINTEXT', False)
        ):
            raise PortalConfigurationError('门户接口未配置加密验签，已拒绝请求。')
        self.crypto = PortalCrypto() if self.encrypted else None

    def parse_request(self, request):
        if self.encrypted:
            try:
                body = request.body.decode('ascii').strip()
                # The documented wire body is the Base64 string itself, even
                # with application/json. Also accept JSON strings and the
                # existing {"data": ...} wrapper for already configured callers.
                if body.startswith(('{', '"')):
                    decoded = json.loads(body)
                    encrypted_data = decoded.get('data') if isinstance(decoded, dict) else decoded
                else:
                    encrypted_data = body
            except (UnicodeDecodeError, ValueError) as exc:
                raise PortalProtocolError('加密请求体格式无效。') from exc
            if not isinstance(encrypted_data, str) or not encrypted_data:
                raise PortalProtocolError('加密请求缺少密文。')
            self.crypto.verify_portal_signature(encrypted_data, request.headers.get('eywa-signature'))
            return self.crypto.decrypt_json(encrypted_data)
        try:
            payload = request.data
        except (ParseError, UnsupportedMediaType) as exc:
            raise PortalProtocolError('请求体必须是有效的 JSON。', code=40001, http_status=200) from exc
        if not isinstance(payload, dict):
            raise PortalProtocolError('请求体必须是 JSON 对象。', code=40001, http_status=200)
        return payload

    def encode_response(self, *, code=0, message='操作成功', data=None):
        body = {'code': code, 'message': message, 'data': data}
        headers = {}
        if self.encrypted:
            encrypted_data = self.crypto.encrypt_json(data)
            body['data'] = encrypted_data
            headers['App-Signature'] = self.crypto.sign_application_content(encrypted_data)
        return body, headers
