import json
import logging

from src.services import planillas

log = logging.getLogger()
log.setLevel(logging.INFO)


def handler(event, context=None):
    fallos = []
    for rec in event.get("Records", []):
        try:
            body = json.loads(rec["body"])
            planillas.procesar_planilla(
                body["tenant_id"],
                body["periodo"],
                body["ejecucion_id"],
                body.get("notificar", True),
            )
        except Exception:  # noqa: BLE001
            log.exception("Fallo procesando planilla %s", rec.get("messageId"))
            fallos.append({"itemIdentifier": rec["messageId"]})
    return {"batchItemFailures": fallos}
