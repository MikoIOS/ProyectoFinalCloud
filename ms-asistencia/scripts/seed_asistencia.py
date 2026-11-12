#!/usr/bin/env python3
"""Carga ficticia: 10 000 marcaciones cerradas por tenant, sin publicar eventos."""
import argparse
import os
from datetime import date

import boto3


def registro(tenant, numero):
    emp = f'emp-{numero:06d}'
    return {'tenant_id': tenant, 'sk': f'EMP#{emp}#MAR#2026-10-01', 'clase': 'MAR',
            'empleado_id': emp, 'fecha': '2026-10-01', 'hora_entrada': '09:00',
            'hora_salida': '17:00', 'horas': 8, 'tardanza_minutos': 0, 'tarde': False,
            'estado': 'CERRADA', 'registrado_por': 'seed-asistencia', 'seed': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--table', default=os.environ.get('TABLE_NAME', 'hcm-asistencia-dev'))
    args = parser.parse_args()
    assert date(2026, 10, 1) < date.today(), 'La fecha del seed debe ser pasada'
    assert registro('andina', 2)['sk'] == 'EMP#emp-000002#MAR#2026-10-01'
    table = boto3.resource('dynamodb', region_name='us-east-1').Table(args.table)
    # Claves determinísticas: repetir el seed no incrementa el volumen.
    with table.batch_writer() as batch:
        for tenant in ('andina', 'pacifico', 'sierra'):
            for numero in range(1, 10001):
                batch.put_item(Item=registro(tenant, numero))
            print(f'{tenant}: 10 000 marcaciones ficticias', flush=True)


if __name__ == '__main__':
    main()
