"""Publicación de eventos al topic SNS hcm-eventos (formato común del proyecto)."""
import json
import os
from datetime import datetime, timezone

import boto3

from src.common.response import to_json

_sns = None


def _cliente():
    global _sns
    if _sns is None:
        _sns = boto3.client("sns", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _sns


def publish_event(tipo_evento, tenant_id, datos, origen="ms-nominas"):
    envelope = {
        "tipo_evento": tipo_evento,
        "tenant_id": tenant_id,
        "origen": origen,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datos": datos,
    }
    _cliente().publish(
        TopicArn=os.environ["TOPIC_ARN"],
        Message=json.dumps(envelope, ensure_ascii=False, default=to_json),
        MessageAttributes={"tipo_evento": {"DataType": "String", "StringValue": tipo_evento}},
    )
    return envelope
