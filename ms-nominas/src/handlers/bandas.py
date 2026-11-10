from src.common.auth import contexto
from src.common.response import api, json_body, ok
from src.services import bandas as svc


@api
def listar(event, context=None):
    ctx = contexto(event)
    return ok(svc.listar(ctx))


@api
def guardar(event, context=None):
    ctx = contexto(event)
    return ok(svc.guardar(ctx, json_body(event)))
