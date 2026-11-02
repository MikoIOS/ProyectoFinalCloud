import json
import os
import uuid
from datetime import datetime, timezone
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
sns = boto3.client('sns')
table = dynamodb.Table(os.environ['TABLE_NAME'])
BUCKET = os.environ['CV_BUCKET']
TOPIC_ARN = os.environ['EVENTS_TOPIC_ARN']

ESTADOS_VALIDOS = {'RECIBIDO', 'ENTREVISTA', 'OFERTA', 'CONTRATADO', 'RECHAZADO'}


def _resp(status, body):
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body, default=str)
    }


def _publicar_evento(tipo, tenant_id, datos):
    event = {
        'tipo_evento': tipo,
        'tenant_id': tenant_id,
        'origen': 'ms-reclutamiento',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'datos': datos
    }
    sns.publish(
        TopicArn=TOPIC_ARN,
        Message=json.dumps(event),
        MessageAttributes={
            'tipo_evento': {'DataType': 'String', 'StringValue': tipo},
            'tenant_id': {'DataType': 'String', 'StringValue': tenant_id}
        }
    )


def crear(event, context):
    body = json.loads(event.get('body') or '{}')
    tenant_id = body.get('tenant_id', 'andina')
    vacante_id = body.get('vacante_id')
    if not vacante_id:
        return _resp(400, {'error': 'vacante_id requerido'})

    post_id = f"pos-{uuid.uuid4().hex[:8]}"
    cv_key = f"{tenant_id}/cvs/{post_id}.pdf"

    presigned_url = s3.generate_presigned_url(
        'put_object',
        Params={'Bucket': BUCKET, 'Key': cv_key, 'ContentType': 'application/pdf'},
        ExpiresIn=600
    )

    item = {
        'tenant_id': tenant_id,
        'sk': f'POSTULACION#{post_id}',
        'postulacion_id': post_id,
        'vacante_id': vacante_id,
        'nombre': body.get('nombre', ''),
        'email': body.get('email', ''),
        'cv_s3_key': cv_key,
        'estado': 'RECIBIDO',
        'fecha': datetime.now(timezone.utc).isoformat(),
    }
    table.put_item(Item=item)
    return _resp(201, {'postulacion': item, 'cv_upload_url': presigned_url})


def listar(event, context):
    vacante_id = event['pathParameters']['vacante_id']
    qs = event.get('queryStringParameters') or {}
    tenant_id = qs.get('tenant_id', 'andina')
    r = table.query(
        IndexName='vacante-index',
        KeyConditionExpression=Key('tenant_id').eq(tenant_id) & Key('vacante_id').eq(vacante_id)
    )
    return _resp(200, r.get('Items', []))


def actualizar_estado(event, context):
    post_id = event['pathParameters']['postulacion_id']
    body = json.loads(event.get('body') or '{}')
    tenant_id = body.get('tenant_id', 'andina')
    nuevo_estado = body.get('estado')

    if nuevo_estado not in ESTADOS_VALIDOS:
        return _resp(400, {'error': f'estado debe ser uno de {sorted(ESTADOS_VALIDOS)}'})

    r = table.update_item(
        Key={'tenant_id': tenant_id, 'sk': f'POSTULACION#{post_id}'},
        UpdateExpression='SET estado = :e, fecha_actualizacion = :f',
        ExpressionAttributeValues={
            ':e': nuevo_estado,
            ':f': datetime.now(timezone.utc).isoformat()
        },
        ReturnValues='ALL_NEW'
    )
    attrs = r['Attributes']

    if nuevo_estado == 'CONTRATADO':
        _publicar_evento('PostulanteContratado', tenant_id, {
            'postulacion_id': post_id,
            'vacante_id': attrs.get('vacante_id'),
            'nombre': attrs.get('nombre'),
            'email': attrs.get('email'),
        })

    return _resp(200, attrs)
