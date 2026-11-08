"""Contexto que inyecta el Lambda Authorizer compartido.

El tenant SIEMPRE sale del token, nunca del body ni de la URL.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Ctx:
    tenant_id: str
    rol: str
    user_id: str
    empleado_id: str = ""


def contexto(event):
    auth = (event.get("requestContext") or {}).get("authorizer") or {}
    if not auth.get("tenant_id"):
        return None
    return Ctx(
        tenant_id=auth["tenant_id"],
        rol=auth.get("rol", ""),
        user_id=auth.get("user_id") or auth.get("principalId", ""),
        empleado_id=auth.get("empleado_id") or "",
    )
