import re
import uuid

from src.common import pagination
from src.common.errors import Conflicto, NoEncontrado, NoAutenticado, Prohibido, Validacion
from src.common.security import hash_password, verify_password
from src.repositories import usuarios_repo

ROLES = ("admin_rrhh", "gerente", "reclutador", "empleado")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


def publico(item):
    """Usuario sin datos sensibles."""
    return {k: v for k, v in item.items() if k != "password_hash"}


def _texto(body, campo, requerido=True):
    v = body.get(campo)
    if v is None or (isinstance(v, str) and not v.strip()):
        if requerido:
            raise Validacion("%s es obligatorio" % campo)
        return None
    if not isinstance(v, str):
        raise Validacion("%s debe ser texto" % campo)
    return v.strip()


def _validar_rol(rol):
    if rol not in ROLES:
        raise Validacion("rol inválido; valores permitidos: %s" % ", ".join(ROLES))


def _validar_password(p):
    if not isinstance(p, str) or len(p) < MIN_PASSWORD:
        raise Validacion("La contraseña debe tener al menos %d caracteres" % MIN_PASSWORD)


def crear(ctx, body):
    nombre = _texto(body, "nombre")
    email = _texto(body, "email").lower()
    rol = _texto(body, "rol")
    password = body.get("password")
    empleado_id = _texto(body, "empleado_id", requerido=False)
    if not EMAIL_RE.match(email):
        raise Validacion("email inválido")
    _validar_rol(rol)
    _validar_password(password)

    if usuarios_repo.get_by_email(ctx.tenant_id, email):
        raise Conflicto("Ya existe un usuario con ese email en este tenant")

    item = {
        "tenant_id": ctx.tenant_id,  # del token, nunca del body
        "user_id": "usr-" + uuid.uuid4().hex[:8],
        "email": email,
        "password_hash": hash_password(password),
        "nombre": nombre,
        "rol": rol,
        "activo": True,
        "debe_cambiar_password": True,
    }
    if empleado_id:  # omitir si no hay: un GSI no admite atributos nulos
        item["empleado_id"] = empleado_id
    return publico(usuarios_repo.put_new(item))


def listar(ctx, qs):
    qs = qs or {}
    limit = pagination.parse_limit(qs)
    start = pagination.decode_token(qs.get("next_token"), ctx.tenant_id)
    rol = qs.get("rol") or None
    if rol:
        _validar_rol(rol)
    activo = None
    if qs.get("activo") not in (None, ""):
        if qs["activo"] not in ("true", "false"):
            raise Validacion("activo debe ser true o false")
        activo = qs["activo"] == "true"
    items, last = usuarios_repo.listar(ctx.tenant_id, limit, start, rol, activo)
    return {"items": [publico(i) for i in items], "next_token": pagination.encode_token(last)}


def obtener(ctx, user_id):
    item = usuarios_repo.get(ctx.tenant_id, user_id)
    if not item:
        raise NoEncontrado("Usuario no encontrado")
    return publico(item)


def mi_usuario(ctx):
    return obtener(ctx, ctx.user_id)


def actualizar(ctx, user_id, body):
    permitidos = {"nombre", "rol", "activo"}
    extra = set(body) - permitidos
    if extra:
        raise Validacion("Campos no permitidos: %s" % ", ".join(sorted(extra)))
    if not body:
        raise Validacion("Nada que actualizar")
    cambios = {}
    if "nombre" in body:
        cambios["nombre"] = _texto(body, "nombre")
    if "rol" in body:
        _validar_rol(body["rol"])
        cambios["rol"] = body["rol"]
    if "activo" in body:
        if not isinstance(body["activo"], bool):
            raise Validacion("activo debe ser true o false")
        cambios["activo"] = body["activo"]

    if user_id == ctx.user_id and (cambios.get("activo") is False or ("rol" in cambios and cambios["rol"] != ctx.rol)):
        raise Prohibido("No puedes desactivarte ni cambiar tu propio rol")
    return publico(usuarios_repo.update(ctx.tenant_id, user_id, cambios))


def cambiar_password(ctx, body):
    actual, nueva = body.get("password_actual"), body.get("password_nueva")
    if not isinstance(actual, str) or not actual:
        raise Validacion("password_actual es obligatorio")
    _validar_password(nueva)
    if nueva == actual:
        raise Validacion("La nueva contraseña debe ser distinta de la actual")
    item = usuarios_repo.get(ctx.tenant_id, ctx.user_id)
    if not item:
        raise NoEncontrado("Usuario no encontrado")
    if not verify_password(actual, item["password_hash"]):
        raise NoAutenticado("La contraseña actual no es correcta")
    usuarios_repo.update(ctx.tenant_id, ctx.user_id,
                         {"password_hash": hash_password(nueva), "debe_cambiar_password": False})
    return {"mensaje": "Contraseña actualizada"}
