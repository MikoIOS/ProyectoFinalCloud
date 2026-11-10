#!/usr/bin/env python3
"""Prueba HTTP de evaluación -> SNS/SQS -> notificación en dev.

Crea una evaluación identificada con E2E y deja sus notificaciones como evidencia.
Las URLs se leen de las colecciones Postman del repositorio.
"""
import getpass
import json
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def base_url(coleccion, variable):
    datos = json.loads((ROOT / "postman" / coleccion).read_text())
    return next(v["value"] for v in datos["variable"] if v["key"] == variable).rstrip("/")


def http(method, url, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(url, data=json.dumps(body).encode() if body is not None else None,
                  headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as res:
            return res.status, json.load(res)
    except HTTPError as error:
        return error.code, None


def comprobar(condicion, mensaje):
    if not condicion:
        raise RuntimeError(mensaje)


def login(url, tenant):
    email = input(f"Email de usuario de prueba ({tenant}): ").strip()
    password = getpass.getpass(f"Contraseña ({tenant}): ")
    status, datos = http("POST", url + "/auth/login", {
        "tenant_id": tenant, "email": email, "password": password,
    })
    comprobar(status == 200, f"Login {tenant}: HTTP {status}")
    comprobar(datos["usuario"]["tenant_id"] == tenant, "Tenant de login inesperado")
    return datos


def probar(desempeno, notificaciones, andina, pacifico):
    token = andina["token"]
    usuario = andina["usuario"]
    comprobar(usuario["rol"] == "admin_rrhh", "Usa un admin_rrhh de prueba de andina")
    user_id = usuario["user_id"]
    comprobar(user_id.startswith("usr-"), "La prueba requiere un user_id con prefijo usr-")
    etiqueta = "E2E-" + uuid.uuid4().hex[:12]
    # El consumidor deriva usr-X de emp-X; el evaluador recibe el aviso de prueba.
    status, evaluacion = http("POST", desempeno + "/evaluaciones", {
        "empleado_id": "emp-" + etiqueta,
        "evaluador_id": "emp-" + user_id[4:],
        "periodo": etiqueta,
        "comentarios": "Prueba E2E de notificaciones; no es una evaluación laboral real",
    }, token)
    comprobar(status == 201, f"Crear evaluación: HTTP {status}")
    eva_id = evaluacion["evaluacion_id"]
    print(f"Evaluación de prueba: {eva_id} ({etiqueta})", flush=True)
    status, _ = http("PUT", desempeno + "/evaluaciones/" + eva_id,
                     {"estado": "COMPLETADA", "puntaje": 4}, token)
    comprobar(status == 200, f"Completar evaluación: HTTP {status}")

    aviso = None
    for intento in range(20):
        status, datos = http("GET", notificaciones + "/notificaciones?limit=200", token=token)
        comprobar(status == 200, f"Listar notificaciones: HTTP {status}")
        aviso = next((n for n in datos["items"]
                      if n.get("metadata", {}).get("evaluacion_id") == eva_id
                      and n.get("destinatario_id") == user_id), None)
        if aviso:
            break
        if intento < 19:
            time.sleep(3)
    comprobar(aviso is not None, "No apareció la notificación en HTTP tras 20 consultas")
    comprobar(aviso["tenant_id"] == "andina", "La notificación tiene otro tenant")
    comprobar(aviso["tipo"] == "EvaluacionCompletada", "Tipo de evento inesperado")
    comprobar(aviso["leida"] is False, "La notificación nueva ya figura leída")
    ruta = notificaciones + "/notificaciones/" + aviso["notificacion_id"] + "/leida"
    status, _ = http("PATCH", ruta, {}, pacifico["token"])
    comprobar(status in (403, 404), f"Acceso desde pacifico: HTTP {status}; se esperaba 403/404")
    status, _ = http("GET", notificaciones + "/notificaciones")
    comprobar(status == 401, f"Acceso sin token: HTTP {status}; se esperaba 401")
    status, leida = http("PATCH", ruta, {}, token)
    comprobar(status == 200, f"Marcar leída: HTTP {status}")
    comprobar(leida.get("leida") is True, "No se confirmó la lectura")
    print("OK: evaluación → notificación HTTP → lectura; acceso cruzado y anónimo rechazados")


def main():
    auth = base_url("ms-usuarios-dev.postman_collection.json", "base_url")
    desempeno = base_url("ms-desempeno-dev.postman_collection.json", "base_url")
    notificaciones = base_url("ms-notificaciones-dev.postman_collection.json", "baseUrl")
    print("Prueba sobre dev: crea una evaluación E2E y sus notificaciones.")
    probar(desempeno, notificaciones, login(auth, "andina"), login(auth, "pacifico"))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, KeyError, ValueError) as error:
        raise SystemExit(f"FALLO: {error}") from None
