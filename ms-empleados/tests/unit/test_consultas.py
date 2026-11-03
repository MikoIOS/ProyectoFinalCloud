from src.handlers import autoservicio, consultas
from tests.unit.conftest import http, respuesta


# ---------------------------------------------------------------- resumen
def test_resumen_por_estado_y_area(tabla):
    s, b = respuesta(consultas.resumen(http()))
    assert s == 200
    assert b == {"total": 5,
                 "por_estado": {"ACTIVO": 3, "VACACIONES": 1, "CESADO": 1},
                 "por_area": {"Recursos Humanos": 1, "Tecnología": 2, "Ventas": 2}}


def test_resumen_solo_cuenta_su_tenant_y_exige_rol(tabla):
    _, b = respuesta(consultas.resumen(http(tenant="pacifico")))
    assert b["total"] == 1 and b["por_area"] == {"Operaciones": 1}
    assert respuesta(consultas.resumen(http(rol="gerente")))[0] == 200
    assert respuesta(consultas.resumen(http(rol="empleado")))[0] == 403


# ---------------------------------------------------------------- organigrama
def test_organigrama_por_jefe(tabla):
    s, b = respuesta(consultas.organigrama(http(qs={"jefe_id": "emp-000001"})))
    assert s == 200 and b["jefe"]["empleado_id"] == "emp-000001"
    assert {e["empleado_id"] for e in b["subordinados"]} == {"emp-000002", "emp-000004", "emp-000005"}
    assert not any("salario_base" in e for e in b["subordinados"])
    _, b = respuesta(consultas.organigrama(http(qs={"jefe_id": "emp-000003"})))
    assert b["subordinados"] == []


def test_organigrama_por_area_agrupa_por_jefe(tabla):
    _, b = respuesta(consultas.organigrama(http(qs={"area": "Tecnología"})))
    grupos = {g["jefe_id"]: [e["empleado_id"] for e in g["empleados"]] for g in b["grupos"]}
    assert grupos == {"emp-000001": ["emp-000002"], "emp-000002": ["emp-000003"]}
    _, b = respuesta(consultas.organigrama(http(qs={"area": "Recursos Humanos"})))
    assert b["grupos"] == [{"jefe_id": None, "empleados": [b["grupos"][0]["empleados"][0]]}]


def test_organigrama_parametros_y_aislamiento(tabla):
    assert respuesta(consultas.organigrama(http()))[0] == 400
    assert respuesta(consultas.organigrama(http(qs={"area": "Ventas", "jefe_id": "emp-000001"})))[0] == 400
    assert respuesta(consultas.organigrama(http(qs={"jefe_id": "emp-999999"})))[0] == 404
    _, b = respuesta(consultas.organigrama(http(tenant="pacifico", qs={"jefe_id": "emp-000001"})))
    assert b["subordinados"] == [] and b["jefe"]["nombres"] == "Paola"       # el jefe 1 de pacifico, no el de andina
    assert respuesta(consultas.organigrama(http(rol="reclutador", qs={"area": "Ventas"})))[0] == 403


# ---------------------------------------------------------------- autoservicio
def test_mi_ficha_completa(tabla):
    s, b = respuesta(autoservicio.mi_ficha(http(rol="empleado", empleado_id="emp-000002")))
    assert s == 200 and b["empleado_id"] == "emp-000002" and b["salario_base"] == 4000


def test_mi_ficha_sin_empleado_vinculado(tabla):
    assert respuesta(autoservicio.mi_ficha(http(empleado_id=None)))[0] == 404
    assert respuesta(autoservicio.mi_ficha({"body": "{}"}))[0] == 401


def test_editar_solo_mi_contacto(tabla):
    def patch(body, **kw):
        return respuesta(autoservicio.actualizar_mi_contacto(http(rol="empleado", empleado_id="emp-000002", body=body, **kw)))

    s, b = patch({"telefono": "987654321", "direccion": "Av. Perú 123"})
    assert s == 200 and b["telefono"] == "987654321" and b["direccion"] == "Av. Perú 123"
    assert patch({"contacto_emergencia": "Marta 999111222"})[0] == 200
    for campo in ("salario_base", "cargo", "area", "estado", "jefe_id", "email", "documento", "tenant_id"):
        s, b = patch({"telefono": "1", campo: "x"})
        assert s == 400, campo
    assert patch({})[0] == 400
    assert patch({"telefono": ""})[0] == 400
    # no se modificó nada ajeno
    fila = tabla.get_item(Key={"tenant_id": "andina", "empleado_id": "emp-000002"})["Item"]
    assert fila["cargo"] == "Cargo 2" and fila["salario_base"] == 4000


def test_editar_contacto_siempre_sobre_el_propio_empleado(tabla):
    # aunque el body traiga otro id, se edita el del token
    autoservicio.actualizar_mi_contacto(http(rol="empleado", empleado_id="emp-000002",
                                             body={"telefono": "111", "empleado_id": "emp-000005"}))
    assert tabla.get_item(Key={"tenant_id": "andina", "empleado_id": "emp-000005"})["Item"]["telefono"] == "900000005"
