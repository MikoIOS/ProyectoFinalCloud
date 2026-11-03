import os

import boto3
import pytest
from moto import mock_aws

from scripts.tabla import crear_tabla
from src.common.security import hash_password

os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ["TABLE_USUARIOS"] = "hcm-usuarios"
os.environ["JWT_SECRET"] = "secreto-de-pruebas-con-al-menos-32-bytes-1234"
os.environ.pop("DYNAMODB_ENDPOINT", None)

PWD = "Demo1234!"


def usuario(tenant, n, email, rol="empleado", activo=True, pwd_hash=None):
    return {"tenant_id": tenant, "user_id": "usr-%06d" % n, "email": email,
            "password_hash": pwd_hash, "nombre": "Usuario %d" % n, "rol": rol,
            "activo": activo, "empleado_id": "emp-%06d" % n}


@pytest.fixture
def tabla():
    with mock_aws():
        t = crear_tabla(boto3.resource("dynamodb", region_name="us-east-1"))
        h = hash_password(PWD)
        t.put_item(Item=usuario("andina", 1, "maria@andina.pe", "admin_rrhh", pwd_hash=h))
        t.put_item(Item=usuario("pacifico", 1, "maria@pacifico.pe", "gerente", pwd_hash=h))
        t.put_item(Item=usuario("andina", 2, "luis@andina.pe", activo=False, pwd_hash=h))
        t.put_item(Item=usuario("andina", 3, "ana@andina.pe", "empleado", pwd_hash=h))
        yield t


def http(tenant="andina", rol="admin_rrhh", user_id="usr-000001", empleado_id="emp-000001",
         body=None, id=None, qs=None):
    """Simula el evento que API Gateway entrega al Lambda tras el Authorizer."""
    import json as _json
    ev = {"requestContext": {"authorizer": {"tenant_id": tenant, "rol": rol, "user_id": user_id,
                                            "principalId": user_id, "empleado_id": empleado_id}}}
    if body is not None:
        ev["body"] = body if isinstance(body, str) else _json.dumps(body)
    if id:
        ev["pathParameters"] = {"id": id}
    if qs:
        ev["queryStringParameters"] = qs
    return ev


def respuesta(r):
    import json as _json
    return r["statusCode"], _json.loads(r["body"])
