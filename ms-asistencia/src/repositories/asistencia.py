"""DynamoDB: lecturas consistentes y control optimista por empleado."""
import base64
import json
import os

import boto3
from boto3.dynamodb.conditions import Attr, Key
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from src.common.errors import Conflicto, NoEncontrado, Validacion


def tabla():
    return boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])


def get(tenant, sk):
    return tabla().get_item(Key={'tenant_id': tenant, 'sk': sk}, ConsistentRead=True).get('Item')


def empleado(tenant, emp):
    item = boto3.resource('dynamodb').Table(os.environ['TABLE_EMPLEADOS']).get_item(
        Key={'tenant_id': tenant, 'empleado_id': emp}, ConsistentRead=True).get('Item')
    if not item:
        raise NoEncontrado('Empleado no encontrado')
    return item


def ausencias(tenant, emp):
    items, key = [], None
    while True:
        args = {'KeyConditionExpression': Key('tenant_id').eq(tenant) & Key('sk').begins_with(f'EMP#{emp}#AUS#'),
                'ConsistentRead': True}
        if key:
            args['ExclusiveStartKey'] = key
        res = tabla().query(**args)
        items.extend(res['Items'])
        key = res.get('LastEvaluatedKey')
        if not key:
            return items


def guardar_ausencia(item, version):
    # Todas las escrituras de ausencias compiten por la misma versión del empleado.
    control = {'tenant_id': item['tenant_id'], 'sk': f"EMP#{item['empleado_id']}#CONTROL",
               'version': version + 1}
    serial = TypeSerializer()
    encode = lambda value: {k: serial.serialize(v) for k, v in value.items()}
    try:
        boto3.client('dynamodb').transact_write_items(TransactItems=[
            {'Put': {'TableName': os.environ['TABLE_NAME'], 'Item': encode(control),
                     'ConditionExpression': 'attribute_not_exists(#v) OR #v = :v',
                     'ExpressionAttributeNames': {'#v': 'version'},
                     'ExpressionAttributeValues': {':v': serial.serialize(version)}}},
            {'Put': {'TableName': os.environ['TABLE_NAME'], 'Item': encode(item)}}])
    except ClientError as error:
        if error.response['Error']['Code'] == 'TransactionCanceledException':
            raise Conflicto('La asistencia cambió durante la operación; vuelve a intentarlo') from error
        raise
    return item


def version(tenant, emp):
    return int((get(tenant, f'EMP#{emp}#CONTROL') or {}).get('version', 0))


def listar(tenant, clase, qs, emp=None, pendientes=False, aprobador=None):
    try:
        limit = int(qs.get('limit', 50))
        if not 1 <= limit <= 200:
            raise ValueError
    except (ValueError, TypeError):
        raise Validacion('limit debe ser un entero entre 1 y 200')
    prefix = f'EMP#{emp}#{clase}#' if emp else 'EMP#'
    args = {'KeyConditionExpression': Key('tenant_id').eq(tenant) & Key('sk').begins_with(prefix),
            'FilterExpression': Attr('clase').eq(clase), 'Limit': limit, 'ConsistentRead': True}
    if pendientes:
        args['FilterExpression'] &= Attr('estado').eq('PENDIENTE')
    if aprobador:
        args['FilterExpression'] &= Attr('aprobador_id').eq(aprobador)
    for field in ('estado', 'tipo', 'fecha'):
        if qs.get(field):
            args['FilterExpression'] &= Attr(field).eq(qs[field])
    if qs.get('next_token'):
        try:
            key = json.loads(base64.urlsafe_b64decode(qs['next_token']))
            if (set(key) != {'tenant_id', 'sk'} or key['tenant_id'] != tenant
                    or not isinstance(key['sk'], str) or not key['sk'].startswith(prefix)):
                raise ValueError
            args['ExclusiveStartKey'] = key
        except (ValueError, TypeError, KeyError):
            raise Validacion('next_token inválido')
    res = tabla().query(**args)
    key = res.get('LastEvaluatedKey')
    return {'items': res['Items'], 'next_token': base64.urlsafe_b64encode(json.dumps(key).encode()).decode() if key else None}
