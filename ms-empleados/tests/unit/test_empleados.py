from src.handlers import empleados
from tests.unit.conftest import NUEVO, http, respuesta


def crear(como="admin_rrhh", tenant="andina", **body):
    """`como` = rol de quien llama; el resto son campos del empleado."""
    return respuesta(empleados.crear(http(tenant=tenant, rol=como, body=dict(NUEVO, **body))))


# ---------------------------------------------------------------- crear
def test_crear_ok_y_publica_evento(tabla, publicados):
    status, b = crear()
    assert status == 201
    assert b["estado"] == "ACTIVO" and b["tenant_id"] == "andina" and b["email"] == "carla.soto@andina.pe"
    assert b["empleado_id"].startswith("emp-") and b["salario_base"] == 4200.5
    assert len(publicados) == 1
    ev = publicados[0]
    assert ev["tipo_evento"] == "EmpleadoCreado" and ev["tenant_id"] == "andina" and ev["origen"] == "ms-empleados"
    assert ev["datos"]["empleado_id"] == b["empleado_id"]
    assert {"email", "nombres", "apellidos", "documento"} <= set(ev["datos"])


def test_crear_ignora_tenant_del_body(tabla):
    status, b = crear(tenant_id="pacifico")
    assert status == 201 and b["tenant_id"] == "andina"
    assert tabla.get_item(Key={"tenant_id": "pacifico", "empleado_id": b["empleado_id"]}).get("Item") is None


def test_documento_unico_por_tenant(tabla):
    assert crear()[0] == 201
    assert crear(email="otra@andina.pe")[0] == 409                  # mismo documento, mismo tenant
    assert crear(tenant="pacifico", jefe_id="emp-000001")[0] == 201  # mismo documento, otro tenant: permitido
    assert crear(documento="10000001", email="x@andina.pe")[0] == 409  # documento del seed de andina


def test_crear_validaciones(tabla):
    assert crear(documento="123")[0] == 400
    assert crear(documento="abcdefgh")[0] == 400
    assert crear(email="no-es-email")[0] == 400
    assert crear(salario_base=0)[0] == 400
    assert crear(salario_base=-5)[0] == 400
    assert crear(salario_base="mucho")[0] == 400
    assert crear(salario_base=True)[0] == 400
    assert crear(fecha_ingreso="15/03/2026")[0] == 400
    assert crear(fecha_ingreso="2026-02-30")[0] == 400
    assert crear(nombres="  ")[0] == 400
    s, b = respuesta(empleados.crear(http(body={"nombres": "X"})))
    assert s == 400 and "Faltan campos" in b["error"]["mensaje"]


def test_jefe_debe_existir_en_el_tenant_y_no_estar_cesado(tabla):
    assert crear(jefe_id="emp-999999")[0] == 400
    assert crear(jefe_id="emp-000004")[0] == 400                    # cesado
    assert crear(jefe_id="emp-000003")[0] == 201                    # en vacaciones: válido
    assert crear(tenant="pacifico", documento="71234568", email="b@p.pe", jefe_id="emp-000002")[0] == 400  # jefe de andina
    assert crear(documento="71234569", email="c@andina.pe", jefe_id="")[0] == 201                          # sin jefe


def test_crear_requiere_admin(tabla):
    for como in ("gerente", "reclutador", "empleado"):
        assert crear(como=como)[0] == 403
    assert respuesta(empleados.crear({"body": "{}"}))[0] == 401


def test_si_falla_la_publicacion_se_avisa_pero_se_crea(tabla, monkeypatch):
    def roto(*a, **k):
        raise RuntimeError("SNS caído")
    monkeypatch.setattr("src.common.events.publish_event", roto)
    status, b = crear()
    assert status == 201 and "aviso" in b


# ---------------------------------------------------------------- listar
def test_listar_resumido_sin_datos_sensibles_y_paginado(tabla):
    s, b = respuesta(empleados.listar(http(qs={"limit": "2"})))
    assert s == 200 and len(b["items"]) == 2 and b["next_token"]
    vistos = [i["empleado_id"] for i in b["items"]]
    while b["next_token"]:
        _, b = respuesta(empleados.listar(http(qs={"limit": "2", "next_token": b["next_token"]})))
        vistos += [i["empleado_id"] for i in b["items"]]
    assert vistos == ["emp-00000%d" % i for i in range(1, 6)]
    sensibles = {"salario_base", "documento", "telefono"}
    assert not any(sensibles & set(i) for i in b["items"])


def test_listar_por_area_estado_y_ambos(tabla):
    _, b = respuesta(empleados.listar(http(qs={"area": "Tecnología"})))
    assert {i["empleado_id"] for i in b["items"]} == {"emp-000002", "emp-000003"}
    _, b = respuesta(empleados.listar(http(qs={"estado": "CESADO"})))
    assert [i["empleado_id"] for i in b["items"]] == ["emp-000004"]
    _, b = respuesta(empleados.listar(http(qs={"area": "Tecnología", "estado": "VACACIONES"})))
    assert [i["empleado_id"] for i in b["items"]] == ["emp-000003"]
    _, b = respuesta(empleados.listar(http(qs={"area": "Ventas", "estado": "ACTIVO"})))
    assert [i["empleado_id"] for i in b["items"]] == ["emp-000005"]


def test_listar_paginado_por_indice_no_pierde_ni_repite(tabla):
    todos = []
    _, b = respuesta(empleados.listar(http(qs={"area": "Ventas", "limit": "1"})))
    todos += [i["empleado_id"] for i in b["items"]]
    while b["next_token"]:
        _, b = respuesta(empleados.listar(http(qs={"area": "Ventas", "limit": "1", "next_token": b["next_token"]})))
        todos += [i["empleado_id"] for i in b["items"]]
    assert todos == ["emp-000004", "emp-000005"]


def test_listar_aislamiento_y_roles(tabla):
    _, b = respuesta(empleados.listar(http(tenant="pacifico")))
    assert [i["nombres"] for i in b["items"]] == ["Paola"]      # pacifico solo ve el suyo (andina tiene 5)
    assert respuesta(empleados.listar(http(rol="gerente")))[0] == 200
    for rol in ("reclutador", "empleado"):
        assert respuesta(empleados.listar(http(rol=rol)))[0] == 403


def test_listar_validaciones(tabla):
    assert respuesta(empleados.listar(http(qs={"estado": "X"})))[0] == 400
    assert respuesta(empleados.listar(http(qs={"limit": "0"})))[0] == 400
    assert respuesta(empleados.listar(http(qs={"next_token": "basura"})))[0] == 400


def test_next_token_de_otro_tenant_o_de_otro_indice_se_rechaza(tabla):
    _, b = respuesta(empleados.listar(http(qs={"limit": "2"})))
    assert respuesta(empleados.listar(http(tenant="pacifico", qs={"next_token": b["next_token"]})))[0] == 400
    assert respuesta(empleados.listar(http(qs={"area": "Ventas", "next_token": b["next_token"]})))[0] == 400


# ---------------------------------------------------------------- obtener
def test_obtener_segun_rol(tabla):
    s, b = respuesta(empleados.obtener(http(id="emp-000002")))
    assert s == 200 and b["salario_base"] == 4000 and b["documento"] == "10000002"
    s, b = respuesta(empleados.obtener(http(rol="gerente", id="emp-000002")))      # gerente: sin datos sensibles
    assert s == 200 and "salario_base" not in b and "documento" not in b and b["cargo"] == "Cargo 2"
    # empleado: solo el suyo (con todo), otro => 403
    s, b = respuesta(empleados.obtener(http(rol="empleado", empleado_id="emp-000002", id="emp-000002")))
    assert s == 200 and b["salario_base"] == 4000
    assert respuesta(empleados.obtener(http(rol="empleado", empleado_id="emp-000002", id="emp-000005")))[0] == 403
    assert respuesta(empleados.obtener(http(rol="reclutador", empleado_id=None, id="emp-000005")))[0] == 403


def test_obtener_otro_tenant_o_inexistente_404(tabla):
    assert respuesta(empleados.obtener(http(tenant="pacifico", rol="admin_rrhh", id="emp-000005")))[0] == 404
    assert respuesta(empleados.obtener(http(id="emp-999999")))[0] == 404


# ---------------------------------------------------------------- actualizar
def test_actualizar_campos_laborales(tabla):
    s, b = respuesta(empleados.actualizar(http(id="emp-000002", body={"cargo": "Tech Lead", "salario_base": 6000,
                                                                      "area": "Operaciones"})))
    assert s == 200 and b["cargo"] == "Tech Lead" and b["salario_base"] == 6000 and b["area"] == "Operaciones"
    _, lista = respuesta(empleados.listar(http(qs={"area": "Operaciones"})))      # el GSI se actualizó
    assert "emp-000002" in [i["empleado_id"] for i in lista["items"]]


def test_actualizar_no_toca_estado_ni_ids_ni_tenant(tabla):
    for campo in ("estado", "tenant_id", "empleado_id", "fecha_cese", "created_at"):
        s, b = respuesta(empleados.actualizar(http(id="emp-000002", body={campo: "X"})))
        assert s == 400, campo
    assert respuesta(empleados.actualizar(http(id="emp-000002", body={})))[0] == 400


def test_actualizar_jefe_sin_ciclos_ni_autojefe(tabla):
    assert respuesta(empleados.actualizar(http(id="emp-000002", body={"jefe_id": "emp-000002"})))[0] == 400
    # emp-000001 -> 2 -> 3: poner a 3 como jefe de 1 (o de 2 tras 3<-2) crearía un ciclo
    assert respuesta(empleados.actualizar(http(id="emp-000001", body={"jefe_id": "emp-000003"})))[0] == 400
    assert respuesta(empleados.actualizar(http(id="emp-000002", body={"jefe_id": "emp-000004"})))[0] == 400  # cesado
    s, b = respuesta(empleados.actualizar(http(id="emp-000003", body={"jefe_id": "emp-000005"})))
    assert s == 200 and b["jefe_id"] == "emp-000005"
    s, b = respuesta(empleados.actualizar(http(id="emp-000003", body={"jefe_id": None})))
    assert s == 200 and "jefe_id" not in b


def test_actualizar_documento_unico_y_cesado_inmodificable(tabla):
    assert respuesta(empleados.actualizar(http(id="emp-000002", body={"documento": "10000005"})))[0] == 409
    assert respuesta(empleados.actualizar(http(id="emp-000002", body={"documento": "10000002"})))[0] == 200  # el suyo
    assert respuesta(empleados.actualizar(http(id="emp-000004", body={"cargo": "X"})))[0] == 409
    assert respuesta(empleados.actualizar(http(id="emp-999999", body={"cargo": "X"})))[0] == 404


def test_actualizar_aislamiento_y_roles(tabla):
    assert respuesta(empleados.actualizar(http(tenant="pacifico", id="emp-000005", body={"cargo": "X"})))[0] == 404
    assert tabla.get_item(Key={"tenant_id": "andina", "empleado_id": "emp-000005"})["Item"]["cargo"] == "Cargo 5"
    for rol in ("gerente", "empleado", "reclutador"):
        assert respuesta(empleados.actualizar(http(rol=rol, id="emp-000002", body={"cargo": "X"})))[0] == 403


# ---------------------------------------------------------------- cambiar estado
def estado(id, body, **kw):
    return respuesta(empleados.cambiar_estado(http(id=id, body=body, **kw)))


def test_transiciones_validas_e_invalidas(tabla):
    assert estado("emp-000002", {"estado": "VACACIONES"})[1]["estado"] == "VACACIONES"
    assert estado("emp-000002", {"estado": "ACTIVO"})[1]["estado"] == "ACTIVO"
    assert estado("emp-000002", {"estado": "ACTIVO"})[0] == 409               # ya está ACTIVO
    assert estado("emp-000004", {"estado": "ACTIVO"})[0] == 409               # CESADO no se reactiva
    assert estado("emp-000002", {"estado": "BORRADO"})[0] == 400
    assert estado("emp-999999", {"estado": "VACACIONES"})[0] == 404
    _, lista = respuesta(empleados.listar(http(qs={"estado": "VACACIONES"})))  # estado-index al día
    assert {i["empleado_id"] for i in lista["items"]} == {"emp-000003"}


def test_cese_publica_evento_y_exige_fecha(tabla, publicados):
    assert estado("emp-000005", {"estado": "CESADO"})[0] == 400
    assert estado("emp-000005", {"estado": "CESADO", "fecha_cese": "2020-01-01"})[0] == 400   # antes del ingreso
    s, b = estado("emp-000005", {"estado": "CESADO", "fecha_cese": "2026-10-31", "motivo": "Renuncia"})
    assert s == 200 and b["estado"] == "CESADO" and b["fecha_cese"] == "2026-10-31"
    assert publicados == [{"tipo_evento": "EmpleadoCesado", "tenant_id": "andina", "origen": "ms-empleados",
                           "datos": {"empleado_id": "emp-000005", "fecha_cese": "2026-10-31", "motivo": "Renuncia"}}]
    assert estado("emp-000005", {"estado": "VACACIONES"})[0] == 409


def test_cese_no_cruza_tenants_ni_roles_ni_a_si_mismo(tabla, publicados):
    assert estado("emp-000005", {"estado": "CESADO", "fecha_cese": "2026-10-31"}, tenant="pacifico")[0] == 404
    assert estado("emp-000005", {"estado": "CESADO", "fecha_cese": "2026-10-31"}, rol="gerente")[0] == 403
    assert estado("emp-000001", {"estado": "CESADO", "fecha_cese": "2026-10-31"}, empleado_id="emp-000001")[0] == 403
    assert publicados == []
