"""Consumidor de la cola SQS de ms-empleados (PostulanteContratado / AusenciaAprobada / AusenciaFinalizada).

Devuelve batchItemFailures: solo los mensajes que fallan se reintentan y, tras 3 intentos, pasan a la DLQ.
"""
import json
import logging

from src.services import eventos_service

log = logging.getLogger()
log.setLevel(logging.INFO)


def _parse(body):
    data = json.loads(body)
    if isinstance(data, dict) and "Message" in data and "tipo_evento" not in data:  # sobre SNS (sin raw delivery)
        data = json.loads(data["Message"])
    return data


def handler(event, context=None):
    fallos = []
    for rec in event.get("Records", []):
        try:
            eventos_service.procesar(_parse(rec["body"]))
        except Exception:  # noqa: BLE001
            log.exception("Fallo procesando mensaje %s", rec.get("messageId"))
            fallos.append({"itemIdentifier": rec["messageId"]})
    return {"batchItemFailures": fallos}
