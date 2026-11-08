import json
import os
import uuid
from datetime import datetime, timezone
import boto3
from boto3.dynamodb.conditions import Key

from common.auth import contexto

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])


def _resp(status, body):
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body, default=str)
    }


def crear(event, context):
    ctx = contexto(event)
    if not ctx:
        return _resp(401, {'error': 'No autenticado'})
    body = json.loads(event.get('body') or '{}')
    tenant_id = ctx.tenant_id
    vac_id = f"vac-{uuid.uuid4().hex[:8]}"
    item = {
        'tenant_id': tenant_id,
        'sk': f'VACANTE#{vac_id}',
        'vacante_id': vac_id,
        'titulo': body.get('titulo', 'Sin titulo'),
        'area': body.get('area', 'General'),
        'estado': 'ABIERTA',
        'fecha_publicacion': datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=item)
    return _resp(201, {**item, 'vacante_id': vac_id})


def _a_vacante(item):
    item = dict(item)
    sk = item.pop('sk', '')
    if 'vacante_id' not in item and sk.startswith('VACANTE#'):
        item['vacante_id'] = sk.split('#', 1)[1]
    return item


def listar(event, context):
    ctx = contexto(event)
    if not ctx:
        return _resp(401, {'error': 'No autenticado'})
    tenant_id = ctx.tenant_id
    r = table.query(
        KeyConditionExpression=Key('tenant_id').eq(tenant_id)
        & Key('sk').begins_with('VACANTE#')
    )
    return _resp(200, [_a_vacante(i) for i in r.get('Items', [])])
