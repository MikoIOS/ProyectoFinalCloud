from src.common.auth import contexto
from src.common.response import api, json_body, ok, pdf_response
from src.services import liquidacion as liq
from src.services import planillas as svc


def _qs(event):
    return event.get("queryStringParameters") or {}


@api
def generar(event, context=None):
    ctx = contexto(event, ("admin_rrhh",))
    return ok(svc.generar(ctx, json_body(event)), 202)


@api
def listar(event, context=None):
    ctx = contexto(event, ("admin_rrhh", "gerente"))
    return ok(svc.listar_nominas(ctx, _qs(event)))


@api
def resumen(event, context=None):
    ctx = contexto(event, ("admin_rrhh", "gerente"))
    return ok(svc.resumen(ctx, _qs(event)))


@api
def planillas(event, context=None):
    ctx = contexto(event, ("admin_rrhh", "gerente"))
    return ok(svc.listar_planillas(ctx, _qs(event)))


@api
def planilla(event, context=None):
    ctx = contexto(event, ("admin_rrhh", "gerente"))
    periodo = (event.get("pathParameters") or {}).get("periodo", "")
    return ok(svc.obtener_planilla(ctx, periodo))


@api
def empleado(event, context=None):
    ctx = contexto(event)
    empleado_id = (event.get("pathParameters") or {}).get("empleado_id", "")
    return ok(svc.nominas_empleado(ctx, empleado_id, _qs(event)))


@api
def liquidacion(event, context=None):
    ctx = contexto(event)
    empleado_id = (event.get("pathParameters") or {}).get("empleado_id", "")
    return ok(liq.obtener(ctx, empleado_id))


@api
def detalle(event, context=None):
    ctx = contexto(event)
    nomina_id = (event.get("pathParameters") or {}).get("nomina_id", "")
    return ok(svc.obtener_nomina(ctx, nomina_id))


@api
def boleta(event, context=None):
    ctx = contexto(event)
    nomina_id = (event.get("pathParameters") or {}).get("nomina_id", "")
    resultado = svc.boleta(ctx, nomina_id, _qs(event))
    if isinstance(resultado, tuple):
        contenido, nombre = resultado
        return pdf_response(contenido, nombre)
    return ok(resultado)
