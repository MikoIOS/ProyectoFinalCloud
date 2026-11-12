"""Bonos, descuentos manuales y días sin goce provenientes de ausencias aprobadas."""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from src.common.auth import propio_o_supervisor
from src.common.dates import dinero, fecha, inicio_fin_mes, periodo_valido
from src.common.errors import Conflicto, NoEncontrado, Validacion
from src.repositories import nominas_repo as repo

TIPOS = {"BONO", "DESCUENTO"}


def _ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def crear(ctx, body):
    if ctx.rol != "admin_rrhh":
        from src.common.errors import Prohibido
        raise Prohibido("Solo RR.HH. puede registrar conceptos")

    periodo = periodo_valido(body.get("periodo"))
    tipo = (body.get("tipo") or "").upper()
    if tipo == "SIN_GOCE":
        raise Validacion("Los días sin goce se registran aprobando una ausencia SIN_GOCE en asistencia")
    if tipo not in TIPOS:
        raise Validacion("tipo debe ser BONO o DESCUENTO")
    concepto = (body.get("concepto") or "").strip()
    if not concepto:
        raise Validacion("concepto es obligatorio")
    if len(concepto) > 120:
        raise Validacion("concepto no puede superar 120 caracteres")
    monto = dinero(body.get("monto"))
    if monto <= 0:
        raise Validacion("monto debe ser mayor que 0")

    empleado_id = body.get("empleado_id")
    if not empleado_id:
        raise Validacion("empleado_id es obligatorio")
    if not repo.get_empleado(ctx.tenant_id, empleado_id):
        raise NoEncontrado("Empleado no encontrado: %s" % empleado_id)

    planilla = repo.get_planilla(ctx.tenant_id, periodo)
    if planilla and planilla.get("estado") == "PAGADA":
        raise Conflicto("La planilla %s ya fue pagada" % periodo)

    concepto_id = "con-%s" % uuid.uuid4().hex[:8]
    item = {
        "tenant_id": ctx.tenant_id,
        "sk": "CONCEPTO#" + concepto_id,
        "tipo": "CONCEPTO",
        "concepto_id": concepto_id,
        "empleado_id": empleado_id,
        "periodo": periodo,
        "periodo_concepto": "%s#%s" % (periodo, concepto_id),
        "tipo_concepto": tipo,
        "concepto": concepto,
        "monto": monto,
        "origen": "MANUAL",
        "creado_por": ctx.user_id,
        "creado_en": _ahora(),
    }
    repo.put_concepto(item)
    return _publico(item)


def listar(ctx, qs):
    qs = qs or {}
    periodo = periodo_valido(qs.get("periodo"))
    empleado_id = qs.get("empleado_id") or None
    if empleado_id:
        propio_o_supervisor(ctx, empleado_id, "Solo puedes ver tus propios conceptos")
    elif ctx.rol not in ("admin_rrhh", "gerente"):
        from src.common.errors import Prohibido
        raise Prohibido("No tienes permisos para ver conceptos de toda la planilla")

    items, _ = repo.query_conceptos_periodo(ctx.tenant_id, periodo, empleado_id)
    return {"items": [_publico(i) for i in items], "total": len(items)}


def _publico(item):
    return {
        "concepto_id": item.get("concepto_id"),
        "empleado_id": item.get("empleado_id"),
        "periodo": item.get("periodo"),
        "tipo": item.get("tipo_concepto"),
        "concepto": item.get("concepto"),
        "monto": item.get("monto"),
        "dias": item.get("dias"),
        "origen": item.get("origen"),
        "referencia": item.get("referencia"),
        "creado_en": item.get("creado_en"),
    }


def registrar_sin_goce(tenant_id, empleado_id, ausencia_id, desde, hasta):
    """Un concepto SIN_GOCE por cada mes que toca la ausencia. Idempotente por referencia."""
    desde, hasta = fecha(desde), fecha(hasta)
    if not desde or not hasta or hasta < desde:
        raise Validacion("La ausencia no trae fechas válidas")
    referencia = "AUSENCIA-%s" % ausencia_id

    anio, mes = desde.year, desde.month
    creados = 0
    while (anio, mes) <= (hasta.year, hasta.month):
        periodo = "%04d-%02d" % (anio, mes)
        if not repo.existe_referencia(tenant_id, periodo, empleado_id, referencia):
            inicio_mes, fin_mes = inicio_fin_mes(periodo)
            ini = max(desde, inicio_mes)
            fin = min(hasta, fin_mes)
            concepto_id = "con-%s" % uuid.uuid4().hex[:8]
            item = {
                "tenant_id": tenant_id,
                "sk": "CONCEPTO#" + concepto_id,
                "tipo": "CONCEPTO",
                "concepto_id": concepto_id,
                "empleado_id": empleado_id,
                "periodo": periodo,
                "periodo_concepto": "%s#%s" % (periodo, concepto_id),
                "tipo_concepto": "SIN_GOCE",
                "concepto": "Ausencia sin goce %s a %s" % (ini.isoformat(), fin.isoformat()),
                "dias": (fin - ini).days + 1,
                "origen": "AUSENCIA",
                "referencia": referencia,
                "creado_en": _ahora(),
            }
            repo.put_concepto(item)
            creados += 1
        mes += 1
        if mes > 12:
            mes = 1
            anio += 1
    return creados
