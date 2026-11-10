"""Consumidor de eventos de hcm-eventos relevantes para nóminas.

- AusenciaAprobada sin goce -> conceptos SIN_GOCE por mes.
- EmpleadoCesado -> liquidación referencial.

Devuelve batchItemFailures para que SQS reintente solo lo que falló y derive a DLQ.
"""
import json
import logging

from src.common.dates import fecha
from src.repositories import nominas_repo as repo
from src.services import conceptos, liquidacion

log = logging.getLogger()
log.setLevel(logging.INFO)


def _parse(body):
    data = json.loads(body)
    if isinstance(data, dict) and "Message" in data and "tipo_evento" not in data:
        data = json.loads(data["Message"])
    return data


def _procesar(evt):
    tipo = evt.get("tipo_evento")
    tenant = evt.get("tenant_id")
    datos = evt.get("datos") or {}
    if not tipo or not tenant:
        raise ValueError("Evento sin tipo_evento o tenant_id")

    if tipo == "AusenciaAprobada":
        sin_goce = datos.get("tipo") == "SIN_GOCE" or datos.get("con_goce") is False
        if not sin_goce:
            return "ignorado"
        conceptos.registrar_sin_goce(
            tenant,
            datos.get("empleado_id"),
            datos.get("ausencia_id"),
            datos.get("desde"),
            datos.get("hasta"),
        )
        return "procesado"

    if tipo == "EmpleadoCesado":
        empleado_id = datos.get("empleado_id")
        cese = fecha(datos.get("fecha_cese"))
        if not empleado_id or not cese:
            raise ValueError("EmpleadoCesado sin empleado_id o fecha_cese")
        empleado = repo.get_empleado(tenant, empleado_id)
        if not empleado:
            log.info("EmpleadoCesado ignorado: %s/%s no existe", tenant, empleado_id)
            return "ignorado"
        liquidacion.calcular(empleado, cese, datos.get("motivo", ""))
        return "procesado"

    return "ignorado"


def handler(event, context=None):
    fallos = []
    for rec in event.get("Records", []):
        try:
            _procesar(_parse(rec["body"]))
        except Exception:  # noqa: BLE001
            log.exception("Fallo procesando evento %s", rec.get("messageId"))
            fallos.append({"itemIdentifier": rec["messageId"]})
    return {"batchItemFailures": fallos}
