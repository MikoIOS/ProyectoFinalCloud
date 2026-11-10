"""Único módulo que habla con DynamoDB."""
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from src.common.errors import Conflicto, NoEncontrado


def _table():
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None,
    )
    return dynamodb.Table(os.environ["TABLE_USUARIOS"])


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _code(e):
    return e.response.get("Error", {}).get("Code")


def get_by_email(tenant_id, email):
    resp = _table().query(
        IndexName="email-index",
        KeyConditionExpression=Key("tenant_id").eq(tenant_id) & Key("email").eq(email.lower()),
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def get_by_login_email(email):
    resp = _table().query(
        IndexName="login-email-index",
        KeyConditionExpression=Key("email").eq(email.lower()),
        Limit=2,
    )
    items = resp.get("Items", [])
    # Un correo ambiguo nunca debe iniciar sesión en una empresa arbitraria.
    if len(items) != 1 or resp.get("LastEvaluatedKey"):
        return None
    item = items[0]
    usuario = _table().get_item(
        Key={"tenant_id": item["tenant_id"], "user_id": item["user_id"]},
        ConsistentRead=True,
    ).get("Item")
    return usuario if usuario and usuario.get("email") == email.lower() else None


def get(tenant_id, user_id):
    return _table().get_item(Key={"tenant_id": tenant_id, "user_id": user_id}).get("Item")


def get_user_id_by_empleado(tenant_id, empleado_id):
    resp = _table().query(
        IndexName="empleado-index",
        KeyConditionExpression=Key("tenant_id").eq(tenant_id) & Key("empleado_id").eq(empleado_id),
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0]["user_id"] if items else None


def put_new(item):
    """Inserta solo si el user_id no existe. Lanza Conflicto si ya existe."""
    item = dict(item)
    item.setdefault("created_at", _now())
    item.setdefault("updated_at", item["created_at"])
    try:
        _table().put_item(Item=item, ConditionExpression="attribute_not_exists(user_id)")
    except ClientError as e:
        if _code(e) == "ConditionalCheckFailedException":
            raise Conflicto("El usuario ya existe")
        raise
    return item


def listar(tenant_id, limit, start_key=None, rol=None, activo=None):
    """Query por tenant (nunca Scan). Los filtros se aplican tras leer, así que se sigue
    leyendo páginas hasta completar `limit` o agotar la partición."""
    kwargs = {"KeyConditionExpression": Key("tenant_id").eq(tenant_id)}
    filt = None
    if rol:
        filt = Attr("rol").eq(rol)
    if activo is not None:
        f = Attr("activo").eq(activo)
        filt = f if filt is None else filt & f
    if filt is not None:
        kwargs["FilterExpression"] = filt
    kwargs["Limit"] = limit if filt is None else 500
    if start_key:
        kwargs["ExclusiveStartKey"] = start_key

    items, table = [], _table()
    while True:
        resp = table.query(**kwargs)
        for it in resp["Items"]:
            items.append(it)
            if len(items) == limit:
                # hay (posiblemente) más: continuar justo después del último devuelto
                return items, {"tenant_id": tenant_id, "user_id": it["user_id"]}
        last = resp.get("LastEvaluatedKey")
        if not last:
            return items, None
        kwargs["ExclusiveStartKey"] = last


def update(tenant_id, user_id, campos):
    """Actualiza campos de un usuario existente. NoEncontrado si no existe en ese tenant."""
    campos = dict(campos, updated_at=_now())
    names = {"#c%d" % i: k for i, k in enumerate(campos)}
    values = {":v%d" % i: v for i, v in enumerate(campos.values())}
    expr = "SET " + ", ".join("#c%d = :v%d" % (i, i) for i in range(len(campos)))
    try:
        resp = _table().update_item(
            Key={"tenant_id": tenant_id, "user_id": user_id},
            UpdateExpression=expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression="attribute_exists(user_id)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if _code(e) == "ConditionalCheckFailedException":
            raise NoEncontrado("Usuario no encontrado")
        raise
    return resp["Attributes"]
