from src.common.errors import NoAutenticado, Prohibido, Validacion
from src.common.security import DUMMY_HASH, create_token, verify_password
from src.repositories import usuarios_repo

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

    token, expires_in = create_token(usuario)
    return {
        "token": token,
        "expires_in": expires_in,
        "usuario": {
            "user_id": usuario["user_id"],
            "nombre": usuario["nombre"],
            "rol": usuario["rol"],
            "tenant_id": usuario["tenant_id"],
            "empleado_id": usuario.get("empleado_id"),
            "debe_cambiar_password": bool(usuario.get("debe_cambiar_password", False)),
        },
    }
