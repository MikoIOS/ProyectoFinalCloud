#!/usr/bin/env python3
"""Exporta instantáneas DynamoDB a S3; guarda solamente el estado en el disco local."""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def prepare_bucket(s3, bucket, account, region):
    try:
        s3.head_bucket(Bucket=bucket, ExpectedBucketOwner=account)
    except ClientError as error:
        if error.response['Error']['Code'] not in ('404', 'NoSuchBucket', 'NotFound'):
            raise
        params = {'Bucket': bucket}
        if region != 'us-east-1':
            params['CreateBucketConfiguration'] = {'LocationConstraint': region}
        s3.create_bucket(**params)
        s3.head_bucket(Bucket=bucket, ExpectedBucketOwner=account)
    s3.put_public_access_block(Bucket=bucket, ExpectedBucketOwner=account, PublicAccessBlockConfiguration={
        'BlockPublicAcls': True, 'IgnorePublicAcls': True,
        'BlockPublicPolicy': True, 'RestrictPublicBuckets': True,
    })


def enable_pitr(client, table):
    status = client.describe_continuous_backups(TableName=table)['ContinuousBackupsDescription']['PointInTimeRecoveryDescription']['PointInTimeRecoveryStatus']
    if status == 'ENABLED':
        return
    print('Habilitando recuperación PITR:', table, flush=True)
    client.update_continuous_backups(TableName=table, PointInTimeRecoverySpecification={'PointInTimeRecoveryEnabled': True})
    for _ in range(60):
        status = client.describe_continuous_backups(TableName=table)['ContinuousBackupsDescription']['PointInTimeRecoveryDescription']['PointInTimeRecoveryStatus']
        if status == 'ENABLED':
            return
        time.sleep(5)
    raise RuntimeError('PITR todavía no está disponible para ' + table + '; vuelve a ejecutar cuando termine de habilitarse')


def run(client, s3, bucket, destination, tables=None):
    os.umask(0o077)
    if not tables:
        tables = [name for page in client.get_paginator('list_tables').paginate()
                  for name in page['TableNames'] if name.startswith('hcm-')]
    if not tables:
        raise RuntimeError('No se encontraron tablas HCM; no se inició ningún respaldo')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + os.urandom(4).hex()
    directory = Path(destination) / stamp
    directory.mkdir(parents=True, mode=0o700)
    prefix = 'dynamodb/' + stamp
    manifest = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'IN_PROGRESS',
                'bucket': bucket, 'prefix': prefix, 'tables': []}

    def save():
        data = json.dumps(manifest, indent=2) + '\n'
        temporary = directory / 'manifest.json.partial'
        temporary.write_text(data)
        temporary.replace(directory / 'manifest.json')
        s3.put_object(Bucket=bucket, Key=prefix + '/manifest.json', Body=data.encode(),
                      ContentType='application/json', ServerSideEncryption='AES256')

    try:
        save()
        print('Destino: s3://' + bucket + '/' + prefix + '/', flush=True)
        print('Estado local:', directory / 'manifest.json', flush=True)
        for table in sorted(set(tables)):
            description = client.describe_table(TableName=table)['Table']
            enable_pitr(client, table)
            schema = json.dumps(description, default=str, indent=2).encode()
            s3.put_object(Bucket=bucket, Key=prefix + '/' + table + '/schema.json', Body=schema,
                          ContentType='application/json', ServerSideEncryption='AES256')
            # Registrar el token antes de iniciar: permite identificar un envío de resultado incierto.
            token = os.urandom(16).hex()
            entry = {'table': table, 'table_arn': description['TableArn'], 'client_token': token, 'status': 'SUBMITTING',
                     's3_prefix': prefix + '/' + table}
            manifest['tables'].append(entry)
            save()
            export = client.export_table_to_point_in_time(
                TableArn=description['TableArn'], ClientToken=token,
                S3Bucket=bucket, S3Prefix=entry['s3_prefix'],
                S3SseAlgorithm='AES256', ExportFormat='DYNAMODB_JSON', ExportType='FULL_EXPORT',
            )['ExportDescription']
            entry.update(export_arn=export['ExportArn'], status=export['ExportStatus'])
            save()
            print('Exportación iniciada:', table, entry['export_arn'], flush=True)

        for _ in range(720):
            pending = False
            for entry in manifest['tables']:
                if entry['status'] == 'COMPLETED':
                    continue
                export = client.describe_export(ExportArn=entry['export_arn'])['ExportDescription']
                entry['status'] = export['ExportStatus']
                if entry['status'] == 'FAILED':
                    entry['error'] = export.get('FailureMessage', 'Sin detalle')
                    raise RuntimeError('Falló la exportación de ' + entry['table'] + ': ' + entry['error'])
                if entry['status'] == 'COMPLETED':
                    entry.update(item_count=export.get('ItemCount'), export_manifest=export.get('ExportManifest'))
                    print('Respaldo disponible en S3:', entry['table'], flush=True)
                else:
                    pending = True
            save()
            if not pending:
                manifest.update(status='COMPLETE', completed_at=datetime.now(timezone.utc).isoformat())
                save()
                return directory
            print('AWS sigue exportando; consultando nuevamente en 30 segundos…', flush=True)
            time.sleep(30)
        raise RuntimeError('Se agotó la espera; las exportaciones iniciadas siguen en AWS. Consulta los ARN del manifiesto')
    except (Exception, KeyboardInterrupt) as error:
        manifest['status'] = 'INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'FAILED'
        try:
            save()
        except Exception as save_error:
            print('No se pudo actualizar el estado en S3:', type(save_error).__name__, flush=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bucket', required=True, help='Bucket privado de respaldos; se crea si no existe')
    parser.add_argument('--destination', type=Path, default=Path.home() / 'hcm-backup-status', help='Solo metadatos locales')
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--table', action='append', help='Repetible; por defecto todas las tablas hcm-*')
    args = parser.parse_args()
    session = boto3.Session(region_name=args.region)
    options = Config(connect_timeout=10, read_timeout=60, retries={'mode': 'standard', 'max_attempts': 5})
    try:
        account = session.client('sts', config=options).get_caller_identity()['Account']
        s3 = session.client('s3', config=options)
        prepare_bucket(s3, args.bucket, account, args.region)
        directory = run(session.client('dynamodb', config=options), s3, args.bucket, args.destination, args.table)
        print('Respaldo S3 completado. Estado local:', directory)
    except KeyboardInterrupt:
        raise SystemExit('Espera interrumpida. Las exportaciones iniciadas siguen en AWS; revisa el manifiesto local.') from None
    except (ClientError, RuntimeError, OSError) as error:
        raise SystemExit('No se confirmó el respaldo: ' + str(error)) from None
