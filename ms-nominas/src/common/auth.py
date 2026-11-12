"""Contexto de autenticación inyectado por el Lambda Authorizer compartido.

El tenant SIEMPRE sale del token, nunca del body ni de la URL.
"""
from dataclasses import dataclass
from typing import Optional

from src.common.errors import NoAutenticado, Prohibido


@dataclass(frozen=True)
class Ctx:
    tenant_id: str
    rol: str
    user_id: str
    empleado_id: Optional[str] = None


def contexto(event, roles=None):
    auth = (event.get("requestContext") or {}).get("authorizer") or {}
    if not auth.get("tenant_id"):
        raise NoAutenticado("Sin contexto de autenticación")
    ctx = Ctx(
        tenant_id=auth["tenant_id"],
        rol=auth.get("rol", ""),
        user_id=auth.get("user_id") or auth.get("principalId", ""),
        empleado_id=auth.get("empleado_id") or None,
    )
    if roles and ctx.rol not in roles:
        raise Prohibido("No tienes permisos para esta operación")
    return ctx


def propio_o_supervisor(ctx, empleado_id, mensaje="Solo puedes ver tus propios datos"):
    """admin_rrhh y gerente pueden ver a cualquiera; el resto solo su propio empleado_id."""
    if ctx.rol in ("admin_rrhh", "gerente"):
        return
    if not ctx.empleado_id or ctx.empleado_id != empleado_id:
        raise Prohibido(mensaje)
