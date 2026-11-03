import time

import jwt
import pytest

from src.common.security import create_token
from src.handlers import authorizer

ARN = "arn:aws:execute-api:us-east-1:123456789012:abc123/dev/GET/usuarios"
USR = {"user_id": "usr-000001", "tenant_id": "andina", "rol": "admin_rrhh", "empleado_id": "emp-000001"}


def test_token_valido_devuelve_allow_con_contexto():
    token, _ = create_token(USR)
    r = authorizer.handler({"authorizationToken": "Bearer " + token, "methodArn": ARN})
    assert r["principalId"] == "usr-000001"
    st = r["policyDocument"]["Statement"][0]
    assert st["Effect"] == "Allow"
    # comodín en método y ruta (la respuesta se cachea por token)
    assert st["Resource"] == "arn:aws:execute-api:us-east-1:123456789012:abc123/dev/*/*"
    assert r["context"] == {"tenant_id": "andina", "rol": "admin_rrhh",
                            "user_id": "usr-000001", "empleado_id": "emp-000001"}


def test_contexto_solo_tiene_strings_sin_none():
    token, _ = create_token(dict(USR, empleado_id=None))
    r = authorizer.handler({"authorizationToken": "Bearer " + token, "methodArn": ARN})
    assert r["context"]["empleado_id"] == ""
    assert all(isinstance(v, str) for v in r["context"].values())


@pytest.mark.parametrize("header", ["", "Bearer", "Bearer ", "Token abc", "Bearer basura.token.x"])
def test_token_ausente_o_malformado_es_unauthorized(header):
    with pytest.raises(Exception, match="Unauthorized"):
        authorizer.handler({"authorizationToken": header, "methodArn": ARN})


def test_token_firmado_con_otro_secreto_es_unauthorized():
    falso = jwt.encode({"sub": "x", "tenant_id": "pacifico", "rol": "admin_rrhh",
                        "exp": int(time.time()) + 600}, "otro-secreto-de-32-bytes-o-mas-1234567", algorithm="HS256")
    with pytest.raises(Exception, match="Unauthorized"):
        authorizer.handler({"authorizationToken": "Bearer " + falso, "methodArn": ARN})


def test_token_vencido_es_unauthorized():
    import os
    vencido = jwt.encode({"sub": "x", "tenant_id": "andina", "rol": "admin_rrhh", "exp": int(time.time()) - 10},
                         os.environ["JWT_SECRET"], algorithm="HS256")
    with pytest.raises(Exception, match="Unauthorized"):
        authorizer.handler({"authorizationToken": "Bearer " + vencido, "methodArn": ARN})
