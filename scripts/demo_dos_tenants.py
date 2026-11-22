#!/usr/bin/env python3
"""Demo HTTP de dev con curl: dos empresas nuevas, EDA y aislamiento.

Crea datos ficticios persistentes. Guarda credenciales y evidencia en hcm/.runtime,
ignorado por Git. No usa boto3 ni consulta tablas directamente.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
from datetime import date
from urllib.parse import quote

BASE = 'https://mwxvk1jpd3.execute-api.us-east-1.amazonaws.com/dev'
ROOT = Path(__file__).resolve().parents[1]


def guardar(path, data):
    with open(path, 'w', encoding='utf-8', opener=lambda p, flags: os.open(p, flags, 0o600)) as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


class Curl:
    def __init__(self, base):
        self.base = base
        self.checks = []

    def request(self, method, path, body=None, token=None, expected=(200,), pdf=None):
        # Config por stdin: tokens y contraseñas no aparecen en argumentos del proceso.
        options = {'url': self.base + path, 'request': method,
                   'header': 'Accept: application/pdf' if pdf else 'Accept: application/json'}
        config = [f'{key} = {json.dumps(value, ensure_ascii=False)}' for key, value in options.items()]
        if token:
            config.append('header = ' + json.dumps('Authorization: Bearer ' + token))
        if body is not None:
            config += ['header = "Content-Type: application/json"',
                       'data = ' + json.dumps(json.dumps(body, ensure_ascii=False), ensure_ascii=False)]
        result = subprocess.run(['curl', '--silent', '--show-error', '--connect-timeout', '5',
                                 '--max-time', '35', '--config', '-', '--write-out', '\n%{http_code}'],
                                input='\n'.join(config).encode(), capture_output=True)
        if result.returncode:
            raise RuntimeError(f'curl falló ({result.returncode}) en {method} {path}: '
                               + result.stderr.decode(errors='replace').strip())
        payload, status = result.stdout.rsplit(b'\n', 1)
        status = int(status)
        self.checks.append({'method': method, 'path': path, 'status': status,
                            'expected': list(expected), 'ok': status in expected})
        if status not in expected:
            raise RuntimeError(f'{method} {path}: HTTP {status}; esperado {expected}. '
                               'No se reintenta automáticamente una escritura.')
        print(f'HTTP {status}: {method} {path}', flush=True)
        if pdf:
            if not payload.startswith(b'%PDF'):
                raise RuntimeError('La boleta no contiene un PDF válido')
            pdf.write_bytes(payload)
            return {'pdf_bytes': len(payload)}
        return json.loads(payload) if payload else {}

    def esperar(self, label, action, ready, attempts=40):
        for index in range(attempts):
            value = action()
            if ready(value):
                return value
            if index < attempts - 1:
                time.sleep(3)
        raise RuntimeError(f'Tiempo agotado esperando {label}; revisar consumidores/colas de dev')


def comprobar_tenant(data, tenant):
    if isinstance(data, dict):
        if 'tenant_id' in data and data['tenant_id'] != tenant:
            raise RuntimeError('Respuesta contiene datos de otro tenant')
        for value in data.values():
            comprobar_tenant(value, tenant)
    elif isinstance(data, list):
        for value in data:
            comprobar_tenant(value, tenant)


def ciclo(api, account, directory, save_accounts):
    token = account['admin_token']
    tenant = account['tenant_id']
    label = account['alias']
    if not account.get('empleado_id'):
        vacante = api.request('POST', '/vacantes', {'titulo': 'Analista DEMO ' + label,
                             'area': 'Tecnología'}, token, (201,))
        postulacion = api.request('POST', '/postulaciones', {
            'vacante_id': vacante['vacante_id'], 'nombre': 'Persona Demo ' + label,
            'nombres': 'Persona', 'apellidos': 'Demo ' + label,
            'email': account['empleado_email'], 'documento': account['documento'],
            'area': 'Tecnología', 'cargo': 'Analista', 'salario_base': 3000,
            'fecha_ingreso': f'{date.today().year}-01-01'}, token, (201,))['postulacion']
        account['vacante_id'] = vacante['vacante_id']
        post_id = postulacion['postulacion_id']
        api.request('PATCH', f'/postulaciones/{post_id}/estado', {'estado': 'CONTRATADO'}, token)
        emp = 'emp-p' + post_id.split('-', 1)[1]
        account['empleado_id'] = emp
        save_accounts()
    emp = account['empleado_id']
    employee = api.esperar('empleado por SNS/SQS',
        lambda: api.request('GET', '/empleados/' + emp, token=token, expected=(200, 404)),
        lambda data: data.get('empleado_id') == emp)
    comprobar_tenant(employee, tenant)
    session = api.esperar('cuenta automática del empleado',
        lambda: api.request('POST', '/auth/login', {'email': account['empleado_email'],
                            'password': account['documento']}, expected=(200, 401)),
        lambda data: bool(data.get('token')))
    comprobar_tenant(session, tenant)
    account['empleado_token'] = session['token']
    api.request('POST', '/auth/cambiar-password', {'password_actual': account['documento'],
                'password_nueva': account['empleado_password']}, session['token'])
    session = api.request('POST', '/auth/login', {'email': account['empleado_email'],
                         'password': account['empleado_password']})
    account['empleado_token'] = session['token']
    save_accounts()
    empleado_token = session['token']
    today = date.today()
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    periodo = f'{year}-{month:02}'
    account['periodo'] = periodo
    ausencia = api.request('POST', '/ausencias', {'empleado_id': emp, 'tipo': 'SIN_GOCE',
                           'desde': periodo + '-20', 'hasta': periodo + '-21',
                           'motivo': 'Prueba ficticia DEMO'}, empleado_token, (201,))
    aus_id = ausencia['ausencia_id']
    account['ausencia_id'] = aus_id
    api.request('PATCH', '/ausencias/' + aus_id + '/estado',
                {'empleado_id': emp, 'estado': 'APROBADA'}, token)
    concepts_path = f'/nominas/conceptos?periodo={periodo}&empleado_id={emp}'
    api.esperar('descuento por ausencia', lambda: api.request('GET', concepts_path, token=token),
                lambda data: any(c.get('referencia') == 'AUSENCIA-' + aus_id for c in data.get('items', [])))
    for tipo, monto in [('BONO', 100), ('DESCUENTO', 50)]:
        api.request('POST', '/nominas/conceptos', {'empleado_id': emp, 'periodo': periodo,
                    'tipo': tipo, 'concepto': 'DEMO ' + tipo, 'monto': monto}, token, (201,))
    api.request('POST', '/nominas/generar', {'periodo': periodo}, token, (202,))
    planilla = api.esperar('planilla por SQS',
        lambda: api.request('GET', '/nominas/planillas/' + periodo, token=token),
        lambda data: data.get('estado') in ('GENERADA', 'ERROR'))
    if planilla['estado'] != 'GENERADA' or planilla.get('procesados') != 1:
        raise RuntimeError('Planilla no terminó correctamente con un empleado')
    nomina_id = f'nom-{periodo}-{emp}'
    nomina = api.request('GET', '/nominas/' + nomina_id, token=token)
    comprobar_tenant(nomina, tenant)
    if abs(float(nomina['neto']) - 2486) > 0.01:
        raise RuntimeError(f'Neto inesperado: {nomina["neto"]}; esperado 2486')
    api.request('GET', f'/nominas/{nomina_id}/boleta', token=empleado_token,
                pdf=directory / f'boleta-{label}.pdf')
    evaluacion = api.request('POST', '/evaluaciones', {'empleado_id': emp, 'periodo': periodo,
                            'comentarios': 'Evaluación ficticia DEMO'}, token, (201,))
    api.request('PUT', '/evaluaciones/' + evaluacion['evaluacion_id'],
                {'estado': 'COMPLETADA', 'puntaje': 4}, token)
    avisos = api.esperar('avisos de nómina y evaluación',
        lambda: api.request('GET', '/notificaciones?limit=200', token=empleado_token),
        lambda data: {'EmpleadoCreado', 'AusenciaAprobada', 'NominaGenerada', 'EvaluacionCompletada'} <=
                     {n.get('tipo') for n in data.get('items', [])})
    comprobar_tenant(avisos, tenant)
    account['nomina_id'] = nomina_id
    account['notificacion_id'] = next(n['notificacion_id'] for n in avisos['items']
                                     if n.get('tipo') == 'NominaGenerada')
    save_accounts()



def cargar_continuacion(directory):
    directory = directory.resolve()
    if not directory.is_relative_to((ROOT / 'hcm' / '.runtime').resolve()):
        raise ValueError('La continuación debe usar un directorio privado hcm/.runtime')
    data = json.loads((directory / 'cuentas.json').read_text())
    accounts = data['cuentas']
    if data['base_url'] != BASE or len(accounts) != 2:
        raise ValueError('Se requieren dos empresas de la misma API dev')
    if accounts[0]['tenant_id'] == accounts[1]['tenant_id']:
        raise ValueError('Los tenants deben ser distintos')
    # shortcut: retoma el fallo previo al login del empleado; otros puntos requieren revisar escrituras ya realizadas.
    if any(a.get('empleado_token') or a.get('periodo') for a in accounts):
        raise ValueError('La demo avanzó después de la contratación; revisar antes de repetir escrituras')
    for account in accounts:
        for field in ('admin_email', 'admin_password', 'empleado_email', 'empleado_password',
                      'documento', 'alias', 'tenant_id', 'admin_user_id'):
            if not account.get(field):
                raise ValueError('Cuenta incompleta: falta ' + field)
    return directory, accounts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--continuar", type=Path, help="Directorio de demo detenida esperando al empleado")
    args = parser.parse_args()
    api = Curl(BASE)
    api.request('GET', '/ping')  # Fallar antes de crear cuentas si no hay conectividad.
    if args.continuar:
        directory, accounts = cargar_continuacion(args.continuar)
        previous = directory / 'resultado.json'
        if previous.exists():
            guardar(directory / 'resultado-antes-continuar.json', json.loads(previous.read_text()))
    else:
        run_id = secrets.token_hex(6)
        directory = ROOT / 'hcm' / '.runtime' / ('demo-' + run_id)
        directory.mkdir(parents=True, mode=0o700)
        directory.chmod(0o700)
        accounts = []
    def save_accounts():
        guardar(directory / 'cuentas.json', {'base_url': BASE, 'cuentas': accounts})
    try:
        if args.continuar:
            for account in accounts:
                session = api.request('POST', '/auth/login', {
                    'email': account['admin_email'], 'password': account['admin_password']})
                if session['usuario']['tenant_id'] != account['tenant_id']:
                    raise RuntimeError('La sesión recuperada corresponde a otro tenant')
                account['admin_token'] = session['token']
            save_accounts()
        else:
            for alias in ('andina-demo', 'pacifico-demo'):
                account = {'alias': alias, 'empresa': alias + '-' + run_id,
                    'admin_email': f'admin.{alias}.{run_id}@example.invalid',
                    'admin_password': 'Demo!' + secrets.token_urlsafe(18) + '9a',
                    'empleado_email': f'persona.{alias}.{run_id}@example.invalid',
                    'empleado_password': 'Demo!' + secrets.token_urlsafe(18) + '9a',
                    'documento': str(10000000 + secrets.randbelow(90000000)),
                    'ruc': '20' + ''.join(str(secrets.randbelow(10)) for _ in range(9))}
                accounts.append(account)
                save_accounts()  # Conservar credenciales incluso si falla un paso posterior.
                api.request('POST', '/auth/register', {'empresa': account['empresa'], 'ruc': account['ruc'],
                    'nombre': 'Admin Demo', 'email': account['admin_email'],
                    'password': account['admin_password']}, expected=(201,))
                session = api.request('POST', '/auth/login', {'email': account['admin_email'],
                                     'password': account['admin_password']})
                account.update(admin_token=session['token'], tenant_id=session['usuario']['tenant_id'],
                               admin_user_id=session['usuario']['user_id'])
                save_accounts()
        if accounts[0]['tenant_id'] == accounts[1]['tenant_id']:
            raise RuntimeError('El registro no generó tenants distintos')
        for account in accounts:
            ciclo(api, account, directory, save_accounts)
        for owner, other in (accounts, accounts[::-1]):
            token = other['admin_token']
            api.request('GET', '/empleados/' + owner['empleado_id'], token=token, expected=(403, 404))
            api.request('GET', '/nominas/' + owner['nomina_id'], token=token, expected=(403, 404))
            api.request('GET', '/usuarios/' + owner['admin_user_id'], token=token, expected=(403, 404))
            api.request('GET', '/ausencias/' + owner['ausencia_id'] + '?empleado=' + owner['empleado_id'],
                        token=token, expected=(403, 404))
            for path in ('/evaluaciones?empleado=' + owner['empleado_id'],
                         '/vacantes/' + owner['vacante_id'] + '/postulaciones'):
                data = api.request('GET', path, token=token)
                if data != []:
                    raise RuntimeError('Consulta cruzada debería devolver un listado vacío')
            notice = '/notificaciones/' + quote(owner['notificacion_id'], safe='') + '/leida'
            api.request('PATCH', notice, {}, token, (403, 404))
            api.request('PATCH', notice, {}, owner['empleado_token'])
            # Intentar elegir tenant mediante query no debe cambiar el del JWT.
            data = api.request('GET', '/empleados?tenant_id=' + owner['tenant_id'], token=token)
            comprobar_tenant(data, other['tenant_id'])
            if owner['empleado_id'] in json.dumps(data):
                raise RuntimeError('Listado expuso el empleado de otro tenant')
        api.request('GET', '/notificaciones', expected=(401,))
        api.request('GET', '/usuarios/me', token=accounts[0]['admin_token'] + 'x', expected=(401,))
        guardar(directory / 'resultado.json', {'estado': 'APROBADO', 'base_url': BASE,
                'checks': api.checks, 'alcance': 'HTTP con curl; efectos EDA observados por endpoints. No inspecciona SNS/SQS/S3 directamente.'})
        print('DEMO APROBADA. Cuentas privadas y PDFs en:', directory)
    except Exception:
        guardar(directory / 'resultado.json', {'estado': 'FALLO', 'checks': api.checks})
        print('Ejecución incompleta. Cuentas parciales y evidencia en:', directory)
        raise


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error)) from None
