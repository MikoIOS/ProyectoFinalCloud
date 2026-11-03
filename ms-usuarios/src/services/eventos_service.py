"""Reacciones a eventos del topic hcm-eventos. Todas son idempotentes (SQS entrega 'al menos una vez')."""
import logging

from src.common.errors import Conflicto, Validacion
from src.common.security import hash_password
from src.repositories import usuarios_repo

log = logging.getLogger()


def _datos(evt, *campos):
    datos = evt.get("datos") or {}
    faltan = [c for c in campos if not isinstance(datos.get(c), str) or not datos[c].strip()]
    if faltan:
        raise Validacion("Evento %s sin campos: %s" % (evt.get("tipo_evento"), ", ".join(faltan)))
    return datos


def _tenant(evt):
    t = evt.get("tenant_id")
    if not isinstance(t, str) or not t.strip():
        raise Validacion("Evento sin tenant_id")
    return t.strip()


def empleado_creado(evt):
    tenant = _tenant(evt)
    d = _datos(evt, "empleado_id", "email", "nombres", "apellidos", "documento")
    empleado_id = d["empleado_id"].strip()
    if not empleado_id.startswith("emp-"):
        raise Validacion("empleado_id con formato inesperado: %s" % empleado_id)
    user_id = "usr-" + empleado_id[4:]  # determinista => idempotente

    existente = usuarios_repo.get_by_email(tenant, d["email"])
    if existente and existente["user_id"] != user_id:
        # Email tomado por otro usuario: no se arregla reintentando; que termine en la DLQ para revisión.
        raise Conflicto("El email %s ya pertenece a otro usuario del tenant" % d["email"])

    try:
        usuarios_repo.put_new({
            "tenant_id": tenant,
            "user_id": user_id,
            "email": d["email"].strip().lower(),
            # contraseña inicial = documento (solo para el curso); debe cambiarla al entrar
            "password_hash": hash_password(d["documento"].strip()),
            "nombre": ("%s %s" % (d["nombres"], d["apellidos"])).strip(),
            "rol": "empleado",
            "activo": True,
            "empleado_id": empleado_id,
            "debe_cambiar_password": True,
        })
        log.info("Usuario %s creado para %s (%s)", user_id, empleado_id, tenant)
    except Conflicto:
        log.info("Usuario %s ya existía; evento duplicado ignorado", user_id)


def empleado_cesado(evt):
    tenant = _tenant(evt)
    d = _datos(evt, "empleado_id")
    user_id = usuarios_repo.get_user_id_by_empleado(tenant, d["empleado_id"].strip())
    if not user_id:
        log.info("EmpleadoCesado: %s no tiene usuario en %s; nada que hacer", d["empleado_id"], tenant)
        return
    usuarios_repo.update(tenant, user_id, {"activo": False})
    log.info("Usuario %s desactivado por cese de %s", user_id, d["empleado_id"])


HANDLERS = {"EmpleadoCreado": empleado_creado, "EmpleadoCesado": empleado_cesado}


def procesar(evt):
    fn = HANDLERS.get(evt.get("tipo_evento"))
    if fn is None:
        log.info("Evento %s ignorado", evt.get("tipo_evento"))
        return
    fn(evt)
