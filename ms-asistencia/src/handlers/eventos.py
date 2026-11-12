"""Publica cambios de ausencias desde el stream durable de DynamoDB."""
import json
import logging
import os

import boto3
from boto3.dynamodb.types import TypeDeserializer

from src.common.response import to_json

log = logging.getLogger(__name__)
EVENTOS = {'PENDIENTE': 'AusenciaSolicitada', 'APROBADA': 'AusenciaAprobada',
           'RECHAZADA': 'AusenciaRechazada', 'FINALIZADA': 'AusenciaFinalizada', 'CANCELADA': 'AusenciaCancelada'}


def handler(event, context=None):
    decoder = TypeDeserializer()
    for rec in event.get('Records', []):
        try:
            if rec['eventName'] not in ('INSERT', 'MODIFY'):
                continue
            ddb = rec['dynamodb']
            item = {k: decoder.deserialize(v) for k, v in ddb['NewImage'].items()}
            old = {k: decoder.deserialize(v) for k, v in ddb.get('OldImage', {}).items()}
            if item.get('clase') != 'AUS' or item.get('seed'):
                continue
            inicio = item.get('iniciada') and not old.get('iniciada')
            if item['estado'] == old.get('estado') and not inicio:
                continue
            tipo = EVENTOS[item['estado']]
            envelope = {'tipo_evento': tipo, 'tenant_id': item['tenant_id'], 'origen': 'ms-asistencia',
                        'timestamp': item['updated_at'], 'datos': {k: v for k, v in item.items()
                            if k not in ('sk', 'clase', 'tenant_id')}}
            boto3.client('sns').publish(TopicArn=os.environ['TOPIC_ARN'],
                Message=json.dumps(envelope, ensure_ascii=False, default=to_json),
                MessageAttributes={'tipo_evento': {'DataType': 'String', 'StringValue': tipo},
                                   'tenant_id': {'DataType': 'String', 'StringValue': item['tenant_id']}})
        except Exception:
            log.exception('No se publicó el registro %s', rec.get('eventID'))
            # Streams reintenta desde el primer fallo; conserva el orden de las transiciones.
            return {'batchItemFailures': [{'itemIdentifier': rec['dynamodb']['SequenceNumber']}]}
    return {'batchItemFailures': []}
