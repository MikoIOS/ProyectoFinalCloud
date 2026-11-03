"""Hash de contraseñas (scrypt, librería estándar) y JWT HS256.

scrypt evita compilar bcrypt para Lambda (no hace falta Docker en Windows).
Formato guardado: scrypt$N$r$p$<salt_b64>$<hash_b64>
"""
import base64
import hashlib
import hmac
import os
import secrets
import time

import jwt

from src.common.errors import NoAutenticado

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
TOKEN_TTL_SECONDS = 8 * 3600


def _b64(b):
    return base64.b64encode(b).decode()


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(dk)}"


def verify_password(password, stored):
    try:
        _, n, r, p, salt, expected = stored.split("$")
        dk = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                            n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(_b64(dk), expected)
    except Exception:  # noqa: BLE001
        return False


# Hash de relleno: se verifica contra él cuando el email no existe, para que
# el tiempo de respuesta no revele si la cuenta existe.
DUMMY_HASH = hash_password("relleno-no-usar")


def _secret():
    return os.environ["JWT_SECRET"]


def create_token(usuario):
    now = int(time.time())
    payload = {
        "sub": usuario["user_id"],
        "tenant_id": usuario["tenant_id"],
        "rol": usuario["rol"],
        "empleado_id": usuario.get("empleado_id"),
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, _secret(), algorithm="HS256"), TOKEN_TTL_SECONDS


def decode_token(token):
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise NoAutenticado("Token inválido o vencido")
