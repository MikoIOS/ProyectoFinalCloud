import json
import os
import uuid
from datetime import datetime, timezone
import boto3

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
    de_empleado = body.get('de_empleado_id')
    para_empleado = body.get('para_empleado_id')
    mensaje = body.get('mensaje')
    if not de_empleado or not para_empleado or not mensaje:
        return _resp(400, {'error': 'de_empleado_id, para_empleado_id y mensaje requeridos'})

    rec_id = f"rec-{uuid.uuid4().hex[:8]}"
    item = {
        'tenant_id': tenant_id,
        'sk': rec_id,
        'reconocimiento_id': rec_id,
        'empleado_id': para_empleado,
        'de_empleado_id': de_empleado,
        'mensaje': mensaje,
        'fecha': datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=item)
    return _resp(201, item)
