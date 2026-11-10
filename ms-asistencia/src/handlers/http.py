import csv
import io

from src.common.auth import contexto, propio_o_supervisor
from src.common.errors import Validacion
from src.common.response import api, json_body, ok
from src.repositories import asistencia as repo
from src.services import asistencia as svc


def qs(event):
    return event.get('queryStringParameters') or {}


@api
def ping(event, context=None):
    return ok({'service': 'ms-asistencia', 'status': 'ok'})


@api
def marcar(event, context=None):
    return ok(svc.marcar(contexto(event), json_body(event)), 201)


def listado(event, clase, pendientes=False):
    ctx = contexto(event)
    query = dict(qs(event))
    emp = query.get('empleado')
    aprobador = None
    if pendientes:
        if ctx.rol != 'admin_rrhh':
            aprobador = svc.emp_id(ctx.empleado_id)
    elif emp or ctx.rol not in ('admin_rrhh', 'gerente'):
        emp = svc.acceso_lectura(ctx, emp)
    if emp:
        svc.emp_id(emp)
    if query.get('fecha'):
        svc.fecha(query['fecha'])
    return repo.listar(ctx.tenant_id, clase, query, emp, pendientes, aprobador)


@api
def marcaciones(event, context=None):
    return ok(listado(event, 'MAR'))


@api
def solicitar(event, context=None):
    return ok(svc.solicitar(contexto(event), json_body(event)), 201)


@api
def ausencias(event, context=None):
    return ok(listado(event, 'AUS'))


@api
def pendientes(event, context=None):
    return ok(listado(event, 'AUS', True))


@api
def ausencia(event, context=None):
    return ok(svc.obtener(contexto(event), event['pathParameters']['ausencia_id'], qs(event).get('empleado')))


@api
def resolver(event, context=None):
    return ok(svc.resolver(contexto(event), event['pathParameters']['ausencia_id'], json_body(event)))


@api
def saldo(event, context=None):
    ctx = contexto(event)
    emp = svc.acceso_lectura(ctx, event['pathParameters']['empleado_id'])
    repo.empleado(ctx.tenant_id, emp)
    try:
        year = int(qs(event).get('anio', svc.ahora().year))
        if not 1900 <= year <= 9998:
            raise ValueError
    except (ValueError, TypeError):
        raise Validacion('anio debe ser un entero entre 1900 y 9998')
    return ok({'empleado_id': emp, **svc.saldo_de(repo.ausencias(ctx.tenant_id, emp), year)})


def registros_dia(ctx, dia):
    query = {'fecha': dia, 'limit': 200}
    while True:
        page = repo.listar(ctx.tenant_id, 'MAR', query)
        yield from page['items']
        if not page['next_token']:
            return
        query['next_token'] = page['next_token']


@api
def resumen(event, context=None):
    ctx = contexto(event, ('admin_rrhh', 'gerente'))
    dia = svc.fecha(qs(event).get('fecha', svc.ahora().date().isoformat())).isoformat()
    items = list(registros_dia(ctx, dia))
    return ok({'fecha': dia, 'marcaciones': len(items), 'tardanzas': sum(i['tarde'] for i in items),
               'abiertas': sum(i['estado'] == 'ABIERTA' for i in items),
               'horas': sum(i.get('horas', 0) for i in items)})


@api
def reporte(event, context=None):
    ctx = contexto(event, ('admin_rrhh', 'gerente'))
    dia = svc.fecha(qs(event).get('fecha', svc.ahora().date().isoformat())).isoformat()
    output = io.StringIO()
    columns = ['empleado_id', 'fecha', 'hora_entrada', 'hora_salida', 'horas', 'tardanza_minutos', 'estado']
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(registros_dia(ctx, dia))
    return {'statusCode': 200, 'headers': {'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': f'attachment; filename="asistencia-{dia}.csv"',
            'Access-Control-Allow-Origin': '*'}, 'body': output.getvalue()}
