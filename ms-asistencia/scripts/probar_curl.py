#!/usr/bin/env python3
"""Prueba real con curl; usa únicamente cuentas de demo y conserva evidencia E2E."""
import argparse
import getpass
import json
import os
import subprocess
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]


def curl(method, url, body=None, token=None):
    # La configuración entra por stdin para no exponer tokens en los argumentos del proceso.
    config = ['silent', 'show-error', 'connect-timeout = 10', 'max-time = 40',
              'url = ' + json.dumps(url), 'request = ' + json.dumps(method),
              'header = "Content-Type: application/json"', 'write-out = "\\n%{http_code}"']
    if token:
        config.append('header = ' + json.dumps('Authorization: Bearer ' + token))
    if body is not None:
        config.append('data = ' + json.dumps(json.dumps(body)))
    result = subprocess.run(['curl', '--config', '-'], input='\n'.join(config),
                            capture_output=True, text=True, check=True)
    data, status = result.stdout.rsplit('\n', 1)
    try:
        data = json.loads(data)
    except ValueError:
        pass
    return int(status), data


def url_coleccion(name, key='base_url'):
    data = json.loads((ROOT / 'postman' / name).read_text())
    return next(v['value'] for v in data['variable'] if v['key'] == key).rstrip('/')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    password = os.environ.get('HCM_DEMO_PASSWORD') or getpass.getpass('Clave de cuentas demo: ')
    checks = []

    def check(label, method, url, expected, body=None, token=None):
        status, data = curl(method, url, body, token)
        if status != expected:
            raise RuntimeError(f'{label}: esperado HTTP {expected}, recibido {status}: {data}')
        print(f'OK {label}: HTTP {status}', flush=True)
        checks.append({'prueba': label, 'http': status})
        return data

    auth = url_coleccion('ms-usuarios-dev.postman_collection.json')
    sessions = {}
    for key, tenant, cuenta in [('admin', 'andina', 'admin'), ('emp', 'andina', 'empleado'),
                                ('pacifico', 'pacifico', 'admin')]:
        sessions[key] = check('Login ' + key, 'POST', auth + '/auth/login', 200,
            {'tenant_id': tenant, 'email': f'{cuenta}@{tenant}.pe', 'password': password})
        if sessions[key]['usuario']['tenant_id'] != tenant:
            raise RuntimeError('Tenant de login inesperado')
    admin, empleado, pacifico = (sessions[k]['token'] for k in ('admin', 'emp', 'pacifico'))
    emp_id = sessions['emp']['usuario']['empleado_id']
    other = sessions['admin']['usuario']['empleado_id']
    tag = 'E2E-' + uuid.uuid4().hex[:12]
    # Fechas ficticias fuera de la nómina actual; solo se afecta al empleado demo.
    seed = int(uuid.uuid4().hex[:8], 16)
    dia = (date(2020, 1, 1) + timedelta(days=seed % 1000)).isoformat()
    futuro = (date(2035, 1, 1) + timedelta(days=seed % 1000)).isoformat()
    pasado = (date(2020, 1, 1) + timedelta(days=(seed + 1) % 1000)).isoformat()
    check('Ping', 'GET', base + '/ping', 200)
    check('Sin token', 'GET', base + '/marcaciones', 401)
    check('Empleado no marca para otro', 'POST', base + '/marcaciones', 403,
          {'empleado_id': other}, empleado)
    check('Empleado no altera hora', 'POST', base + '/marcaciones', 403,
          {'fecha': dia, 'hora': '09:00'}, empleado)
    mark = {'empleado_id': emp_id, 'fecha': dia, 'hora': '09:25', 'tipo': 'ENTRADA'}
    entrada = check('Entrada manual RRHH', 'POST', base + '/marcaciones', 201, mark, admin)
    if entrada['tardanza_minutos'] != 15:
        raise RuntimeError('Tardanza incorrecta')
    check('Entrada duplicada', 'POST', base + '/marcaciones', 409, mark, admin)
    check('Salida antes de entrada', 'POST', base + '/marcaciones', 400,
          {**mark, 'tipo': 'SALIDA', 'hora': '08:00'}, admin)
    salida = check('Salida y horas', 'POST', base + '/marcaciones', 201,
          {**mark, 'tipo': 'SALIDA', 'hora': '17:55'}, admin)
    if salida['horas'] != 8.5:
        raise RuntimeError('Horas incorrectas')
    check('Salida duplicada', 'POST', base + '/marcaciones', 409,
          {**mark, 'tipo': 'SALIDA', 'hora': '17:55'}, admin)
    query = urlencode({'empleado': emp_id, 'fecha': dia})
    listed = check('Historial propio', 'GET', base + '/marcaciones?' + query, 200, token=empleado)
    if len(listed['items']) != 1:
        raise RuntimeError('Historial no contiene la marcación')
    cross = check('Historial aislado Pacífico', 'GET', base + '/marcaciones?' + query, 200, token=pacifico)
    if cross['items']:
        raise RuntimeError('Marcación visible desde otro tenant')
    check('Historial ajeno prohibido', 'GET', base + '/marcaciones?empleado=' + other, 403, token=empleado)
    check('Resumen diario', 'GET', base + '/asistencia/resumen?fecha=' + dia, 200, token=admin)
    csv = check('Reporte CSV', 'GET', base + '/asistencia/reportes?fecha=' + dia, 200, token=admin)
    if emp_id not in csv or 'hora_entrada' not in csv:
        raise RuntimeError('CSV incompleto')
    check('Reporte solo supervisor', 'GET', base + '/asistencia/reportes', 403, token=empleado)
    saldo = check('Saldo vacaciones', 'GET', base + '/ausencias/saldo/' + emp_id + '?anio=2035', 200, token=empleado)
    check('Body inválido', 'POST', base + '/ausencias', 400, [], empleado)
    ausencia = {'empleado_id': emp_id, 'tipo': 'SIN_GOCE', 'desde': futuro, 'hasta': futuro, 'motivo': tag}
    item = check('Solicitar ausencia', 'POST', base + '/ausencias', 201, ausencia, empleado)
    aus_id = item['ausencia_id']
    ruta = base + '/ausencias/' + aus_id
    check('Cruce de ausencias', 'POST', base + '/ausencias', 409, ausencia, empleado)
    check('Consulta propia', 'GET', ruta + '?empleado=' + emp_id, 200, token=empleado)
    check('Consulta desde Pacífico', 'GET', ruta + '?empleado=' + emp_id, 404, token=pacifico)
    check('Pendientes RRHH', 'GET', base + '/ausencias/pendientes', 200, token=admin)
    cambio = {'empleado_id': emp_id, 'estado': 'APROBADA'}
    check('No autoaprobar', 'PATCH', ruta + '/estado', 403, cambio, empleado)
    check('No aprobar desde otro tenant', 'PATCH', ruta + '/estado', 404, cambio, pacifico)
    check('Aprobar RRHH', 'PATCH', ruta + '/estado', 200, cambio, admin)
    check('Doble aprobación', 'PATCH', ruta + '/estado', 409, cambio, admin)
    check('No finalizar anticipadamente', 'PATCH', ruta + '/estado', 409,
          {**cambio, 'estado': 'FINALIZADA'}, admin)
    check('Ausencia histórica rechazada incluso para RRHH', 'POST', base + '/ausencias', 400,
        {**ausencia, 'tipo': 'PERMISO', 'desde': pasado, 'hasta': pasado}, admin)

    noti = url_coleccion('ms-notificaciones-dev.postman_collection.json', 'baseUrl')
    nomina = url_coleccion('ms-nominas-dev.postman_collection.json')
    nomina_query = urlencode({'empleado_id': emp_id, 'periodo': futuro[:7], 'limit': 200})
    for intento in range(20):
        status, avisos = curl('GET', noti + '/notificaciones?limit=200', token=empleado)
        status2, conceptos = curl('GET', nomina + '/nominas/conceptos?' + nomina_query, token=admin)
        aviso = next((a for a in avisos.get('items', []) if a.get('tipo') == 'AusenciaAprobada'
                      and a.get('metadata', {}).get('empleado_id') == emp_id
                      and a.get('metadata', {}).get('ausencia_id') == aus_id), None) if status == 200 else None
        concepto = next((c for c in conceptos.get('items', []) if c.get('referencia') == 'AUSENCIA-' + aus_id), None) if status2 == 200 else None
        if aviso and concepto:
            print('OK EDA: ausencia aprobada → notificación y concepto SIN_GOCE', flush=True)
            checks.append({'prueba': 'EDA notificación y nómina', 'http': 200})
            break
        if intento == 19:
            raise RuntimeError(f'EDA incompleto: aviso={bool(aviso)}, concepto={bool(concepto)}')
        time.sleep(3)
    report = {'etiqueta': tag, 'empleado_id': emp_id, 'fecha_marcacion': dia,
              'fecha_ausencia': futuro, 'ausencia_id': aus_id, 'checks': checks}
    destination = ROOT / 'docs' / 'prueba_asistencia_curl.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(checks)} comprobaciones aprobadas; evidencia: {destination}', flush=True)


if __name__ == '__main__':
    main()
