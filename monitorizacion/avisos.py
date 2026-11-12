"""Convierte las alarmas de CloudWatch a un correo legible usando el topic confirmado."""
import json
import os
from urllib.parse import quote

import boto3
from botocore.config import Config


def handler(event, context=None):
    sns = boto3.client('sns', config=Config(connect_timeout=3, read_timeout=5,
                                           retries={'total_max_attempts': 2}))
    estados = {'ALARM': 'ALERTA', 'OK': 'RECUPERADO', 'INSUFFICIENT_DATA': 'SIN DATOS'}
    enviados = 0
    for record in event['Records']:
        alarma = json.loads(record['Sns']['Message'])
        if alarma['NewStateValue'] == 'OK' and alarma.get('OldStateValue') != 'ALARM':
            continue  # La creación de alarmas no debe inundar el correo con estados OK iniciales.
        nombre = alarma['AlarmName']
        estado = estados[alarma['NewStateValue']]
        region = os.environ.get('AWS_REGION', 'us-east-1')
        mensaje = '\n'.join([
            'Hola,', '',
            f'Estado del monitoreo HCM: {estado}.', '',
            f'Alarma: {nombre}',
            alarma.get('AlarmDescription') or 'Revisar el flujo de eventos HCM.',
            '',
            f"Fecha: {alarma['StateChangeTime']}",
            f"Detalle de AWS: {alarma['NewStateReason']}", '',
            'Revisa la alarma y sus métricas en AWS:',
            f'https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#alarmsV2:alarm/{quote(nombre, safe="")}',
            '', 'Equipo HCM',
        ])
        sns.publish(TopicArn=os.environ['EMAIL_TOPIC_ARN'],
                    Subject=f'[HCM/{estado}] {nombre}'[:99], Message=mensaje)
        enviados += 1
    return {'avisos': enviados}
