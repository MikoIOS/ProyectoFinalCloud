"""Publicación de eventos al topic SNS hcm-eventos (formato común del documento base)."""
import json
import os
from datetime import datetime, timezone

import boto3

from src.common.response import to_json


def publish_event(tipo_evento, tenant_id, datos, origen):
    envelope = {
        "tipo_evento": tipo_evento,
        "tenant_id": tenant_id,
        "origen": origen,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datos": datos,
    }
    sns = boto3.client("sns", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    sns.publish(
        TopicArn=os.environ["TOPIC_ARN"],
        Message=json.dumps(envelope, ensure_ascii=False, default=to_json),
        MessageAttributes={"tipo_evento": {"DataType": "String", "StringValue": tipo_evento}},
    )
    return envelope
