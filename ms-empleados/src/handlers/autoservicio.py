from src.common.response import api, json_body, ok
from src.common.tenant import contexto
from src.services import empleados_service as svc


@api
def mi_ficha(event, context=None):
    return ok(svc.mi_ficha(contexto(event)))


@api
def actualizar_mi_contacto(event, context=None):
    ctx = contexto(event)
    return ok(svc.actualizar_mi_contacto(ctx, json_body(event)))
