import base64
import json

from src.common.errors import Validacion

LIMIT_DEFAULT, LIMIT_MAX = 50, 200

INDICES = {
    "empleado-index": {"tenant_id", "sk", "empleado_periodo"},
    "periodo-index": {"tenant_id", "sk", "periodo_empleado"},
    "concepto-index": {"tenant_id", "sk", "periodo_concepto"},
    "planilla-index": {"tenant_id", "sk", "periodo_planilla"},
    "cargo-index": {"tenant_id", "sk", "banda_cargo"},
}


def parse_limit(qs, default=LIMIT_DEFAULT):
    raw = (qs or {}).get("limit")
    if raw in (None, ""):
        return default
    try:
        n = int(raw)
    except (TypeError, ValueError):
        raise Validacion("limit debe ser un entero")
    if not 1 <= n <= LIMIT_MAX:
        raise Validacion("limit debe estar entre 1 y %d" % LIMIT_MAX)
    return n


def parse_page(qs):
    raw = (qs or {}).get("page")
    if raw in (None, ""):
        return 1
    try:
        n = int(raw)
    except (TypeError, ValueError):
        raise Validacion("page debe ser un entero")
    if n < 1:
        raise Validacion("page debe ser >= 1")
    return n


def encode_token(key):
    return base64.urlsafe_b64encode(json.dumps(key).encode()).decode() if key else None


def decode_token(token, tenant_id, index=None):
    """Decodifica next_token y verifica que pertenezca al tenant y al índice usados."""
    if not token:
        return None
    try:
        key = json.loads(base64.urlsafe_b64decode(token.encode()))
        esperadas = INDICES.get(index, {"tenant_id"})
        if (not isinstance(key, dict) or key.get("tenant_id") != tenant_id
                or set(key) != esperadas or not all(isinstance(v, str) for v in key.values())):
            raise ValueError
        return key
    except Exception:  # noqa: BLE001
        raise Validacion("next_token inválido")
