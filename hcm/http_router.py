"""Despacha las rutas REST del módulo sin alterar el evento ni la respuesta del handler."""
import importlib
import json
from pathlib import Path

ROUTES = json.loads(Path(__file__).with_name('hcm_routes.json').read_text())


def error(status, code, message):
    return {'statusCode': status, 'headers': {
        'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*',
    }, 'body': json.dumps({'error': {'codigo': code, 'mensaje': message}})}


def handler(event, context=None):
    method, resource = event.get('httpMethod'), event.get('resource')
    route = ROUTES.get(method.upper() + ' ' + resource.strip('/')) if isinstance(method, str) and isinstance(resource, str) else None
    if route is None:
        return error(404, 'NO_ENCONTRADO', 'Ruta no encontrada')
    if route['protected']:
        auth = (event.get('requestContext') or {}).get('authorizer') or {}
        if not all(isinstance(auth.get(key), str) and auth[key].strip() for key in ('tenant_id', 'user_id', 'rol')):
            return error(401, 'NO_AUTENTICADO', 'Sin contexto de autenticación')
    module, name = route['handler'].rsplit('.', 1)
    return getattr(importlib.import_module(module.replace('/', '.')), name)(event, context)
