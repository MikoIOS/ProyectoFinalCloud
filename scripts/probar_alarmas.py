#!/usr/bin/env python3
"""Activa únicamente la alarma sintética de HCM; no cambia colas ni microservicios."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3


def esperar(cloudwatch, nombre, estado, timeout=240):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        alarms = cloudwatch.describe_alarms(AlarmNames=[nombre])['MetricAlarms']
        if not alarms:
            raise RuntimeError('No existe la alarma de prueba; despliega primero hcm-monitorizacion')
        alarm = alarms[0]
        if alarm['StateValue'] == estado:
            return alarm
        print(f"Esperando {estado}: estado actual {alarm['StateValue']}", flush=True)
        time.sleep(10)
    raise RuntimeError(f'La alarma no llegó a {estado} dentro de {timeout} segundos')


def probar(cloudwatch, stage):
    nombre = f'hcm-{stage}-eda-prueba'
    esperar(cloudwatch, nombre, 'OK')
    metric = {'MetricName': f'PruebaAlarma-{stage}', 'Value': 1, 'Unit': 'Count'}
    cloudwatch.put_metric_data(Namespace='HCM/EDA', MetricData=[metric])
    try:
        alarma = esperar(cloudwatch, nombre, 'ALARM')
        if not alarma.get('ActionsEnabled') or not alarma.get('AlarmActions'):
            raise RuntimeError('La alarma llegó a ALARM pero sus notificaciones están deshabilitadas')
        print('OK: métrica de prueba → alarma ALARM con acciones habilitadas', flush=True)
    finally:
        cloudwatch.put_metric_data(Namespace='HCM/EDA', MetricData=[{**metric, 'Value': 0}])
    esperar(cloudwatch, nombre, 'OK')
    print('OK: la alarma de prueba volvió a OK', flush=True)
    return {'fecha': datetime.now(timezone.utc).isoformat(), 'alarma': nombre,
            'estados_verificados': ['OK', 'ALARM', 'OK'], 'acciones': alarma['AlarmActions'],
            'alcance': 'Verifica evaluación y configuración de acciones; la entrega SNS/correo se comprueba por separado.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', default='dev')
    args = parser.parse_args()
    resultado = probar(boto3.client('cloudwatch', region_name='us-east-1'), args.stage)
    destino = Path(__file__).resolve().parents[1] / 'docs' / 'prueba_alarmas.json'
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + '\n')
    print(f'Evidencia: {destino}', flush=True)


if __name__ == '__main__':
    main()
