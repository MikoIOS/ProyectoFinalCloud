import json

from src.common.security import decode_token
from src.handlers import auth
from tests.unit.conftest import PWD


def llamar(tenant, email, password):
    body = json.dumps({"tenant_id": tenant, "email": email, "password": password})
    r = auth.login({"body": body})
    return r["statusCode"], json.loads(r["body"])


def test_login_ok_devuelve_jwt_con_claims(tabla):
    status, body = llamar("andina", "maria@andina.pe", PWD)
    assert status == 200
    claims = decode_token(body["token"])
    assert claims["tenant_id"] == "andina"
    assert claims["rol"] == "admin_rrhh"
    assert claims["sub"] == "usr-000001"
    assert claims["empleado_id"] == "emp-000001"
    assert claims["exp"] - claims["iat"] == 28800
    assert body["usuario"]["tenant_id"] == "andina"
    assert "password_hash" not in json.dumps(body)


def test_email_se_normaliza_a_minusculas(tabla):
    status, _ = llamar("andina", "  MARIA@Andina.pe ", PWD)
    assert status == 200


def test_password_incorrecta_y_email_inexistente_dan_el_mismo_error(tabla):
    s1, b1 = llamar("andina", "maria@andina.pe", "mala")
    s2, b2 = llamar("andina", "nadie@andina.pe", PWD)
    assert s1 == s2 == 401
    assert b1 == b2


def test_usuario_desactivado_403(tabla):
    status, body = llamar("andina", "luis@andina.pe", PWD)
    assert status == 403
    assert body["error"]["codigo"] == "PROHIBIDO"


def test_aislamiento_entre_tenants(tabla):
    # El email existe solo en andina: con tenant pacifico no debe entrar
    status, _ = llamar("pacifico", "maria@andina.pe", PWD)
    assert status == 401
    # Mismo usuario n=1 en ambos tenants: el token lleva el tenant correcto
    _, body = llamar("pacifico", "maria@pacifico.pe", PWD)
    assert decode_token(body["token"])["tenant_id"] == "pacifico"
    assert decode_token(body["token"])["rol"] == "gerente"


def test_campos_faltantes_400(tabla):
    r = auth.login({"body": json.dumps({"email": "maria@andina.pe", "password": PWD})})
    assert r["statusCode"] == 400
    assert auth.login({})["statusCode"] == 400
    assert auth.login({"body": "no-es-json"})["statusCode"] == 400


def test_ping(tabla):
    assert json.loads(auth.ping({})["body"])["status"] == "ok"
