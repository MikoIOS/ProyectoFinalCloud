"""Único módulo que habla con DynamoDB."""
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from src.common.errors import Conflicto, NoEncontrado, Validacion

SK_DE = {"area-index": "area", "estado-index": "estado", "jefe-index": "jefe_id"}


def _table():
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None,
    )
    return dynamodb.Table(os.environ["TABLE_EMPLEADOS"])


def ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _code(e):
    return e.response.get("Error", {}).get("Code")


def get(tenant_id, empleado_id):
    return _table().get_item(Key={"tenant_id": tenant_id, "empleado_id": empleado_id}).get("Item")


def get_id_por_documento(tenant_id, documento):
    resp = _table().query(
        IndexName="documento-index",
        KeyConditionExpression=Key("tenant_id").eq(tenant_id) & Key("documento").eq(documento),
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0]["empleado_id"] if items else None


def put_new(item):
    """Inserta solo si el empleado_id no existe. Lanza Conflicto si ya existe."""
    item = dict(item)
    item.setdefault("created_at", ahora())
    item.setdefault("updated_at", item["created_at"])
    try:
        _table().put_item(Item=item, ConditionExpression="attribute_not_exists(empleado_id)")
    except ClientError as e:
        if _code(e) == "ConditionalCheckFailedException":
            raise Conflicto("El empleado ya existe")
        raise
    return item


def _clave(item, index):
    base = {"tenant_id": item["tenant_id"], "empleado_id": item["empleado_id"]}
    if index:
        base[SK_DE[index]] = item[SK_DE[index]]
    return base


def consultar(tenant_id, limit, start_key=None, index=None, valor=None, estado=None):
    """Query por tenant (nunca Scan), opcionalmente por GSI. El filtro de estado se aplica tras leer,
    así que se siguen leyendo páginas hasta completar `limit` o agotar la partición."""
    if start_key:  # el token debe corresponder a este mismo índice
        esperadas = {"tenant_id", "empleado_id"} | ({SK_DE[index]} if index else set())
        if set(start_key) != esperadas:
            raise Validacion("next_token inválido")
    cond = Key("tenant_id").eq(tenant_id)
    if index:
        cond = cond & Key(SK_DE[index]).eq(valor)
    kwargs = {"KeyConditionExpression": cond}
    if index:
        kwargs["IndexName"] = index
    if estado and index != "estado-index":
        kwargs["FilterExpression"] = Attr("estado").eq(estado)
        kwargs["Limit"] = 500
    else:
        kwargs["Limit"] = limit
    if start_key:
        kwargs["ExclusiveStartKey"] = start_key

    items, table = [], _table()
    while True:
        try:
            resp = table.query(**kwargs)
        except ClientError as e:
            if _code(e) == "ValidationException":
                raise Validacion("next_token inválido")
            raise
        for it in resp["Items"]:
            items.append(it)
            if len(items) == limit:
                return items, _clave(it, index)
        last = resp.get("LastEvaluatedKey")
        if not last:
            return items, None
        kwargs["ExclusiveStartKey"] = last


def recorrer_area_estado(tenant_id):
    """Para /resumen: recorre area-index leyendo solo area y estado (una pasada, sin Scan)."""
    kwargs = {"IndexName": "area-index", "KeyConditionExpression": Key("tenant_id").eq(tenant_id),
              "ProjectionExpression": "#a, #e", "ExpressionAttributeNames": {"#a": "area", "#e": "estado"}}
    table = _table()
    while True:
        resp = table.query(**kwargs)
        for it in resp["Items"]:
            yield it
        if not resp.get("LastEvaluatedKey"):
            return
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def update(tenant_id, empleado_id, campos, remover=(), estado_actual=None):
    """Actualiza campos de un empleado existente (y quita los de `remover`).
    NoEncontrado si no existe en ese tenant; Conflicto si `estado_actual` ya no coincide."""
    campos = dict(campos, updated_at=ahora())
    names, values, sets, rems = {}, {}, [], []
    for i, (k, v) in enumerate(campos.items()):
        names["#s%d" % i] = k
        values[":s%d" % i] = v
        sets.append("#s%d = :s%d" % (i, i))
    for i, k in enumerate(remover):
        names["#r%d" % i] = k
        rems.append("#r%d" % i)
    expr = "SET " + ", ".join(sets) + ((" REMOVE " + ", ".join(rems)) if rems else "")
    cond = "attribute_exists(empleado_id)"
    if estado_actual:
        names["#est"] = "estado"
        values[":prev"] = estado_actual
        cond += " AND #est = :prev"
    try:
        resp = _table().update_item(
            Key={"tenant_id": tenant_id, "empleado_id": empleado_id},
            UpdateExpression=expr, ExpressionAttributeNames=names, ExpressionAttributeValues=values,
            ConditionExpression=cond, ReturnValues="ALL_NEW")
    except ClientError as e:
        if _code(e) == "ConditionalCheckFailedException":
            if estado_actual and get(tenant_id, empleado_id):
                raise Conflicto("El estado del empleado cambió; vuelve a consultarlo e inténtalo de nuevo")
            raise NoEncontrado("Empleado no encontrado")
        raise
    return resp["Attributes"]
