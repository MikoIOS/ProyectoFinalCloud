import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.handlers import eventos
from tests.unit.conftest import http, respuesta
from src.handlers import empleados


def evento(nombre_evento, /, tenant="andina", **datos):
    return {"tipo_evento": nombre_evento, "tenant_id": tenant, "origen": "x", "timestamp": "2026-10-31T14:00:00Z", "datos": datos}


CONTRATADO = dict(postulacion_id="pos-004567", nombres="Luis", apellidos="Ramos", email="luis.ramos@mail.com",
                  documento="45678901", area="Tecnología", cargo="Desarrollador Backend", jefe_id="emp-000001",
                  salario_base=4200.0, fecha_ingreso="2026-11-03")


def sqs(*evs, raw=True):
    return {"Records": [{"messageId": "m%d" % i,
                         "body": json.dumps(e) if raw else json.dumps({"Type": "Notification", "Message": json.dumps(e)})}
                        for i, e in enumerate(evs)]}


OK = {"batchItemFailures": []}


def fila(tabla, tenant, empleado_id):
    return tabla.get_item(Key={"tenant_id": tenant, "empleado_id": empleado_id}).get("Item")


# ---------------------------------------------------------------- PostulanteContratado
def test_postulante_contratado_crea_empleado_y_publica(tabla, publicados):
    assert eventos.handler(sqs(evento("PostulanteContratado", **CONTRATADO))) == OK
    e = fila(tabla, "andina", "emp-p004567")
    assert e["estado"] == "ACTIVO" and e["nombres"] == "Luis" and e["jefe_id"] == "emp-000001" and e["email"] == "luis.ramos@mail.com"
    assert [p["tipo_evento"] for p in publicados] == ["EmpleadoCreado"]
    assert publicados[0]["datos"]["empleado_id"] == "emp-p004567" and publicados[0]["datos"]["documento"] == "45678901"


def test_sobre_sns_sin_raw_delivery_tambien_se_entiende(tabla):
    assert eventos.handler(sqs(evento("PostulanteContratado", **CONTRATADO), raw=False)) == OK
    assert fila(tabla, "andina", "emp-p004567")


def test_entrega_duplicada_no_duplica_y_vuelve_a_publicar(tabla, publicados):
    ev = evento("PostulanteContratado", **CONTRATADO)
    assert eventos.handler(sqs(ev, ev)) == OK
    assert eventos.handler(sqs(ev)) == OK
    ids = [i["empleado_id"] for i in tabla.scan()["Items"] if i["tenant_id"] == "andina" and i["documento"] == "45678901"]
    assert ids == ["emp-p004567"]
    assert len(publicados) == 3        # reparar un publish fallido exige reenviar; los consumidores son idempotentes


def test_postulante_respeta_el_tenant_del_evento(tabla):
    eventos.handler(sqs(evento("PostulanteContratado", tenant="pacifico", **dict(CONTRATADO, jefe_id="emp-000001"))))
    assert fila(tabla, "pacifico", "emp-p004567") and fila(tabla, "andina", "emp-p004567") is None


def test_postulante_con_datos_malos_o_conflictivos_va_a_reintento(tabla, publicados):
    sin_post = {k: v for k, v in CONTRATADO.items() if k != "postulacion_id"}
    doc_repetido = dict(CONTRATADO, postulacion_id="pos-000001", documento="10000002")      # ya es de emp-000002
    jefe_ajeno = dict(CONTRATADO, postulacion_id="pos-000002", documento="45678902", jefe_id="emp-999999")
    ev = {"Records": [{"messageId": "bueno", "body": json.dumps(evento("PostulanteContratado", **CONTRATADO))},
                      {"messageId": "sin_post", "body": json.dumps(evento("PostulanteContratado", **sin_post))},
                      {"messageId": "doc", "body": json.dumps(evento("PostulanteContratado", **doc_repetido))},
                      {"messageId": "jefe", "body": json.dumps(evento("PostulanteContratado", **jefe_ajeno))},
                      {"messageId": "roto", "body": "no-es-json"}]}
    r = eventos.handler(ev)
    assert {f["itemIdentifier"] for f in r["batchItemFailures"]} == {"sin_post", "doc", "jefe", "roto"}
    assert fila(tabla, "andina", "emp-p004567")             # el bueno sí se procesó
    assert len(publicados) == 1


def test_el_empleado_creado_por_evento_se_puede_consultar_y_gestionar(tabla):
    eventos.handler(sqs(evento("PostulanteContratado", **CONTRATADO)))
    s, b = respuesta(empleados.obtener(http(id="emp-p004567")))
    assert s == 200 and b["apellidos"] == "Ramos"
    assert respuesta(empleados.cambiar_estado(http(id="emp-p004567", body={"estado": "VACACIONES"})))[0] == 200


# ---------------------------------------------------------------- Ausencias
def test_ausencia_aprobada_de_vacaciones_cambia_estado(tabla):
    assert eventos.handler(sqs(evento("AusenciaAprobada", empleado_id="emp-000002", tipo="VACACIONES",
                                      desde=datetime.now(ZoneInfo("America/Lima")).date().isoformat(),
                                      hasta=datetime.now(ZoneInfo("America/Lima")).date().isoformat()))) == OK
    assert fila(tabla, "andina", "emp-000002")["estado"] == "VACACIONES"
    _, lista = respuesta(empleados.listar(http(qs={"estado": "VACACIONES"})))
    assert "emp-000002" in [i["empleado_id"] for i in lista["items"]]


def test_ausencia_que_no_es_vacaciones_o_empleado_cesado_se_ignora(tabla):
    assert eventos.handler(sqs(evento("AusenciaAprobada", empleado_id="emp-000002", tipo="PERMISO_SIN_GOCE"))) == OK
    assert fila(tabla, "andina", "emp-000002")["estado"] == "ACTIVO"
    assert eventos.handler(sqs(evento("AusenciaAprobada", empleado_id="emp-000004", tipo="VACACIONES"))) == OK
    assert fila(tabla, "andina", "emp-000004")["estado"] == "CESADO"
    assert eventos.handler(sqs(evento("AusenciaAprobada", empleado_id="emp-777777", tipo="VACACIONES"))) == OK


def test_ausencia_aprobada_no_cruza_tenants(tabla):
    eventos.handler(sqs(evento("AusenciaAprobada", tenant="pacifico", empleado_id="emp-000001", tipo="VACACIONES")))
    assert fila(tabla, "pacifico", "emp-000001")["estado"] == "VACACIONES"
    assert fila(tabla, "andina", "emp-000001")["estado"] == "ACTIVO"


def test_ausencia_finalizada_devuelve_a_activo_y_es_idempotente(tabla):
    ev = evento("AusenciaFinalizada", empleado_id="emp-000003")        # estaba en VACACIONES
    assert eventos.handler(sqs(ev, ev)) == OK
    assert fila(tabla, "andina", "emp-000003")["estado"] == "ACTIVO"
    assert eventos.handler(sqs(evento("AusenciaFinalizada", empleado_id="emp-000004"))) == OK
    assert fila(tabla, "andina", "emp-000004")["estado"] == "CESADO"      # un cesado nunca vuelve


def test_evento_desconocido_o_sin_tenant(tabla):
    assert eventos.handler(sqs(evento("NominaGenerada", empleado_id="emp-1"))) == OK
    r = eventos.handler(sqs(dict(evento("AusenciaAprobada", empleado_id="emp-000002", tipo="VACACIONES"), tenant_id="")))
    assert len(r["batchItemFailures"]) == 1


def test_vacaciones_futuras_no_adelantan_estado(tabla):
    assert eventos.handler(sqs(evento("AusenciaAprobada", empleado_id="emp-000002", tipo="VACACIONES",
                                      desde="9998-01-01", hasta="9998-01-10"))) == OK
    assert fila(tabla, "andina", "emp-000002")["estado"] == "ACTIVO"


def test_finalizar_permiso_no_finaliza_vacaciones(tabla):
    assert eventos.handler(sqs(evento("AusenciaFinalizada", empleado_id="emp-000003", tipo="PERMISO"))) == OK
    assert fila(tabla, "andina", "emp-000003")["estado"] == "VACACIONES"
