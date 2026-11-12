from src.common.response import api, json_body, ok
from src.common.tenant import contexto
from src.services import auth_service, usuarios_service


@api
def login(event, context=None):
    # Única ruta donde el tenant viene en el body: todavía no existe JWT.
    body = json_body(event)
    return ok(auth_service.login(body.get("tenant_id"), body.get("email"), body.get("password")))


@api
def registrar_empresa(event, context=None):
    return ok(auth_service.registrar_empresa(json_body(event)), status=201)


@api
def cambiar_password(event, context=None):
    ctx = contexto(event)  # cualquier rol autenticado
    return ok(usuarios_service.cambiar_password(ctx, json_body(event)))


@api
def ping(event, context=None):
    return ok({"service": "ms-usuarios", "status": "ok"})
