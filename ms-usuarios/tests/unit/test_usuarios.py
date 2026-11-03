import json

from src.handlers import auth, usuarios
from tests.unit.conftest import PWD, http, respuesta

NUEVO = {"nombre": "Rosa Díaz", "email": "Rosa.Diaz@Andina.pe", "password": "Clave12345", "rol": "reclutador"}


def crear(tenant="andina", como="admin_rrhh", **body):
    """`como` = rol de quien llama; `rol` (en body) = rol del usuario que se crea."""
    return respuesta(usuarios.crear(http(tenant=tenant, rol=como, body=dict(NUEVO, **body))))


# ---------- crear ----------
def test_crear_ok_sin_exponer_hash(tabla):
    status, b = crear()
    assert status == 201
    assert b["email"] == "rosa.diaz@andina.pe" and b["tenant_id"] == "andina"
    assert b["activo"] is True and b["debe_cambiar_password"] is True
    assert "password_hash" not in b
    # puede iniciar sesión
    r = auth.login({"body": json.dumps({"tenant_id": "andina", "email": "rosa.diaz@andina.pe", "password": "Clave12345"})})
    assert r["statusCode"] == 200


def test_crear_ignora_tenant_del_body(tabla):
    status, b = crear(tenant_id="pacifico")
    assert status == 201 and b["tenant_id"] == "andina"
    assert tabla.get_item(Key={"tenant_id": "pacifico", "user_id": b["user_id"]}).get("Item") is None


def test_email_duplicado_409_pero_ok_en_otro_tenant(tabla):
    assert crear()[0] == 201
    status, b = crear()
    assert status == 409 and b["error"]["codigo"] == "CONFLICTO"
    assert crear(tenant="pacifico")[0] == 201      # único por tenant, no global


def test_crear_validaciones(tabla):
    assert crear(rol="superadmin")[0] == 400
    assert crear(password="corta")[0] == 400
    assert crear(email="no-es-email")[0] == 400
    assert crear(nombre="  ")[0] == 400


def test_crear_requiere_admin(tabla):
    for como in ("gerente", "reclutador", "empleado"):
        assert crear(como=como)[0] == 403
    assert respuesta(usuarios.crear({"body": "{}"}))[0] == 401   # sin contexto del Authorizer


# ---------- listar ----------
def test_listar_pagina_y_filtra(tabla):
    for i in range(5):
        crear(email="u%d@andina.pe" % i)
    status, b = respuesta(usuarios.listar(http(qs={"limit": "3"})))
    assert status == 200 and len(b["items"]) == 3 and b["next_token"]
    vistos = [i["user_id"] for i in b["items"]]
    while b["next_token"]:
        _, b = respuesta(usuarios.listar(http(qs={"limit": "3", "next_token": b["next_token"]})))
        vistos += [i["user_id"] for i in b["items"]]
    assert len(vistos) == len(set(vistos)) == 8            # 3 del fixture en andina + 5 creados
    _, b = respuesta(usuarios.listar(http(qs={"rol": "reclutador"})))
    assert len(b["items"]) == 5 and all(i["rol"] == "reclutador" for i in b["items"])
    _, b = respuesta(usuarios.listar(http(qs={"activo": "false"})))
    assert [i["email"] for i in b["items"]] == ["luis@andina.pe"]


def test_listar_solo_ve_su_tenant(tabla):
    _, b = respuesta(usuarios.listar(http(tenant="pacifico", user_id="usr-000001")))
    assert [i["email"] for i in b["items"]] == ["maria@pacifico.pe"]
    assert all(i["tenant_id"] == "pacifico" for i in b["items"])


def test_listar_validaciones(tabla):
    assert respuesta(usuarios.listar(http(qs={"limit": "0"})))[0] == 400
    assert respuesta(usuarios.listar(http(qs={"limit": "abc"})))[0] == 400
    assert respuesta(usuarios.listar(http(qs={"rol": "x"})))[0] == 400
    assert respuesta(usuarios.listar(http(qs={"next_token": "basura"})))[0] == 400


def test_next_token_de_otro_tenant_se_rechaza(tabla):
    for i in range(3):
        crear(email="t%d@andina.pe" % i)
    _, b = respuesta(usuarios.listar(http(qs={"limit": "2"})))
    status, _ = respuesta(usuarios.listar(http(tenant="pacifico", qs={"next_token": b["next_token"]})))
    assert status == 400


# ---------- obtener ----------
def test_obtener_y_aislamiento(tabla):
    assert respuesta(usuarios.obtener(http(id="usr-000003")))[1]["email"] == "ana@andina.pe"
    # usr-000002 existe en andina; con token de pacifico (que no tiene ese id) => 404, no 403
    assert respuesta(usuarios.obtener(http(tenant="pacifico", id="usr-000002")))[0] == 404
    assert respuesta(usuarios.obtener(http(id="usr-999999")))[0] == 404


# ---------- actualizar ----------
def test_actualizar_rol_nombre_y_activo(tabla):
    status, b = respuesta(usuarios.actualizar(http(id="usr-000003", body={"rol": "gerente", "nombre": "Ana P."})))
    assert status == 200 and b["rol"] == "gerente" and b["nombre"] == "Ana P."
    _, b = respuesta(usuarios.actualizar(http(id="usr-000003", body={"activo": False})))
    assert b["activo"] is False
    r = auth.login({"body": json.dumps({"tenant_id": "andina", "email": "ana@andina.pe", "password": PWD})})
    assert r["statusCode"] == 403                           # desactivado no entra


def test_actualizar_restricciones(tabla):
    assert respuesta(usuarios.actualizar(http(id="usr-000003", body={"email": "x@y.pe"})))[0] == 400
    assert respuesta(usuarios.actualizar(http(id="usr-000003", body={"rol": "dios"})))[0] == 400
    assert respuesta(usuarios.actualizar(http(id="usr-000003", body={"activo": "no"})))[0] == 400
    assert respuesta(usuarios.actualizar(http(id="usr-000003", body={})))[0] == 400
    # un admin no se desactiva ni se cambia el rol a sí mismo
    assert respuesta(usuarios.actualizar(http(id="usr-000001", body={"activo": False})))[0] == 403
    assert respuesta(usuarios.actualizar(http(id="usr-000001", body={"rol": "empleado"})))[0] == 403
    # no se puede tocar un usuario de otro tenant
    assert respuesta(usuarios.actualizar(http(tenant="pacifico", user_id="usr-000001", id="usr-000003",
                                              body={"activo": False})))[0] == 404
    assert tabla.get_item(Key={"tenant_id": "andina", "user_id": "usr-000003"})["Item"]["activo"] is True
    assert respuesta(usuarios.actualizar(http(rol="empleado", id="usr-000003", body={"activo": False})))[0] == 403


# ---------- me / cambiar password ----------
def test_mi_usuario(tabla):
    status, b = respuesta(usuarios.mi_usuario(http(rol="empleado", user_id="usr-000003")))
    assert status == 200 and b["email"] == "ana@andina.pe" and "password_hash" not in b


def test_cambiar_password(tabla):
    def cambiar(actual, nueva):
        body = {"password_actual": actual, "password_nueva": nueva}
        return respuesta(auth.cambiar_password(http(rol="empleado", user_id="usr-000003", body=body)))[0]

    assert cambiar("incorrecta", "NuevaClave99") == 401
    assert cambiar(PWD, "corta") == 400
    assert cambiar(PWD, PWD) == 400
    assert cambiar(PWD, "NuevaClave99") == 200

    def login(p):
        return auth.login({"body": json.dumps({"tenant_id": "andina", "email": "ana@andina.pe", "password": p})})["statusCode"]

    assert login(PWD) == 401 and login("NuevaClave99") == 200
