"""Reacciones a eventos del topic hcm-eventos. Todas son idempotentes (SQS entrega 'al menos una vez')."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from src.common import events
from src.common.errors import Conflicto, Validacion
from src.repositories import empleados_repo as repo
from src.services import empleados_service as svc

log = logging.getLogger()


def _tenant(evt):
    t = evt.get("tenant_id")
    if not isinstance(t, str) or not t.strip():
        raise Validacion("Evento sin tenant_id")
    return t.strip()


def _empleado_id(evt):
    e = (evt.get("datos") or {}).get("empleado_id")
    if not isinstance(e, str) or not e.strip():
        raise Validacion("Evento %s sin empleado_id" % evt.get("tipo_evento"))
    return e.strip()


def postulante_contratado(evt):
    """Crea el empleado. El id se deriva de la postulación (emp-p<n>), así un evento repetido no duplica nada."""
    tenant = _tenant(evt)
    d = dict(evt.get("datos") or {})
    post = d.get("postulacion_id")
    if not isinstance(post, str) or "-" not in post:
        raise Validacion("PostulanteContratado sin postulacion_id válido")
    empleado_id = "emp-p" + post.split("-", 1)[1]
    item, creado = svc.construir_y_guardar(tenant, d, empleado_id=empleado_id)
    log.info("Empleado %s %s desde %s (%s)", empleado_id, "creado" if creado else "ya existía", post, tenant)
    # Se publica siempre: si la primera vez falló el publish, el reintento lo repara (los consumidores son idempotentes)
    events.publish_event("EmpleadoCreado", tenant, svc.datos_evento_creado(item), origen="ms-empleados")


def ausencia_aprobada(evt):
    tenant, empleado_id = _tenant(evt), _empleado_id(evt)
    if (evt.get("datos") or {}).get("tipo") != "VACACIONES":
        return  # permisos sin goce, etc.: no cambian el estado
    datos = evt.get("datos") or {}
    hoy = datetime.now(ZoneInfo("America/Lima")).date().isoformat()
    if datos.get("desde") and datos.get("hasta") and not datos["desde"] <= hoy <= datos["hasta"]:
        return  # ms-asistencia vuelve a publicar al comenzar las vacaciones.
    actual = repo.get(tenant, empleado_id)
    if not actual or actual["estado"] != "ACTIVO":
        log.info("AusenciaAprobada ignorada para %s (%s)", empleado_id, actual and actual["estado"])
        return
    try:
        repo.update(tenant, empleado_id, {"estado": "VACACIONES"}, estado_actual="ACTIVO")
    except Conflicto:
        return  # otro proceso ya lo cambió


def ausencia_finalizada(evt):
    """Devuelve a ACTIVO a quien volvió de vacaciones, sin alterar cesados ni permisos."""
    tenant, empleado_id = _tenant(evt), _empleado_id(evt)
    if (evt.get("datos") or {}).get("tipo", "VACACIONES") != "VACACIONES":
        return
    actual = repo.get(tenant, empleado_id)
    if not actual or actual["estado"] != "VACACIONES":
        return
    try:
        repo.update(tenant, empleado_id, {"estado": "ACTIVO"}, estado_actual="VACACIONES")
    except Conflicto:
        return


HANDLERS = {"PostulanteContratado": postulante_contratado,
            "AusenciaAprobada": ausencia_aprobada,
            "AusenciaFinalizada": ausencia_finalizada}


def procesar(evt):
    fn = HANDLERS.get(evt.get("tipo_evento"))
    if fn is None:
        log.info("Evento %s ignorado", evt.get("tipo_evento"))
        return
    fn(evt)
