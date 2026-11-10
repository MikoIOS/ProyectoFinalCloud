"""Comprueba conexiones EDA sin habilitarlas ni alterar mensajes."""
import json
import logging
import os

import boto3
from botocore.config import Config

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def handler(event, context=None):
    config = Config(connect_timeout=10, read_timeout=10, retries={'total_max_attempts': 2})
    cliente = boto3.client('lambda', config=config)
    problemas = []
    for nombre in json.loads(os.environ['CANALES']):
        mappings = []
        for pagina in cliente.get_paginator('list_event_source_mappings').paginate(FunctionName=nombre):
            mappings.extend(pagina['EventSourceMappings'])
        if not mappings or any(m['State'] != 'Enabled' for m in mappings):
            problemas.append(nombre)
    log.info('Canales no habilitados: %s', json.dumps(problemas))
    boto3.client('cloudwatch', config=config).put_metric_data(Namespace='HCM/EDA', MetricData=[{
        'MetricName': 'CanalesDeshabilitados-' + os.environ['STAGE'],
        'Value': len(problemas), 'Unit': 'Count',
    }])
    return {'canales_no_habilitados': problemas}


if __name__ == '__main__':
    from pathlib import Path
    import subprocess

    stage = os.environ.setdefault('STAGE', 'dev')
    os.environ['CANALES'] = subprocess.check_output(
        ['node', '-e', "process.stdout.write(require('./recursos.cjs').canales)"],
        cwd=Path(__file__).resolve().parent, text=True,
    ).replace('${sls:stage}', stage)
    print(json.dumps(handler({}), ensure_ascii=False))
