"""Bandas salariales por cargo (referencia de compensación)."""
import re
from datetime import datetime, timezone
from decimal import Decimal

from src.common.dates import dinero
from src.common.errors import Validacion
from src.repositories import nominas_repo as repo


def _ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def listar(ctx):
    if ctx.rol not in ("admin_rrhh", "gerente", "reclutador"):
        from src.common.errors import Prohibido
        raise Prohibido("No tienes permisos para ver bandas salariales")
    items, _ = repo.query_bandas(ctx.tenant_id, limit=200)
    return {"items": [_publico(i) for i in items], "total": len(items)}


def guardar(ctx, body):
    if ctx.rol != "admin_rrhh":
        from src.common.errors import Prohibido
        raise Prohibido("Solo RR.HH. puede modificar bandas salariales")
    cargo = (body.get("cargo") or "").strip()
    if not cargo:
        raise Validacion("cargo es obligatorio")
    if len(cargo) > 120:
        raise Validacion("cargo no puede superar 120 caracteres")
    try:
        minimo = dinero(body.get("minimo"))
        maximo = dinero(body.get("maximo"))
    except Exception:  # noqa: BLE001
        raise Validacion("minimo y maximo deben ser numéricos")
    if minimo > maximo:
        raise Validacion("El mínimo no puede ser mayor que el máximo")
    moneda = (body.get("moneda") or "PEN").upper()
    if not re.match(r"^[A-Z]{3}$", moneda):
        raise Validacion("moneda debe tener 3 letras (ej. PEN)")

    item = {
        "tenant_id": ctx.tenant_id,
        "sk": "BANDA#" + cargo,
        "tipo": "BANDA",
        "banda_cargo": cargo,
        "cargo": cargo,
        "minimo": minimo,
        "maximo": maximo,
        "moneda": moneda,
        "actualizado_en": _ahora(),
    }
    repo.put_banda(item)
    return _publico(item)


def _publico(item):
    return {
        "cargo": item.get("cargo"),
        "minimo": item.get("minimo"),
        "maximo": item.get("maximo"),
        "moneda": item.get("moneda"),
        "actualizado_en": item.get("actualizado_en"),
    }
