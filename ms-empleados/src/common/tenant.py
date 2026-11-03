"""Contexto de autenticación que inyecta el Authorizer.

El tenant SIEMPRE sale de aquí, nunca del body ni de la URL.
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
    """Devuelve el Ctx del request. Si se pasa `roles`, exige que el rol esté en esa lista (403 si no)."""
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
