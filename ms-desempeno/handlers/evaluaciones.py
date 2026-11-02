import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
table = dynamodb.Table(os.environ['TABLE_NAME'])
TOPIC_ARN = os.environ['EVENTS_TOPIC_ARN']

ESTADOS = {'PENDIENTE', 'EN_PROGRESO', 'COMPLETADA'}


def _enc(o):
    if isinstance(o, Decimal):
        return float(o)
    return str(o)


def _resp(status, body):
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body, default=_enc)
    }


def _formato_email_evaluacion(datos, tenant_id, fecha):
    return f"""⭐ Evaluación de desempeño completada

════════════════════════════════════
📊 DETALLES DE LA EVALUACIÓN
════════════════════════════════════

👤 Empleado:     {datos.get('empleado_id', '-')}
👔 Evaluador:    {datos.get('evaluador_id', '-')}
📅 Periodo:      {datos.get('periodo', '-')}
🎯 Puntaje:      {datos.get('puntaje', '-')} / 5.0
🏢 Tenant:       {tenant_id}

🆔 Evaluación:   {datos.get('evaluacion_id', '-')}
⏰ Fecha:        {fecha}

════════════════════════════════════
Fuente: ms-desempeno | HCM SaaS Grupo 2
"""


def _publicar_evento(tipo, tenant_id, datos):
    ahora_utc = datetime.now(timezone.utc)
    ts = ahora_utc.isoformat()
    fecha_bonita = ahora_utc.astimezone(timezone(timedelta(hours=-5))).strftime('%d/%m/%Y %H:%M:%S') + ' (Lima)'
    event = {
        'tipo_evento': tipo,
        'tenant_id': tenant_id,
        'origen': 'ms-desempeno',
        'timestamp': ts,
        'datos': datos
    }
    sns.publish(
        TopicArn=TOPIC_ARN,
        Subject=f'[HCM/{tenant_id}] {tipo}',
        Message=json.dumps({
            'default': json.dumps(event, default=_enc),
            'sqs': json.dumps(event, default=_enc),
            'email': _formato_email_evaluacion(datos, tenant_id, fecha_bonita)
        }),
        MessageStructure='json',
        MessageAttributes={
            'tipo_evento': {'DataType': 'String', 'StringValue': tipo},
            'tenant_id': {'DataType': 'String', 'StringValue': tenant_id}
        }
    )


def crear(event, context):
    body = json.loads(event.get('body') or '{}', parse_float=Decimal)
    tenant_id = body.get('tenant_id', 'andina')
    empleado_id = body.get('empleado_id')
    if not empleado_id:
        return _resp(400, {'error': 'empleado_id requerido'})

    eva_id = f"eva-{uuid.uuid4().hex[:8]}"
    item = {
        'tenant_id': tenant_id,
        'sk': eva_id,
        'evaluacion_id': eva_id,
        'empleado_id': empleado_id,
        'evaluador_id': body.get('evaluador_id', ''),
        'periodo': body.get('periodo', ''),
        'puntaje': body.get('puntaje', Decimal('0')),
        'competencias': body.get('competencias', []),
        'objetivos': body.get('objetivos', []),
        'comentarios': body.get('comentarios', ''),
        'estado': 'PENDIENTE',
        'fecha_creacion': datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=item)
    return _resp(201, item)


def listar(event, context):
    qs = event.get('queryStringParameters') or {}
    tenant_id = qs.get('tenant_id', 'andina')
    empleado_id = qs.get('empleado')
    if not empleado_id:
        return _resp(400, {'error': 'query param "empleado" requerido'})

    r = table.query(
        IndexName='empleado-index',
        KeyConditionExpression=Key('tenant_id').eq(tenant_id) & Key('empleado_id').eq(empleado_id),
        FilterExpression=Attr('sk').begins_with('eva-')
    )
    return _resp(200, r.get('Items', []))


def actualizar(event, context):
    eva_id = event['pathParameters']['evaluacion_id']
    body = json.loads(event.get('body') or '{}', parse_float=Decimal)
    tenant_id = body.get('tenant_id', 'andina')

    campos_actualizables = ['puntaje', 'competencias', 'objetivos', 'comentarios', 'estado']
    sets = []
    vals = {}
    names = {}
    for c in campos_actualizables:
        if c in body:
            if c == 'estado' and body[c] not in ESTADOS:
                return _resp(400, {'error': f'estado debe ser uno de {sorted(ESTADOS)}'})
            sets.append(f'#{c} = :{c}')
            vals[f':{c}'] = body[c]
            names[f'#{c}'] = c

    if not sets:
        return _resp(400, {'error': 'nada que actualizar'})

    sets.append('#fa = :fa')
    vals[':fa'] = datetime.now(timezone.utc).isoformat()
    names['#fa'] = 'fecha_actualizacion'

    r = table.update_item(
        Key={'tenant_id': tenant_id, 'sk': eva_id},
        UpdateExpression='SET ' + ', '.join(sets),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=vals,
        ReturnValues='ALL_NEW'
    )
    attrs = r['Attributes']

    if attrs.get('estado') == 'COMPLETADA':
        _publicar_evento('EvaluacionCompletada', tenant_id, {
            'evaluacion_id': eva_id,
            'empleado_id': attrs.get('empleado_id'),
            'evaluador_id': attrs.get('evaluador_id'),
            'periodo': attrs.get('periodo'),
            'puntaje': attrs.get('puntaje'),
        })

    return _resp(200, attrs)
