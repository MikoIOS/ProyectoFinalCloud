"""Generación asíncrona y consultas de planillas/nóminas."""
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3

from src.common import events
from src.common.auth import propio_o_supervisor
from src.common.dates import dias_laborados, dinero, mes_actual, periodo_valido
from src.common.errors import Conflicto, NoEncontrado, Prohibido, Validacion
from src.common.pagination import decode_token, encode_token, parse_limit
from src.repositories import nominas_repo as repo
from src.repositories import boletas_s3
from src.services import calculo, pdf

PROCESO_COLGADO = timedelta(minutes=15)
ADMIN = ("admin_rrhh",)
LECTURA = ("admin_rrhh", "gerente")


def _ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _siguiente_mes(periodo):
    anio, mes = (int(x) for x in periodo.split("-"))
    mes += 1
    if mes > 12:
        mes = 1
        anio += 1
    return "%04d-%02d" % (anio, mes)


def _publico_planilla(item):
    return {
        "periodo": item.get("periodo"),
        "estado": item.get("estado"),
        "ejecucion_id": item.get("ejecucion_id"),
        "total_empleados": item.get("total_empleados", 0),
        "procesados": item.get("procesados", 0),
        "total_bruto": item.get("total_bruto", 0),
        "total_descuentos": item.get("total_descuentos", 0),
        "total_neto": item.get("total_neto", 0),
        "total_essalud": item.get("total_essalud", 0),
        "iniciado_en": item.get("iniciado_en"),
        "completado_en": item.get("completado_en"),
        "mensaje_error": item.get("mensaje_error"),
        "solicitado_por": item.get("solicitado_por"),
    }


def _publico_resumen(item):
    return {
        "nomina_id": item.get("nomina_id"),
        "empleado_id": item.get("empleado_id"),
        "nombre_empleado": item.get("nombre_empleado"),
        "documento": item.get("documento"),
        "area": item.get("area"),
        "cargo": item.get("cargo"),
        "periodo": item.get("periodo"),
        "dias_laborados": item.get("dias_laborados"),
        "sueldo_base": item.get("sueldo_base"),
        "bonos": item.get("bonos"),
        "descuentos": item.get("descuentos"),
        "neto": item.get("neto"),
        "aporte_essalud": item.get("aporte_essalud"),
        "estado": item.get("estado"),
        "generado_en": item.get("generado_en"),
    }


def _publico_detalle(item):
    data = _publico_resumen(item)
    data["detalle"] = item.get("detalle", [])
    return data


def _publico_liquidacion(item):
    if not item:
        return None
    return {
        "empleado_id": item.get("empleado_id"),
        "fecha_cese": item.get("fecha_cese"),
        "motivo": item.get("motivo"),
        "vacaciones_truncas": item.get("vacaciones_truncas"),
        "cts_trunca": item.get("cts_trunca"),
        "gratificacion_trunca": item.get("gratificacion_trunca"),
        "total": item.get("total"),
        "calculado_en": item.get("calculado_en"),
    }


# ------------------------------------------------------------------ generación
def generar(ctx, body):
    if ctx.rol not in ADMIN:
        raise Prohibido("Solo RR.HH. puede generar la planilla")
    periodo = periodo_valido(body.get("periodo"))
    if periodo > _siguiente_mes(mes_actual()):
        raise Validacion("No se puede generar la planilla de un periodo tan lejano: %s" % periodo)

    forzar = body.get("forzar") is True
    notificar = body.get("notificar") is not False
    planilla = repo.get_planilla(ctx.tenant_id, periodo)

    if planilla:
        estado = planilla.get("estado")
        if estado == "EN_PROCESO":
            iniciado = _parse_iso(planilla.get("iniciado_en"))
            if iniciado and datetime.now(timezone.utc) - iniciado < PROCESO_COLGADO:
                raise Conflicto(
                    "La planilla %s se está generando (%s/%s)"
                    % (periodo, planilla.get("procesados", 0), planilla.get("total_empleados", 0))
                )
        if estado == "PAGADA":
            raise Conflicto("La planilla %s ya fue pagada y no se puede recalcular" % periodo)
        if estado == "GENERADA" and not forzar:
            raise Conflicto('La planilla %s ya existe. Envía "forzar": true para recalcularla' % periodo)

    ejecucion_id = uuid.uuid4().hex
    item = {
        "tenant_id": ctx.tenant_id,
        "sk": "PLANILLA#" + periodo,
        "tipo": "PLANILLA",
        "planilla_id": "pla-" + periodo,
        "periodo_planilla": periodo,
        "periodo": periodo,
        "estado": "EN_PROCESO",
        "ejecucion_id": ejecucion_id,
        "total_empleados": 0,
        "procesados": 0,
        "total_bruto": dinero(0),
        "total_descuentos": dinero(0),
        "total_neto": dinero(0),
        "total_essalud": dinero(0),
        "iniciado_en": _ahora(),
        "completado_en": None,
        "mensaje_error": None,
        "solicitado_por": ctx.user_id,
        "notificar": notificar,
        "actualizado_en": _ahora(),
    }
    repo.put_planilla(item)
    _encolar(ctx.tenant_id, periodo, ejecucion_id, notificar)
    return _publico_planilla(item)


def _parse_iso(valor):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None


def _encolar(tenant_id, periodo, ejecucion_id, notificar):
    sqs = boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    sqs.send_message(
        QueueUrl=os.environ["TRABAJOS_QUEUE_URL"],
        MessageBody=json.dumps({
            "tenant_id": tenant_id,
            "periodo": periodo,
            "ejecucion_id": ejecucion_id,
            "notificar": notificar,
        }),
    )


# ------------------------------------------------------------------ worker
def procesar_planilla(tenant_id, periodo, ejecucion_id, notificar=True):
    planilla = repo.get_planilla(tenant_id, periodo)
    if not planilla or planilla.get("ejecucion_id") != ejecucion_id:
        return {"omitida": True}
    if planilla.get("estado") in ("GENERADA", "PAGADA"):
        return {"omitida": True}

    if not repo.update_planilla(tenant_id, periodo, {
        "estado": "EN_PROCESO",
        "total_empleados": 0,
        "procesados": 0,
        "total_bruto": dinero(0),
        "total_descuentos": dinero(0),
        "total_neto": dinero(0),
        "total_essalud": dinero(0),
        "mensaje_error": None,
        "completado_en": None,
    }, ejecucion_id=ejecucion_id):
        return {"omitida": True}
    try:
        repo.borrar_nominas_periodo(tenant_id, periodo)
        empleados = [
            e for e in repo.listar_empleados(tenant_id)
            if Decimal(str(e.get("salario_base") or 0)) > 0 and dias_laborados(e, periodo) > 0
        ]
        conceptos = _conceptos_por_empleado(tenant_id, periodo)
        if not repo.update_planilla(
            tenant_id, periodo, {"total_empleados": len(empleados)}, ejecucion_id=ejecucion_id
        ):
            return {"omitida": True}

        for inicio in range(0, len(empleados), 200):
            lote = empleados[inicio:inicio + 200]
            nominas = [
                n for n in (calculo.calcular(e, periodo, conceptos.get(e["empleado_id"], [])) for e in lote)
                if n is not None
            ]
            if not nominas:
                continue
            repo.batch_put_nominas(nominas)
            if not repo.update_planilla(tenant_id, periodo, {
                "add_procesados": len(nominas),
                "add_total_bruto": sum((n["sueldo_base"] + n["bonos"] for n in nominas), Decimal("0")),
                "add_total_descuentos": sum((n["descuentos"] for n in nominas), Decimal("0")),
                "add_total_neto": sum((n["neto"] for n in nominas), Decimal("0")),
                "add_total_essalud": sum((n["aporte_essalud"] for n in nominas), Decimal("0")),
            }, ejecucion_id=ejecucion_id):
                return {"omitida": True}
            if notificar:
                for n in nominas:
                    events.publish_event("NominaGenerada", tenant_id, {
                        "nomina_id": n["nomina_id"],
                        "empleado_id": n["empleado_id"],
                        "email": n.get("email"),
                        "periodo": periodo,
                        "neto": n["neto"],
                        "mensaje": "Tu boleta de %s ya está disponible" % periodo,
                    })

        repo.update_planilla(tenant_id, periodo, {
            "estado": "GENERADA",
            "completado_en": _ahora(),
        }, ejecucion_id=ejecucion_id)
        return {"periodo": periodo, "procesados": len(empleados)}
    except Exception as e:  # noqa: BLE001
        repo.update_planilla(tenant_id, periodo, {
            "estado": "FALLIDA",
            "mensaje_error": "%s: %s" % (type(e).__name__, e),
        }, ejecucion_id=ejecucion_id)
        raise


def _conceptos_por_empleado(tenant_id, periodo):
    agrupados, start_key = {}, None
    while True:
        items, start_key = repo.query_conceptos_periodo(tenant_id, periodo, None, start_key)
        for item in items:
            agrupados.setdefault(item.get("empleado_id"), []).append(item)
        if not start_key:
            return agrupados


# ------------------------------------------------------------------ consultas
def listar_planillas(ctx, qs):
    if ctx.rol not in LECTURA:
        raise Prohibido("No tienes permisos para ver planillas")
    limit = parse_limit(qs)
    start_key = decode_token((qs or {}).get("next_token"), ctx.tenant_id, "planilla-index")
    items, last = repo.query_planillas(ctx.tenant_id, limit, start_key)
    return {"items": [_publico_planilla(i) for i in items], "next_token": encode_token(last)}


def obtener_planilla(ctx, periodo):
    if ctx.rol not in LECTURA:
        raise Prohibido("No tienes permisos para ver planillas")
    periodo = periodo_valido(periodo)
    item = repo.get_planilla(ctx.tenant_id, periodo)
    if not item:
        raise NoEncontrado("No hay planilla para %s" % periodo)
    return _publico_planilla(item)


def listar_nominas(ctx, qs):
    if ctx.rol not in LECTURA:
        raise Prohibido("No tienes permisos para ver nóminas")
    qs = qs or {}
    periodo = periodo_valido(qs.get("periodo"))
    area = (qs.get("area") or "").strip() or None
    limit = parse_limit(qs)
    start_key = decode_token(qs.get("next_token"), ctx.tenant_id, "periodo-index")
    items, last = repo.query_nominas_periodo(ctx.tenant_id, periodo, area, limit, start_key)
    return {"items": [_publico_resumen(i) for i in items], "next_token": encode_token(last)}


def nominas_empleado(ctx, empleado_id, qs):
    propio_o_supervisor(ctx, empleado_id, "Solo puedes ver tus propias boletas")
    limit = parse_limit(qs)
    start_key = decode_token((qs or {}).get("next_token"), ctx.tenant_id, "empleado-index")
    items, last = repo.query_nominas_empleado(ctx.tenant_id, empleado_id, limit, start_key)
    items = [i for i in items if i.get("tipo") == "NOMINA"]
    liquidacion = repo.get_liquidacion(ctx.tenant_id, empleado_id)
    return {
        "empleado_id": empleado_id,
        "nominas": {"items": [_publico_resumen(i) for i in items], "next_token": encode_token(last)},
        "liquidacion": _publico_liquidacion(liquidacion),
    }


def obtener_nomina(ctx, nomina_id):
    item = repo.get_nomina(ctx.tenant_id, nomina_id)
    if not item:
        raise NoEncontrado("Nómina no encontrada con ID: %s" % nomina_id)
    propio_o_supervisor(ctx, item.get("empleado_id"), "Solo puedes ver tus propias boletas")
    return _publico_detalle(item)


def boleta(ctx, nomina_id, qs):
    item = repo.get_nomina(ctx.tenant_id, nomina_id)
    if not item:
        raise NoEncontrado("Nómina no encontrada con ID: %s" % nomina_id)
    propio_o_supervisor(ctx, item.get("empleado_id"), "Solo puedes ver tus propias boletas")
    contenido = pdf.generar(item)
    nombre = "boleta-%s-%s.pdf" % (item.get("periodo"), item.get("empleado_id"))
    boletas_s3.guardar(ctx.tenant_id, item, contenido, nombre)
    if (qs or {}).get("formato") == "json":
        import base64
        return {"nombre_archivo": nombre, "contenido_base64": base64.b64encode(contenido).decode("ascii")}
    return contenido, nombre


def resumen(ctx, qs):
    if ctx.rol not in LECTURA:
        raise Prohibido("No tienes permisos para ver el resumen de nóminas")
    qs = qs or {}
    periodo = qs.get("periodo")
    if periodo:
        periodo = periodo_valido(periodo)
        planilla = repo.get_planilla(ctx.tenant_id, periodo)
    else:
        items, _ = repo.query_planillas(ctx.tenant_id, 1)
        planilla = items[0] if items else None
        periodo = planilla.get("periodo") if planilla else mes_actual()

    activos = repo.contar_activos(ctx.tenant_id)
    if not planilla:
        return {
            "periodo": periodo, "estado": None, "procesados": 0,
            "total_bruto": 0, "total_descuentos": 0, "total_neto": 0,
            "total_essalud": 0, "empleados_activos": activos,
        }
    return {
        "periodo": periodo,
        "estado": planilla.get("estado"),
        "procesados": planilla.get("procesados", 0),
        "total_bruto": planilla.get("total_bruto", 0),
        "total_descuentos": planilla.get("total_descuentos", 0),
        "total_neto": planilla.get("total_neto", 0),
        "total_essalud": planilla.get("total_essalud", 0),
        "empleados_activos": activos,
    }
