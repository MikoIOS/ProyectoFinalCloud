from src.common.response import api, ok
from src.common.tenant import contexto
from src.services import empleados_service as svc

LECTURA = ("admin_rrhh", "gerente")


@api
def organigrama(event, context=None):
    ctx = contexto(event, LECTURA)
    return ok(svc.organigrama(ctx, event.get("queryStringParameters")))


@api
def resumen(event, context=None):
    ctx = contexto(event, LECTURA)
    return ok(svc.resumen(ctx))
