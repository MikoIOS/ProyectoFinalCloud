import json
import os
import uuid
from datetime import datetime, timezone
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])


def _resp(status, body):
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body, default=str)
    }


def crear(event, context):
    body = json.loads(event.get('body') or '{}')
    tenant_id = body.get('tenant_id', 'andina')
    vac_id = f"vac-{uuid.uuid4().hex[:8]}"
    item = {
        'tenant_id': tenant_id,
        'sk': f'VACANTE#{vac_id}',
        'titulo': body.get('titulo', 'Sin titulo'),
        'area': body.get('area', 'General'),
        'estado': 'ABIERTA',
        'fecha_publicacion': datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=item)
    return _resp(201, {**item, 'vacante_id': vac_id})


def listar(event, context):
    qs = event.get('queryStringParameters') or {}
    tenant_id = qs.get('tenant_id', 'andina')
    r = table.query(
        KeyConditionExpression=Key('tenant_id').eq(tenant_id)
        & Key('sk').begins_with('VACANTE#')
    )
    return _resp(200, r.get('Items', []))
