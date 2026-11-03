from src.common.response import api, json_body, ok
from src.common.tenant import contexto
from src.services import empleados_service as svc

ADMIN = ("admin_rrhh",)
LECTURA = ("admin_rrhh", "gerente")


def _id(event):
    return (event.get("pathParameters") or {}).get("id", "")


@api
def crear(event, context=None):
    ctx = contexto(event, ADMIN)
    return ok(svc.crear(ctx, json_body(event)), 201)


@api
def listar(event, context=None):
    ctx = contexto(event, LECTURA)
    return ok(svc.listar(ctx, event.get("queryStringParameters")))


@api
def obtener(event, context=None):
    ctx = contexto(event)  # admin y gerente cualquiera; los demás solo el suyo (lo valida el servicio)
    return ok(svc.obtener(ctx, _id(event)))


@api
def actualizar(event, context=None):
    ctx = contexto(event, ADMIN)
    return ok(svc.actualizar(ctx, _id(event), json_body(event)))


@api
def cambiar_estado(event, context=None):
    ctx = contexto(event, ADMIN)
    return ok(svc.cambiar_estado(ctx, _id(event), json_body(event)))
