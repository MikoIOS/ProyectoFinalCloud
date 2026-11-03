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
    empleado_id = body.get('empleado_id')
    tarea = body.get('tarea')
    if not empleado_id or not tarea:
        return _resp(400, {'error': 'empleado_id y tarea requeridos'})

    onb_id = f"onb-{uuid.uuid4().hex[:8]}"
    item = {
        'tenant_id': tenant_id,
        'sk': f'ONBOARDING#{empleado_id}#{onb_id}',
        'onboarding_id': onb_id,
        'empleado_id': empleado_id,
        'tarea': tarea,
        'completada': False,
        'fecha_creacion': datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=item)
    return _resp(201, item)


def listar(event, context):
    empleado_id = event['pathParameters']['empleado_id']
    qs = event.get('queryStringParameters') or {}
    tenant_id = qs.get('tenant_id', 'andina')
    r = table.query(
        KeyConditionExpression=Key('tenant_id').eq(tenant_id)
        & Key('sk').begins_with(f'ONBOARDING#{empleado_id}#')
    )
    return _resp(200, r.get('Items', []))


def completar(event, context):
    empleado_id = event['pathParameters']['empleado_id']
    onb_id = event['pathParameters']['onboarding_id']
    qs = event.get('queryStringParameters') or {}
    tenant_id = qs.get('tenant_id', 'andina')

    r = table.update_item(
        Key={'tenant_id': tenant_id, 'sk': f'ONBOARDING#{empleado_id}#{onb_id}'},
        UpdateExpression='SET completada = :c, fecha_completada = :f',
        ExpressionAttributeValues={
            ':c': True,
            ':f': datetime.now(timezone.utc).isoformat()
        },
        ReturnValues='ALL_NEW'
    )
    return _resp(200, r['Attributes'])
