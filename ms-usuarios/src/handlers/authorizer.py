"""Lambda Authorizer (type: token) compartido por todos los microservicios.

Valida el JWT y entrega tenant_id, rol, user_id y empleado_id al Lambda destino.
La policy usa comodín en método y ruta porque API Gateway cachea el resultado por token.
"""
import logging

from src.common.errors import NoAutenticado
from src.common.security import decode_token

log = logging.getLogger()


def _policy(principal, effect, method_arn, context=None):
    partes = method_arn.split(":")                   # arn:aws:execute-api:region:cuenta:api/stage/METODO/ruta
    api_id, stage = partes[5].split("/")[:2]
    recurso = ":".join(partes[:5]) + ":%s/%s/*/*" % (api_id, stage)
    return {
        "principalId": principal,
        "policyDocument": {"Version": "2012-10-17", "Statement": [
            {"Effect": effect, "Action": "execute-api:Invoke", "Resource": recurso}]},
        "context": context or {},
    }


def handler(event, context=None):
    header = event.get("authorizationToken") or ""
    if not header.startswith("Bearer ") or len(header) < 8:
        raise Exception("Unauthorized")              # API Gateway responde 401
    try:
        claims = decode_token(header[7:].strip())
    except NoAutenticado:
        raise Exception("Unauthorized")
    if not claims.get("tenant_id") or not claims.get("sub"):
        raise Exception("Unauthorized")
    ctx = {"tenant_id": claims["tenant_id"], "rol": claims.get("rol", ""),
           "user_id": claims["sub"], "empleado_id": claims.get("empleado_id") or ""}
    return _policy(claims["sub"], "Allow", event["methodArn"], ctx)
