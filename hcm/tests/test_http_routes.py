import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

HCM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HCM))
from build import MODULES, compose, group_http_functions


class HttpRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = compose(group_http=False)
        cls.config = compose()

    def test_conserva_las_58_rutas_autorizadores_y_workers(self):
        def routes(config):
            return {(e['http']['method'].upper(), e['http']['path']): e['http']
                    for fn in config['functions'].values() for e in fn.get('events', []) if 'http' in e}
        self.assertEqual(len(routes(self.config)), 58)
        self.assertEqual(routes(self.config), routes(self.original))
        remaining = {key: fn for key, fn in self.original['functions'].items()
                     if not any('http' in e for e in fn.get('events', []))}
        self.assertEqual(len(remaining), 10)
        for key, fn in remaining.items():
            self.assertEqual(self.config['functions'][key], fn, key)
        for module, manifest in self.config['custom']['httpRoutes'].items():
            events = self.config['functions'][module + '_http']['events']
            self.assertEqual(len(events), len(manifest))
            for key, fn in self.original['functions'].items():
                if key.startswith(module + '_'):
                    for event in fn.get('events', []):
                        if 'http' in event:
                            http = event['http']
                            entry = manifest[http['method'].upper() + ' ' + http['path'].strip('/')]
                            self.assertEqual(entry, {'handler': fn['handler'], 'protected': bool(http.get('authorizer'))})
                            self.assertGreaterEqual(self.config['functions'][module + '_http']['timeout'], fn['timeout'])

    def test_cada_ruta_python_conserva_evento_respuesta_y_contexto(self):
        count = 0
        for module, routes in self.config['custom']['httpRoutes'].items():
            if module == 'notificaciones':
                continue
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'hcm_routes.json').write_text(json.dumps(routes))
                (root / 'hcm_http.py').write_bytes((HCM / 'http_router.py').read_bytes())
                spec = importlib.util.spec_from_file_location('router_' + module, root / 'hcm_http.py')
                router = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(router)
                for key, route in routes.items():
                    with self.subTest(module=module, route=key):
                        count += 1
                        method, resource = key.split(' ', 1)
                        event = {'httpMethod': method, 'resource': '/' + resource,
                                 'path': '/ruta-con-valores-concretos',
                                 'pathParameters': {'id': 'emp-1', 'nomina_id': 'nom-1', 'periodo': '2026-11'},
                                 'queryStringParameters': {'next_token': 'cursor', 'formato': 'json'},
                                 'body': '{"tenant_id":"pacifico"}', 'isBase64Encoded': False,
                                 'requestContext': {'authorizer': {'tenant_id': 'andina', 'user_id': 'usr-1', 'rol': 'empleado'}}}
                        original_event = copy.deepcopy(event)
                        context = object()
                        response = {'statusCode': 200, 'headers': {'Content-Type': 'application/pdf'},
                                    'isBase64Encoded': True, 'body': 'JVBERi0='}
                        callback = Mock(return_value=response)
                        target = Mock(**{route['handler'].rsplit('.', 1)[1]: callback})
                        with patch.object(router.importlib, 'import_module', return_value=target) as load:
                            self.assertIs(router.handler(event, context), response)
                            callback.assert_called_once_with(event, context)
                            self.assertIs(callback.call_args.args[0], event)
                            load.assert_called_once_with(route['handler'].rsplit('.', 1)[0].replace('/', '.'))
                            self.assertEqual(event, original_event)
                            if route['protected']:
                                for auth in ({}, {'tenant_id': 'andina'}, {'tenant_id': 'andina', 'user_id': 'usr-1', 'rol': ''}):
                                    load.reset_mock()
                                    unauthenticated = dict(event, requestContext={'authorizer': auth})
                                    self.assertEqual(router.handler(unauthenticated)['statusCode'], 401)
                                    load.assert_not_called()
                            else:
                                self.assertIs(router.handler(dict(event, requestContext={})), response)
                            callback.side_effect = RuntimeError('fallo original')
                            with self.assertRaisesRegex(RuntimeError, 'fallo original'):
                                router.handler(event, context)
                        self.assertEqual(router.handler({'httpMethod': method, 'resource': '/desconocida'})['statusCode'], 404)
                        self.assertEqual(router.handler({})['statusCode'], 404)
        self.assertEqual(count, 55)

    def test_tres_rutas_node_y_errores(self):
        routes = self.config['custom']['httpRoutes']['notificaciones']
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'hcm_routes.json').write_text(json.dumps(routes))
            (directory / 'hcm_http.js').write_bytes((HCM / 'http_router.js').read_bytes())
            result = subprocess.run(['node', str(HCM / 'tests/router_node.cjs'), str(directory)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_no_agrupa_workers_ni_configuraciones_incompatibles(self):
        original = copy.deepcopy(self.original['functions'])
        original['usuarios_login']['events'].append({'sqs': {'arn': 'arn:cola'}})
        with self.assertRaises(ValueError):
            group_http_functions(original)
        original = copy.deepcopy(self.original['functions'])
        original['usuarios_login']['environment']['EXTRA'] = 'otro'
        with self.assertRaises(ValueError):
            group_http_functions(original)

    def test_artefactos_incluyen_los_siete_routers_y_sus_handlers(self):
        for module in MODULES[:-1]:
            with self.subTest(module=module), zipfile.ZipFile(HCM / '.build' / (module + '.zip')) as artifact:
                self.assertEqual(json.loads(artifact.read('hcm_routes.json')), self.config['custom']['httpRoutes'][module])
                for route in self.config['custom']['httpRoutes'][module].values():
                    extension = '.js' if module == 'notificaciones' else '.py'
                    self.assertIn(route['handler'].rsplit('.', 1)[0] + extension, artifact.namelist())

    def test_siete_lambdas_http_con_handlers_reales_y_aws_simulado(self):
        for module in MODULES[:-1]:
            with self.subTest(module=module), tempfile.TemporaryDirectory() as tmp:
                artifact = HCM / '.build' / (module + '.zip')
                with zipfile.ZipFile(artifact) as archive:
                    archive.extractall(tmp)
                if module == 'notificaciones':
                    result = subprocess.run(['node', str(HCM / 'tests/runtime_node.cjs'), tmp],
                                            text=True, capture_output=True, timeout=30)
                else:
                    result = subprocess.run([sys.executable, str(HCM / 'tests/runtime_python.py'), tmp, module],
                                            text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_authorizer_workers_calendario_y_monitores_reales(self):
        checked = 1  # El consumidor Node se ejecuta junto a sus tres rutas HTTP en runtime_node.cjs.
        for key, fn in self.config['functions'].items():
            if key.endswith('_http') or key.startswith('notificaciones_'):
                continue
            module = 'usuarios' if key == 'authorizer' else key.split('_', 1)[0]
            with self.subTest(function=key), tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(HCM / '.build' / (module + '.zip')) as archive:
                    archive.extractall(tmp)
                result = subprocess.run([sys.executable, str(HCM / 'tests/runtime_python.py'), tmp, module, fn['handler']],
                                        text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                checked += 1
        self.assertEqual(checked, 10)
