import base64
import json

from src.common.errors import Validacion

LIMIT_DEFAULT, LIMIT_MAX = 50, 200


def parse_limit(qs):
    raw = (qs or {}).get("limit")
    if raw in (None, ""):
        return LIMIT_DEFAULT
    try:
        n = int(raw)
    except ValueError:
        raise Validacion("limit debe ser un entero")
    if not 1 <= n <= LIMIT_MAX:
        raise Validacion("limit debe estar entre 1 y %d" % LIMIT_MAX)
    return n


def encode_token(key):
    return base64.urlsafe_b64encode(json.dumps(key).encode()).decode() if key else None


def decode_token(token, tenant_id):
    """Decodifica next_token y verifica que pertenezca al tenant del request."""
    if not token:
        return None
    try:
        key = json.loads(base64.urlsafe_b64decode(token.encode()))
        if key.get("tenant_id") != tenant_id or not isinstance(key.get("user_id"), str):
            raise ValueError
        return {"tenant_id": key["tenant_id"], "user_id": key["user_id"]}
    except Exception:  # noqa: BLE001
        raise Validacion("next_token inválido")
