from src.common.auth import contexto
from src.common.response import api, json_body, ok
from src.services import conceptos as svc


@api
def crear(event, context=None):
    ctx = contexto(event)
    return ok(svc.crear(ctx, json_body(event)), 201)


@api
def listar(event, context=None):
    ctx = contexto(event)
    return ok(svc.listar(ctx, event.get("queryStringParameters") or {}))
