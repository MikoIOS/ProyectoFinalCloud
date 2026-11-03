import json

import boto3
import pytest

from src.common.events import publish_event
from src.handlers import auth, eventos
from tests.unit.conftest import PWD


def evento(tipo, tenant="andina", **datos):
    return {"tipo_evento": tipo, "tenant_id": tenant, "origen": "ms-empleados",
            "timestamp": "2026-10-31T14:00:00Z", "datos": datos}


CREADO = dict(empleado_id="emp-010001", email="Nuevo.Empleado@andina.pe",
              nombres="Nuevo", apellidos="Empleado", documento="71234567")


def sqs(*eventos_, raw=True):
    recs = []
    for i, e in enumerate(eventos_):
        body = json.dumps(e) if raw else json.dumps({"Type": "Notification", "Message": json.dumps(e)})
        recs.append({"messageId": "m%d" % i, "body": body})
    return {"Records": recs}


def login(email, password, tenant="andina"):
    r = auth.login({"body": json.dumps({"tenant_id": tenant, "email": email, "password": password})})
    return r["statusCode"], json.loads(r["body"])


def test_empleado_creado_crea_usuario_con_clave_inicial_igual_al_documento(tabla):
    assert eventos.handler(sqs(evento("EmpleadoCreado", **CREADO))) == {"batchItemFailures": []}
    item = tabla.get_item(Key={"tenant_id": "andina", "user_id": "usr-010001"})["Item"]
    assert item["rol"] == "empleado" and item["empleado_id"] == "emp-010001"
    assert item["email"] == "nuevo.empleado@andina.pe" and item["nombre"] == "Nuevo Empleado"
    assert item["debe_cambiar_password"] is True
    status, body = login("nuevo.empleado@andina.pe", "71234567")
    assert status == 200 and body["usuario"]["debe_cambiar_password"] is True


def test_sobre_sns_sin_raw_delivery_tambien_se_entiende(tabla):
    assert eventos.handler(sqs(evento("EmpleadoCreado", **CREADO), raw=False)) == {"batchItemFailures": []}
    assert tabla.get_item(Key={"tenant_id": "andina", "user_id": "usr-010001"}).get("Item")


def test_entrega_duplicada_es_idempotente(tabla):
    ev = evento("EmpleadoCreado", **CREADO)
    assert eventos.handler(sqs(ev, ev)) == {"batchItemFailures": []}
    assert eventos.handler(sqs(ev)) == {"batchItemFailures": []}
    items = tabla.scan()["Items"]
    assert len([i for i in items if i["empleado_id"] == "emp-010001"]) == 1


def test_empleado_creado_respeta_el_tenant_del_evento(tabla):
    eventos.handler(sqs(evento("EmpleadoCreado", tenant="pacifico", **CREADO)))
    assert tabla.get_item(Key={"tenant_id": "pacifico", "user_id": "usr-010001"}).get("Item")
    assert tabla.get_item(Key={"tenant_id": "andina", "user_id": "usr-010001"}).get("Item") is None


def test_empleado_cesado_desactiva_y_bloquea_login(tabla):
    # usr-000003 / emp-000003 (ana@andina.pe) viene del fixture
    assert login("ana@andina.pe", PWD)[0] == 200
    assert eventos.handler(sqs(evento("EmpleadoCesado", empleado_id="emp-000003"))) == {"batchItemFailures": []}
    assert login("ana@andina.pe", PWD)[0] == 403
    # repetir el evento no rompe
    assert eventos.handler(sqs(evento("EmpleadoCesado", empleado_id="emp-000003"))) == {"batchItemFailures": []}


def test_cese_de_empleado_sin_usuario_se_confirma_sin_error(tabla):
    assert eventos.handler(sqs(evento("EmpleadoCesado", empleado_id="emp-777777"))) == {"batchItemFailures": []}


def test_cese_no_cruza_tenants(tabla):
    # emp-000001 existe en andina y pacifico: cesar en pacifico no toca andina
    eventos.handler(sqs(evento("EmpleadoCesado", tenant="pacifico", empleado_id="emp-000001")))
    assert login("maria@andina.pe", PWD)[0] == 200
    assert login("maria@pacifico.pe", PWD, tenant="pacifico")[0] == 403


def test_evento_desconocido_se_ignora(tabla):
    assert eventos.handler(sqs(evento("NominaGenerada", empleado_id="emp-1"))) == {"batchItemFailures": []}


def test_mensajes_malos_se_reportan_individualmente(tabla):
    bueno = evento("EmpleadoCreado", **CREADO)
    sin_documento = evento("EmpleadoCreado", **{k: v for k, v in CREADO.items() if k != "documento"})
    email_ajeno = evento("EmpleadoCreado", **dict(CREADO, empleado_id="emp-010002", email="ana@andina.pe"))
    ev = {"Records": [{"messageId": "ok", "body": json.dumps(bueno)},
                      {"messageId": "falta", "body": json.dumps(sin_documento)},
                      {"messageId": "ajeno", "body": json.dumps(email_ajeno)},
                      {"messageId": "roto", "body": "no-es-json"}]}
    r = eventos.handler(ev)
    assert {f["itemIdentifier"] for f in r["batchItemFailures"]} == {"falta", "ajeno", "roto"}
    assert tabla.get_item(Key={"tenant_id": "andina", "user_id": "usr-010001"}).get("Item")   # el bueno sí se procesó


def test_publish_event_envia_el_formato_comun(tabla, monkeypatch):
    sns = boto3.client("sns", region_name="us-east-1")
    sqs_c = boto3.client("sqs", region_name="us-east-1")
    topic = sns.create_topic(Name="hcm-eventos")["TopicArn"]
    q = sqs_c.create_queue(QueueName="q")["QueueUrl"]
    qarn = sqs_c.get_queue_attributes(QueueUrl=q, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    sns.subscribe(TopicArn=topic, Protocol="sqs", Endpoint=qarn, Attributes={"RawMessageDelivery": "true"})
    monkeypatch.setenv("TOPIC_ARN", topic)

    publish_event("EmpleadoCreado", "andina", {"empleado_id": "emp-000045"}, origen="ms-empleados")
    msgs = sqs_c.receive_message(QueueUrl=q, MaxNumberOfMessages=1).get("Messages", [])
    assert len(msgs) == 1
    env = json.loads(msgs[0]["Body"])
    assert set(env) == {"tipo_evento", "tenant_id", "origen", "timestamp", "datos"}
    assert env["tipo_evento"] == "EmpleadoCreado" and env["datos"] == {"empleado_id": "emp-000045"}
