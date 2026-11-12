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


def test_tenant_opcional_y_campos_obligatorios(tabla):
    r = auth.login({"body": json.dumps({"email": "maria@andina.pe", "password": PWD})})
    assert r["statusCode"] == 200
    assert auth.login({})["statusCode"] == 400
    assert auth.login({"body": "no-es-json"})["statusCode"] == 400


def test_ping(tabla):
    assert json.loads(auth.ping({})["body"])["status"] == "ok"


def test_login_sin_empresa_resuelve_cuenta_en_bd(tabla):
    for email, tenant in [("  MARIA@ANDINA.PE ", "andina"), ("maria@pacifico.pe", "pacifico")]:
        status, body = llamar(None, email, PWD)
        assert status == 200
        assert decode_token(body["token"])["tenant_id"] == tenant


def test_login_no_deduce_empresa_del_dominio(tabla):
    from tests.unit.conftest import usuario
    from src.common.security import hash_password
    tabla.put_item(Item=usuario("sierra", 9, "persona@gmail.com", pwd_hash=hash_password(PWD)))
    status, body = llamar(None, "persona@gmail.com", PWD)
    assert status == 200
    assert decode_token(body["token"])["tenant_id"] == "sierra"


def test_correo_ambiguo_no_elige_empresa(tabla):
    from tests.unit.conftest import usuario
    from src.common.security import hash_password
    tabla.put_item(Item=usuario("pacifico", 9, "maria@andina.pe", pwd_hash=hash_password(PWD)))
    status, body = llamar(None, "maria@andina.pe", PWD)
    assert status == 401
    assert body["error"]["mensaje"] == "Credenciales inválidas"


def test_sin_empresa_respeta_credenciales_y_desactivacion(tabla):
    assert llamar(None, "maria@andina.pe", "incorrecta")[0] == 401
    assert llamar(None, "nadie@andina.pe", PWD)[0] == 401
    assert llamar(None, "luis@andina.pe", PWD)[0] == 403


def test_tipos_invalidos_no_producen_500(tabla):
    for tenant in ["", " ", 123, {}, []]:
        assert llamar(tenant, "maria@andina.pe", PWD)[0] == 400
    for email, password in [(None, PWD), ([], PWD), ("maria@andina.pe", None)]:
        assert llamar(None, email, password)[0] == 400


def test_indice_desactualizado_no_autentica_con_correo_anterior(tabla, monkeypatch):
    from unittest.mock import Mock
    from src.repositories import usuarios_repo
    table = Mock()
    table.query.return_value = {"Items": [{"tenant_id": "andina", "user_id": "usr-000001"}]}
    table.get_item.return_value = {"Item": {"email": "nuevo@andina.pe"}}
    monkeypatch.setattr(usuarios_repo, "_table", lambda: table)
    assert usuarios_repo.get_by_login_email("anterior@andina.pe") is None
    assert table.get_item.call_args.kwargs["ConsistentRead"] is True
