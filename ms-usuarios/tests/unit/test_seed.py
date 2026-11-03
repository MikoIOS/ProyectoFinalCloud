import boto3
from boto3.dynamodb.conditions import Key

from scripts.seed_usuarios import sembrar
from scripts.tabla import crear_tabla
from moto import mock_aws


def test_seed_pequeno_respeta_la_convencion():
    with mock_aws():
        t = crear_tabla(boto3.resource("dynamodb", region_name="us-east-1"))
        total = sembrar(t, ["andina", "pacifico"], 100, "hash", log=lambda *_: None)
        assert total == 200
        items = t.query(KeyConditionExpression=Key("tenant_id").eq("andina"))["Items"]
        assert len(items) == 100
        assert all(i["tenant_id"] == "andina" for i in items)
        por_id = {i["user_id"]: i for i in items}
        assert por_id["usr-000001"]["rol"] == "admin_rrhh"
        assert por_id["usr-000001"]["email"] == "admin@andina.pe"
        assert por_id["usr-000040"]["activo"] is False
        assert por_id["usr-000045"]["empleado_id"] == "emp-000045"
        # emails únicos dentro del tenant
        assert len({i["email"] for i in items}) == 100
