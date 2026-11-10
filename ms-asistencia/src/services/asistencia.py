import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from botocore.exceptions import ClientError

from src.common.auth import propio_o_supervisor
from src.common.errors import Conflicto, NoEncontrado, Prohibido, Validacion
from src.repositories import asistencia as repo

ZONA = ZoneInfo('America/Lima')
TIPOS = {'VACACIONES', 'PERMISO', 'LICENCIA_MEDICA', 'SIN_GOCE'}
ESTADOS = {'APROBADA', 'RECHAZADA', 'CANCELADA', 'FINALIZADA'}


def ahora():
    return datetime.now(ZONA)


def fecha(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise Validacion('Fecha inválida; usa YYYY-MM-DD')


def texto(value, nombre, maximo=500):
    if not isinstance(value, str) or not value.strip() or len(value) > maximo:
        raise Validacion(f'{nombre} debe ser texto de 1 a {maximo} caracteres')
    return value.strip()


def emp_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'emp-[a-zA-Z0-9_-]{1,100}', value):
        raise Validacion('empleado_id inválido')
    return value


def objetivo(ctx, body):
    emp = emp_id(body.get('empleado_id') or ctx.empleado_id)
    if emp != ctx.empleado_id and ctx.rol != 'admin_rrhh':
        raise Prohibido('Solo RR.HH. puede registrar para otro empleado')
    e = repo.empleado(ctx.tenant_id, emp)
    if e.get('estado') == 'CESADO':
        raise Conflicto('El empleado está cesado')
    return emp, e


def acceso_lectura(ctx, emp):
    emp = emp_id(emp or ctx.empleado_id)
    propio_o_supervisor(ctx, emp)
    return emp


def marcar(ctx, body):
    emp, _ = objetivo(ctx, body)
    now = ahora()
    if ctx.rol != 'admin_rrhh' and ('fecha' in body or 'hora' in body):
        raise Prohibido('Solo RR.HH. puede indicar fecha u hora manual')
    dia = fecha(body['fecha']) if 'fecha' in body else now.date()
    try:
        raw = body.get('hora', now.strftime('%H:%M'))
        if not isinstance(raw, str) or not re.fullmatch(r'\d{2}:\d{2}', raw):
            raise ValueError
        hora = time.fromisoformat(raw)
    except (ValueError, TypeError):
        raise Validacion('Hora inválida; usa HH:MM')
    if datetime.combine(dia, hora, ZONA) > now:
        raise Validacion('No se puede marcar en el futuro')
    sk = f'EMP#{emp}#MAR#{dia.isoformat()}'
    actual = repo.get(ctx.tenant_id, sk)
    tipo = body.get('tipo') or ('SALIDA' if actual else 'ENTRADA')
    if tipo not in ('ENTRADA', 'SALIDA'):
        raise Validacion('tipo debe ser ENTRADA o SALIDA')
    if tipo == 'ENTRADA':
        if actual:
            raise Conflicto('Ya existe una entrada ese día')
        tarde = max(0, hora.hour * 60 + hora.minute - (9 * 60 + 10))
        item = {'tenant_id': ctx.tenant_id, 'sk': sk, 'clase': 'MAR', 'empleado_id': emp,
                'fecha': dia.isoformat(), 'hora_entrada': hora.isoformat(timespec='minutes'),
                'estado': 'ABIERTA', 'tardanza_minutos': tarde, 'tarde': tarde > 0,
                'registrado_por': ctx.user_id}
        try:
            repo.tabla().put_item(Item=item, ConditionExpression='attribute_not_exists(sk)')
        except ClientError as error:
            if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise Conflicto('Ya existe una entrada ese día') from error
            raise
        return item
    if not actual:
        raise Conflicto('Primero registra la entrada')
    if actual.get('hora_salida'):
        raise Conflicto('Ya existe una salida ese día')
    entrada = time.fromisoformat(actual['hora_entrada'])
    minutos = hora.hour * 60 + hora.minute - entrada.hour * 60 - entrada.minute
    if minutos < 0:
        raise Validacion('La salida no puede ser anterior a la entrada')
    try:
        res = repo.tabla().update_item(Key={'tenant_id': ctx.tenant_id, 'sk': sk},
            UpdateExpression='SET hora_salida = :h, horas = :n, #e = :e',
            ConditionExpression='attribute_exists(sk) AND attribute_not_exists(hora_salida)',
            ExpressionAttributeNames={'#e': 'estado'},
            ExpressionAttributeValues={':h': hora.isoformat(timespec='minutes'),
                ':n': (Decimal(minutos) / 60).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), ':e': 'CERRADA'},
            ReturnValues='ALL_NEW')
        return res['Attributes']
    except ClientError as error:
        if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise Conflicto('Ya existe una salida ese día') from error
        raise


def dias_en_anio(item, year):
    desde = max(fecha(item['desde']), date(year, 1, 1))
    hasta = min(fecha(item['hasta']), date(year, 12, 31))
    return max(0, (hasta - desde).days + 1)


def saldo_de(items, year):
    vacaciones = [a for a in items if a['tipo'] == 'VACACIONES']
    pendientes = sum(dias_en_anio(a, year) for a in vacaciones if a['estado'] == 'PENDIENTE')
    usados = sum(dias_en_anio(a, year) for a in vacaciones if a['estado'] in ('APROBADA', 'FINALIZADA'))
    return {'anio': year, 'dias_asignados': 30, 'dias_usados': usados,
            'dias_pendientes': pendientes, 'dias_disponibles': 30 - usados - pendientes}


def solicitar(ctx, body):
    emp, e = objetivo(ctx, body)
    tipo = body.get('tipo')
    if not isinstance(tipo, str) or tipo not in TIPOS:
        raise Validacion('tipo debe ser VACACIONES, PERMISO, LICENCIA_MEDICA o SIN_GOCE')
    desde, hasta = fecha(body.get('desde')), fecha(body.get('hasta'))
    dias = (hasta - desde).days + 1
    if not 1 <= dias <= 90:
        raise Validacion('La ausencia debe durar entre 1 y 90 días calendario')
    if ctx.rol != 'admin_rrhh' and desde < ahora().date() - timedelta(days=30):
        raise Validacion('No se puede solicitar con más de 30 días de antigüedad')
    motivo = texto(body.get('motivo'), 'motivo')
    version = repo.version(ctx.tenant_id, emp)
    items = repo.ausencias(ctx.tenant_id, emp)
    if any(a['estado'] in ('PENDIENTE', 'APROBADA') and a['desde'] <= hasta.isoformat()
           and a['hasta'] >= desde.isoformat() for a in items):
        raise Conflicto('La solicitud se cruza con otra ausencia vigente')
    if tipo == 'VACACIONES':
        for year in range(desde.year, hasta.year + 1):
            requeridos = dias_en_anio({'desde': desde.isoformat(), 'hasta': hasta.isoformat()}, year)
            if requeridos > saldo_de(items, year)['dias_disponibles']:
                raise Conflicto('Saldo de vacaciones insuficiente')
    aus_id = 'aus-' + uuid.uuid4().hex
    item = {'tenant_id': ctx.tenant_id, 'sk': f'EMP#{emp}#AUS#{aus_id}', 'clase': 'AUS',
            'ausencia_id': aus_id, 'empleado_id': emp, 'tipo': tipo, 'con_goce': tipo != 'SIN_GOCE',
            'nombre_empleado': f"{e.get('nombres', '')} {e.get('apellidos', '')}".strip() or emp,
            'desde': desde.isoformat(), 'hasta': hasta.isoformat(), 'dias': dias,
            'motivo': motivo, 'estado': 'PENDIENTE', 'solicitado_por': ctx.user_id,
            'aprobador_id': e.get('jefe_id') or '', 'updated_at': ahora().isoformat()}
    return repo.guardar_ausencia(item, version)


def obtener(ctx, aus_id, emp):
    emp = emp_id(emp)
    if not isinstance(aus_id, str) or not re.fullmatch(r'aus-[a-f0-9]{32}', aus_id):
        raise Validacion('ausencia_id inválido')
    item = repo.get(ctx.tenant_id, f'EMP#{emp}#AUS#{aus_id}')
    if not item:
        raise NoEncontrado('Ausencia no encontrada')
    if ctx.rol not in ('admin_rrhh', 'gerente') and ctx.empleado_id not in (emp, item.get('aprobador_id')):
        raise Prohibido('No puedes consultar esta ausencia')
    return item


def resolver(ctx, aus_id, body):
    # Leer la versión antes de la ausencia permite detectar modificaciones concurrentes.
    emp = emp_id(body.get('empleado_id'))
    version = repo.version(ctx.tenant_id, emp)
    item = obtener(ctx, aus_id, emp)
    estado = body.get('estado')
    if not isinstance(estado, str) or estado not in ESTADOS:
        raise Validacion('estado debe ser APROBADA, RECHAZADA, CANCELADA o FINALIZADA')
    if estado == 'CANCELADA':
        if ctx.rol != 'admin_rrhh' and ctx.empleado_id != emp:
            raise Prohibido('Solo el solicitante o RR.HH. puede cancelar')
    else:
        if ctx.empleado_id == emp:
            raise Prohibido('No puedes resolver tu propia ausencia')
        if ctx.rol != 'admin_rrhh' and (not ctx.empleado_id or ctx.empleado_id != item.get('aprobador_id')):
            raise Prohibido('Solo el jefe directo o RR.HH. puede resolver')
    if estado == 'FINALIZADA':
        if item['estado'] != 'APROBADA' or fecha(item['hasta']) >= ahora().date():
            raise Conflicto('Solo se finalizan ausencias aprobadas cuyo último día ya terminó')
    elif item['estado'] != 'PENDIENTE':
        raise Conflicto('La solicitud ya fue resuelta')
    if estado == 'APROBADA':
        if repo.empleado(ctx.tenant_id, emp).get('estado') == 'CESADO':
            raise Conflicto('El empleado está cesado')
    comentario = body.get('comentario', '')
    if not isinstance(comentario, str) or len(comentario) > 500:
        raise Validacion('comentario debe ser texto de hasta 500 caracteres')
    item.update(estado=estado, comentario=comentario, resuelto_por=ctx.user_id, updated_at=ahora().isoformat())
    if estado == 'APROBADA' and item['tipo'] == 'VACACIONES':
        item['iniciada'] = item['desde'] <= ahora().date().isoformat() <= item['hasta']
    return repo.guardar_ausencia(item, version)
