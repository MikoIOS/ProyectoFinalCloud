"""Único módulo que habla con DynamoDB."""
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from src.common.errors import Validacion


def ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resource():
    return boto3.resource(
        "dynamodb",
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None,
    )


def table():
    return _resource().Table(os.environ["TABLE_NAME"])


def empleados_table():
    return _resource().Table(os.environ["TABLE_EMPLEADOS"])


def _code(error):
    return error.response.get("Error", {}).get("Code")


def _limpiar(item):
    return {k: v for k, v in item.items() if v is not None}


# ------------------------------------------------------------------ planillas
def get_planilla(tenant_id, periodo):
    return table().get_item(Key={"tenant_id": tenant_id, "sk": "PLANILLA#" + periodo}).get("Item")


def put_planilla(item):
    item = dict(item)
    item.setdefault("actualizado_en", ahora())
    table().put_item(Item=_limpiar(item))
    return item


def update_planilla(tenant_id, periodo, campos, ejecucion_id=None):
    """Actualiza la planilla. Si se indica ejecucion_id, solo escribe si sigue siendo la ejecución vigente."""
    campos = dict(campos)
    sets, adds, names, values = [], [], {}, {}
    for i, (k, v) in enumerate(campos.items()):
        if k.startswith("add_"):
            nombre = k[4:]
            names["#a%d" % i] = nombre
            values[":a%d" % i] = v
            adds.append("#a%d :a%d" % (i, i))
        else:
            names["#s%d" % i] = k
            values[":s%d" % i] = v
            sets.append("#s%d = :s%d" % (i, i))
    expr = ""
    if sets:
        expr += "SET " + ", ".join(sets)
    if adds:
        expr += (" " if expr else "") + "ADD " + ", ".join(adds)
    if not expr:
        return True
    kwargs = {
        "Key": {"tenant_id": tenant_id, "sk": "PLANILLA#" + periodo},
        "UpdateExpression": expr,
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": values,
    }
    if ejecucion_id:
        kwargs["ConditionExpression"] = "attribute_exists(sk) AND ejecucion_id = :ejecucion"
        kwargs["ExpressionAttributeValues"][":ejecucion"] = ejecucion_id
    try:
        table().update_item(**kwargs)
        return True
    except ClientError as error:
        if _code(error) == "ConditionalCheckFailedException":
            return False
        raise


def query_planillas(tenant_id, limit, start_key=None):
    return _query(
        index="planilla-index",
        key_condition=Key("tenant_id").eq(tenant_id),
        limit=limit,
        start_key=start_key,
        scan_forward=False,
    )


# ------------------------------------------------------------------ nóminas
def get_nomina(tenant_id, nomina_id):
    return table().get_item(Key={"tenant_id": tenant_id, "sk": "NOMINA#" + nomina_id}).get("Item")


def put_nomina(item):
    table().put_item(Item=_limpiar(item))
    return item


def query_nominas_periodo(tenant_id, periodo, area, limit, start_key=None):
    filtro = None
    if area:
        from boto3.dynamodb.conditions import Attr
        filtro = Attr("area").eq(area)
    return _query(
        index="periodo-index",
        key_condition=Key("tenant_id").eq(tenant_id) & Key("periodo_empleado").begins_with(periodo + "#"),
        limit=limit,
        start_key=start_key,
        filter_expression=filtro,
    )


def query_nominas_empleado(tenant_id, empleado_id, limit, start_key=None):
    from boto3.dynamodb.conditions import Attr
    return _query(
        index="empleado-index",
        key_condition=Key("tenant_id").eq(tenant_id) & Key("empleado_periodo").begins_with(empleado_id + "#"),
        limit=limit,
        start_key=start_key,
        scan_forward=False,
        filter_expression=Attr("tipo").eq("NOMINA"),
    )


def borrar_nominas_periodo(tenant_id, periodo):
    """Borra las nóminas del periodo antes de recalcular. Las consulta por GSI, nunca con Scan."""
    eliminados = 0
    start_key = None
    while True:
        items, start_key = _query(
            index="periodo-index",
            key_condition=Key("tenant_id").eq(tenant_id) & Key("periodo_empleado").begins_with(periodo + "#"),
            limit=200,
            start_key=start_key,
        )
        if not items:
            break
        with table().batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={"tenant_id": item["tenant_id"], "sk": item["sk"]})
                eliminados += 1
        if not start_key:
            break
    return eliminados


def batch_put_nominas(items):
    with table().batch_writer() as batch:
        for item in items:
            batch.put_item(Item=_limpiar(item))


def batch_put_conceptos(items):
    with table().batch_writer() as batch:
        for item in items:
            batch.put_item(Item=_limpiar(item))


# ------------------------------------------------------------------ conceptos
def get_concepto(tenant_id, concepto_id):
    return table().get_item(Key={"tenant_id": tenant_id, "sk": "CONCEPTO#" + concepto_id}).get("Item")


def put_concepto(item):
    table().put_item(Item=_limpiar(item))
    return item


def query_conceptos_periodo(tenant_id, periodo, empleado_id=None, start_key=None, limit=200):
    filtro = None
    if empleado_id:
        from boto3.dynamodb.conditions import Attr
        filtro = Attr("empleado_id").eq(empleado_id)
    return _query(
        index="concepto-index",
        key_condition=Key("tenant_id").eq(tenant_id) & Key("periodo_concepto").begins_with(periodo + "#"),
        limit=limit,
        start_key=start_key,
        filter_expression=filtro,
    )


def existe_referencia(tenant_id, periodo, empleado_id, referencia):
    start_key = None
    while True:
        items, start_key = query_conceptos_periodo(tenant_id, periodo, empleado_id, start_key)
        if any(i.get("referencia") == referencia for i in items):
            return True
        if not start_key:
            return False


# ------------------------------------------------------------------ bandas
def query_bandas(tenant_id, limit=100, start_key=None):
    return _query(
        index="cargo-index",
        key_condition=Key("tenant_id").eq(tenant_id),
        limit=limit,
        start_key=start_key,
    )


def put_banda(item):
    table().put_item(Item=_limpiar(item))
    return item


# ------------------------------------------------------------------ liquidación
def get_liquidacion(tenant_id, empleado_id):
    return table().get_item(Key={"tenant_id": tenant_id, "sk": "LIQUIDACION#" + empleado_id}).get("Item")


def put_liquidacion(item):
    table().put_item(Item=_limpiar(item))
    return item


# ------------------------------------------------------------------ empleados (lectura)
def get_empleado(tenant_id, empleado_id):
    return empleados_table().get_item(Key={"tenant_id": tenant_id, "empleado_id": empleado_id}).get("Item")


def listar_empleados(tenant_id):
    """Query por partición de tenant. hcm-empleados usa (tenant_id, empleado_id)."""
    kwargs = {"KeyConditionExpression": Key("tenant_id").eq(tenant_id)}
    items, tabla = [], empleados_table()
    while True:
        resp = tabla.query(**kwargs)
        items.extend(resp.get("Items", []))
        if not resp.get("LastEvaluatedKey"):
            return items
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def contar_activos(tenant_id):
    kwargs = {
        "IndexName": "estado-index",
        "KeyConditionExpression": Key("tenant_id").eq(tenant_id) & Key("estado").eq("ACTIVO"),
        "Select": "COUNT",
    }
    total, tabla = 0, empleados_table()
    while True:
        resp = tabla.query(**kwargs)
        total += resp.get("Count", 0)
        if not resp.get("LastEvaluatedKey"):
            return total
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


# ------------------------------------------------------------------ query genérica
def _query(index, key_condition, limit, start_key=None, filter_expression=None, scan_forward=True):
    kwargs = {
        "IndexName": index,
        "KeyConditionExpression": key_condition,
        "Limit": max(limit * 4, 100) if filter_expression else limit,
        "ScanIndexForward": scan_forward,
    }
    if filter_expression is not None:
        kwargs["FilterExpression"] = filter_expression
    if start_key:
        kwargs["ExclusiveStartKey"] = start_key

    items, tabla = [], table()
    while True:
        try:
            resp = tabla.query(**kwargs)
        except ClientError as e:
            if _code(e) == "ValidationException":
                raise Validacion("next_token inválido")
            raise
        for item in resp.get("Items", []):
            items.append(item)
            if len(items) == limit:
                # El token debe continuar justo después del último item entregado.
                return items, _token_desde(item, index, resp.get("LastEvaluatedKey"))
        last = resp.get("LastEvaluatedKey")
        if not last:
            return items, None
        kwargs["ExclusiveStartKey"] = last


def _token_desde(item, index, last_evaluated):
    """Construye una ExclusiveStartKey equivalente a continuar después de `item`.

    En un GSI, DynamoDB exige incluir también la clave primaria completa de la tabla
    (tenant_id + sk), no solo las claves del índice.
    """
    base = {"tenant_id": item["tenant_id"], "sk": item["sk"]}
    if index == "empleado-index":
        base["empleado_periodo"] = item["empleado_periodo"]
    elif index == "periodo-index":
        base["periodo_empleado"] = item["periodo_empleado"]
    elif index == "concepto-index":
        base["periodo_concepto"] = item["periodo_concepto"]
    elif index == "planilla-index":
        base["periodo_planilla"] = item["periodo_planilla"]
    elif index == "cargo-index":
        base["banda_cargo"] = item["banda_cargo"]
    else:
        return last_evaluated
    return base
