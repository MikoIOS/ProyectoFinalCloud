import hashlib
import json
import os
import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
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


_SALARIO_POR_DEFECTO = Decimal("3000")


def _decimal(valor, defecto=_SALARIO_POR_DEFECTO):
    if valor in (None, ""):
        return defecto
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return defecto


def _documento_de_respaldo(post_id):
    """Documento determinista de 8 dígitos para contrataciones sin documento (demo)."""
    return str(int(hashlib.sha1(post_id.encode()).hexdigest(), 16) % 100_000_000).zfill(8)


def _vacante(tenant_id, vacante_id):
    if not vacante_id:
        return {}
    r = table.get_item(Key={"tenant_id": tenant_id, "sk": f"VACANTE#{vacante_id}"})
    return r.get("Item") or {}


def _datos_contratacion(tenant_id, attrs, post_id):
    """Completa PostulanteContratado con los campos que exige ms-empleados."""
    nombre = (attrs.get("nombre") or "").strip()
    partes = nombre.split(" ", 1)
    vacante = _vacante(tenant_id, attrs.get("vacante_id"))
    return {
        "postulacion_id": post_id,
        "vacante_id": attrs.get("vacante_id"),
        "nombre": nombre,
        "nombres": attrs.get("nombres") or partes[0] or "Candidato",
        "apellidos": attrs.get("apellidos") or (partes[1] if len(partes) > 1 else "Sin apellidos"),
        "email": attrs.get("email"),
        "documento": str(attrs.get("documento") or _documento_de_respaldo(post_id)),
        "area": attrs.get("area") or vacante.get("area") or "General",
        "cargo": attrs.get("cargo") or vacante.get("titulo") or "Empleado",
        "fecha_ingreso": attrs.get("fecha_ingreso") or date.today().isoformat(),
        "salario_base": _decimal(attrs.get("salario_base")),
    }


def _formato_email_postulante(datos, tenant_id, fecha):
    return f"""🎉 ¡Nuevo postulante contratado!

Un candidato ha sido contratado para una vacante abierta.

════════════════════════════════════
📋 DETALLES DE LA CONTRATACIÓN
════════════════════════════════════

👤 Candidato:    {datos.get('nombre', '-')}
📧 Email:        {datos.get('email', '-')}
🏢 Tenant:       {tenant_id}
📌 Vacante:      {datos.get('vacante_id', '-')}
🔗 Postulación:  {datos.get('postulacion_id', '-')}

⏰ Fecha:        {fecha}

════════════════════════════════════
Fuente: ms-reclutamiento | HCM SaaS Grupo 2
"""


def _publicar_evento(tipo, tenant_id, datos):
    ahora_utc = datetime.now(timezone.utc)
    ts = ahora_utc.isoformat()
    fecha_bonita = ahora_utc.astimezone(timezone(timedelta(hours=-5))).strftime('%d/%m/%Y %H:%M:%S') + ' (Lima)'
    event = {
        'tipo_evento': tipo,
        'tenant_id': tenant_id,
        'origen': 'ms-reclutamiento',
        'timestamp': ts,
        'datos': datos
    }
    sns.publish(
        TopicArn=TOPIC_ARN,
        Subject=f'[HCM/{tenant_id}] {tipo}',
        Message=json.dumps({
            'default': json.dumps(event, default=str),
            'sqs': json.dumps(event, default=str),
            'email': _formato_email_postulante(datos, tenant_id, fecha_bonita)
        }),
        MessageStructure='json',
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
    for campo in ('nombres', 'apellidos', 'documento', 'area', 'cargo', 'fecha_ingreso'):
        if body.get(campo):
            item[campo] = str(body[campo])
    if body.get('salario_base') not in (None, ''):
        item['salario_base'] = _decimal(body.get('salario_base'))
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
        _publicar_evento('PostulanteContratado', tenant_id,
                         _datos_contratacion(tenant_id, attrs, post_id))

    return _resp(200, attrs)
