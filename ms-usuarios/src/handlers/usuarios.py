from src.common.response import api, json_body, ok
from src.common.tenant import contexto
from src.services import usuarios_service as svc

ADMIN = ("admin_rrhh",)


def _id(event):
    return (event.get("pathParameters") or {}).get("id", "")


@api
def crear(event, context=None):
    ctx = contexto(event, ADMIN)
    return ok(svc.crear(ctx, json_body(event)), 201)


@api
def listar(event, context=None):
    ctx = contexto(event, ADMIN)
    return ok(svc.listar(ctx, event.get("queryStringParameters")))


@api
def obtener(event, context=None):
    ctx = contexto(event, ADMIN)
    return ok(svc.obtener(ctx, _id(event)))


@api
def actualizar(event, context=None):
    ctx = contexto(event, ADMIN)
    return ok(svc.actualizar(ctx, _id(event), json_body(event)))


@api
def mi_usuario(event, context=None):
    ctx = contexto(event)  # cualquier rol autenticado
    return ok(svc.mi_usuario(ctx))
