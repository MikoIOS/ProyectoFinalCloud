import decimal
import functools
import json
import logging

from src.common.errors import AppError, Validacion

log = logging.getLogger()
log.setLevel(logging.INFO)

HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,OPTIONS",
}


def to_json(value):
    """DynamoDB devuelve Decimal: enteros como int y el resto como float."""
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError("No serializable: %r" % type(value))


def ok(body, status=200):
    return {
        "statusCode": status,
        "headers": HEADERS,
        "body": json.dumps(body, ensure_ascii=False, default=to_json),
    }


def error(status, codigo, mensaje):
    return ok({"error": {"codigo": codigo, "mensaje": mensaje}}, status)


def api(fn):
    """Envuelve un handler HTTP: traduce AppError a JSON y oculta errores inesperados."""

    @functools.wraps(fn)
    def wrapper(event, context=None):
        try:
            return fn(event, context)
        except AppError as e:
            return error(e.status, e.codigo, e.mensaje)
        except Exception:  # noqa: BLE001
            log.exception("Error inesperado")
            return error(500, "ERROR_INTERNO", "Error interno del servidor")

    return wrapper


def json_body(event):
    raw = event.get("body")
    if not raw:
        raise Validacion("El body es obligatorio")
    try:
        data = json.loads(raw, parse_float=decimal.Decimal)
    except (TypeError, ValueError):
        raise Validacion("El body debe ser JSON válido")
    if not isinstance(data, dict):
        raise Validacion("El body debe ser un objeto JSON")
    return data
