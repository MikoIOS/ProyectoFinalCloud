import uuid

from src.common.errors import Conflicto, NoAutenticado, Prohibido, Validacion
from src.common.security import DUMMY_HASH, create_token, hash_password, verify_password
from src.repositories import usuarios_repo
from src.services.usuarios_service import EMAIL_RE, _texto, _validar_password

MSG_CREDENCIALES = "Credenciales inválidas"


def login(tenant_id, email, password):
    if not all(isinstance(x, str) and x.strip() for x in (email, password)):
        raise Validacion("email y password son obligatorios")
    if tenant_id is not None and (not isinstance(tenant_id, str) or not tenant_id.strip()):
        raise Validacion("tenant_id debe ser texto no vacío")

    usuario = (usuarios_repo.get_by_email(tenant_id.strip(), email.strip()) if tenant_id is not None
               else usuarios_repo.get_by_login_email(email.strip()))
    if usuario is None:
        verify_password(password, DUMMY_HASH)  # igualar tiempos
        raise NoAutenticado(MSG_CREDENCIALES)
    if not verify_password(password, usuario["password_hash"]):
        raise NoAutenticado(MSG_CREDENCIALES)
    if not usuario.get("activo", False):
        raise Prohibido("Usuario desactivado")

    return _sesion(usuario)


def registrar_empresa(body):
    extra = set(body) - {"empresa", "ruc", "nombre", "email", "password"}
    if extra:
        raise Validacion("Campos no permitidos: %s" % ", ".join(sorted(extra)))
    empresa = _texto(body, "empresa")
    ruc = _texto(body, "ruc")
    if len(ruc) != 11 or not ruc.isascii() or not ruc.isdigit():
        raise Validacion("El RUC debe contener 11 dígitos")
    nombre = _texto(body, "nombre")
    email = _texto(body, "email").lower()
    password = body.get("password")
    _validar_password(password)
    if len(empresa) > 120 or len(nombre) > 120:
        raise Validacion("Empresa y nombre deben tener como máximo 120 caracteres")
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise Validacion("email inválido")
    if len(password) > 128:
        raise Validacion("La contraseña debe tener como máximo 128 caracteres")
    if usuarios_repo.email_existe(email):
        raise Conflicto("Este correo ya tiene una cuenta. Inicia sesión")
    usuario = {
        "tenant_id": "empresa-" + uuid.uuid4().hex,
        "user_id": "usr-" + uuid.uuid4().hex,
        "empresa_nombre": empresa,
        "ruc": ruc,
        "nombre": nombre,
        "email": email,
        "password_hash": hash_password(password),
        "rol": "admin_rrhh",
        "activo": True,
        "debe_cambiar_password": False,
    }
    sesion = _sesion(usuario)
    usuarios_repo.registrar_empresa(usuario)
    return sesion


def _sesion(usuario):
    token, expires_in = create_token(usuario)
    return {
        "token": token,
        "expires_in": expires_in,
        "usuario": {
            "user_id": usuario["user_id"],
            "nombre": usuario["nombre"],
            "rol": usuario["rol"],
            "tenant_id": usuario["tenant_id"],
            "empresa_nombre": usuario.get("empresa_nombre"),
            "ruc": usuario.get("ruc"),
            "empleado_id": usuario.get("empleado_id"),
            "debe_cambiar_password": bool(usuario.get("debe_cambiar_password", False)),
        },
    }
