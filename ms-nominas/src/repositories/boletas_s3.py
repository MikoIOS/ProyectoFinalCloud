"""Archivo privado de boletas; las claves se construyen después de autorizar la nómina."""
import os

import boto3
from botocore.config import Config


def guardar(tenant_id, nomina, contenido, nombre):
    boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'),
                 config=Config(connect_timeout=3, read_timeout=5, retries={'total_max_attempts': 2})).put_object(
        Bucket=os.environ['BOLETAS_BUCKET'],
        Key=f"{tenant_id}/boletas/{nomina['periodo']}/{nomina['nomina_id']}.pdf",
        Body=contenido,
        ContentType='application/pdf',
        ContentDisposition=f'attachment; filename="{nombre}"',
        ServerSideEncryption='AES256',
        Metadata={'tenant_id': tenant_id, 'nomina_id': nomina['nomina_id']},
    )
