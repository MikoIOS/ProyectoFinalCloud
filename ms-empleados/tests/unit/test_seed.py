import boto3
from boto3.dynamodb.conditions import Key
from moto import mock_aws

from scripts.seed_empleados import sembrar
from scripts.tabla import crear_tabla


def traer(t, tenant):
    items, kw = [], {"KeyConditionExpression": Key("tenant_id").eq(tenant)}
    while True:
        r = t.query(**kw)
        items += r["Items"]
        if "LastEvaluatedKey" not in r:
            return items
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def test_seed_respeta_la_convencion_y_la_jerarquia():
    with mock_aws():
        t = crear_tabla(boto3.resource("dynamodb", region_name="us-east-1"))
        assert sembrar(t, ["andina", "pacifico"], 400, log=lambda *_: None) == 800
        items = traer(t, "andina")
        assert len(items) == 400 and all(i["tenant_id"] == "andina" for i in items)
        por_id = {i["empleado_id"]: i for i in items}

        assert por_id["emp-000001"]["email"] == "admin@andina.pe" and "jefe_id" not in por_id["emp-000001"]
        assert por_id["emp-000002"]["email"] == "empleado@andina.pe"
        assert por_id["emp-000040"]["estado"] == "CESADO" and "fecha_cese" in por_id["emp-000040"]
        assert por_id["emp-000022"]["estado"] == "VACACIONES"
        assert por_id["emp-000045"]["estado"] == "ACTIVO"

        assert len({i["documento"] for i in items}) == 400                  # único por tenant
        assert len({i["email"] for i in items}) == 400
        for i in items:                                                     # jerarquía: jefe existe, no cesado, sin ciclos
            if "jefe_id" in i:
                jefe = por_id[i["jefe_id"]]
                assert jefe["estado"] != "CESADO" and jefe["empleado_id"] < i["empleado_id"]
        assert all(i["fecha_cese"] >= i["fecha_ingreso"] for i in items if i["estado"] == "CESADO")
