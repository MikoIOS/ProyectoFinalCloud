import json
import os
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

from scripts.tabla import crear_tabla

os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ["TABLE_EMPLEADOS"] = "hcm-empleados"
os.environ["TOPIC_ARN"] = "arn:aws:sns:us-east-1:123456789012:hcm-eventos"
os.environ.pop("DYNAMODB_ENDPOINT", None)


def emp(tenant, n, nombres, apellidos, area, estado="ACTIVO", jefe=None, salario="4000.00", **extra):
    item = {"tenant_id": tenant, "empleado_id": "emp-%06d" % n, "nombres": nombres, "apellidos": apellidos,
            "documento": "1000%04d" % n, "email": "%s%d@%s.pe" % (nombres.lower(), n, tenant), "area": area,
            "cargo": "Cargo %d" % n, "fecha_ingreso": "2023-03-15", "salario_base": Decimal(salario),
            "estado": estado, "telefono": "900000%03d" % n, "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z"}
    if jefe:
        item["jefe_id"] = "emp-%06d" % jefe
    item.update(extra)
    return item


@pytest.fixture
def publicados(monkeypatch):
    """Captura los eventos publicados en lugar de enviarlos a SNS."""
    lista = []

    def falso(tipo, tenant_id, datos, origen):
        lista.append({"tipo_evento": tipo, "tenant_id": tenant_id, "datos": json.loads(json.dumps(datos, default=float)),
                      "origen": origen})

    monkeypatch.setattr("src.common.events.publish_event", falso)
    return lista


@pytest.fixture
def tabla(publicados):
    with mock_aws():
        t = crear_tabla(boto3.resource("dynamodb", region_name="us-east-1"))
        for it in (
            emp("andina", 1, "Ana", "Directora", "Recursos Humanos", salario="9000.00"),
            emp("andina", 2, "Luis", "Ramos", "Tecnología", jefe=1),
            emp("andina", 3, "Rosa", "Díaz", "Tecnología", estado="VACACIONES", jefe=2),
            emp("andina", 4, "Pedro", "Cesado", "Ventas", estado="CESADO", jefe=1, fecha_cese="2026-05-01"),
            emp("andina", 5, "Mario", "Quispe", "Ventas", jefe=1),
            emp("pacifico", 1, "Paola", "Gerente", "Operaciones"),   # mismo id y mismo documento que andina/1
        ):
            t.put_item(Item=it)
        yield t


def http(tenant="andina", rol="admin_rrhh", user_id="usr-000001", empleado_id="emp-000001",
         body=None, id=None, qs=None):
    """Simula el evento que API Gateway entrega al Lambda tras el Authorizer."""
    ev = {"requestContext": {"authorizer": {"tenant_id": tenant, "rol": rol, "user_id": user_id,
                                            "principalId": user_id, "empleado_id": empleado_id}}}
    if body is not None:
        ev["body"] = body if isinstance(body, str) else json.dumps(body)
    if id:
        ev["pathParameters"] = {"id": id}
    if qs:
        ev["queryStringParameters"] = qs
    return ev


def respuesta(r):
    return r["statusCode"], json.loads(r["body"])


NUEVO = {"nombres": "Carla", "apellidos": "Soto", "documento": "71234567", "email": "Carla.Soto@andina.pe",
         "area": "Tecnología", "cargo": "Analista de Datos", "fecha_ingreso": "2026-11-03", "salario_base": 4200.5,
         "jefe_id": "emp-000002"}
