import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import MODULES, compose, validate


class UnifiedServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = compose()

    def test_todos_los_modulos_y_rutas_sin_duplicados(self):
        self.assertEqual(len(self.config['functions']), 68)
        for module in MODULES:
            self.assertTrue(any(k.startswith(module + '_') for k in self.config['functions']), module)
        validate(self.config)
        functions = self.config['functions']
        self.assertEqual(functions['usuarios_login']['handler'], 'src/handlers/auth.login')
        self.assertEqual(functions['notificaciones_procesarEventos']['runtime'], 'nodejs22.x')
        self.assertEqual(functions['nominas_procesarPlanilla']['timeout'], 900)
        self.assertTrue(any('stream' in e for e in functions['asistencia_publicarEventos']['events']))
        self.assertTrue(any('schedule' in e for e in functions['asistencia_calendario']['events']))

    def test_tablas_y_recursos_de_ambientes_no_colisionan(self):
        resources = self.config['resources']['Resources']
        names = []
        for r in resources.values():
            p = r['Properties']
            for key in ('TableName', 'QueueName', 'TopicName', 'BucketName', 'AlarmName'):
                if key in p:
                    self.assertIn('${sls:stage}', p[key])
                    names.append(p[key])
            if r['Type'] in ('AWS::DynamoDB::Table', 'AWS::S3::Bucket'):
                self.assertEqual(r['DeletionPolicy'], 'Retain')
        dev = {s.replace('${sls:stage}', 'dev') for s in names}
        prod = {s.replace('${sls:stage}', 'prod') for s in names}
        self.assertFalse(dev & prod)
        self.assertEqual(len(names), len(set(names)))

    def test_autorizacion_y_secretos_por_ambiente(self):
        for fn in self.config['functions'].values():
            for e in fn.get('events', []):
                if e.get('http', {}).get('authorizer'):
                    self.assertEqual(e['http']['authorizer']['name'], 'authorizer')
        self.assertEqual(self.config['functions']['usuarios_login']['environment']['JWT_SECRET'], '${env:HCM_JWT_SECRET_${sls:stage}}')
        self.assertEqual(self.config['functions']['nominas_generar']['environment']['TABLE_EMPLEADOS'], {'Ref': 'TablaEmpleados'})

    def test_monitor_apunta_a_funciones_y_colas_unificadas(self):
        fn = self.config['functions']['monitorizacion_comprobarCanales']
        names = json.loads(fn['environment']['CANALES'])
        self.assertEqual(len(names), 6)
        self.assertTrue(all(n.startswith('hcm-${sls:stage}-') for n in names))
        self.assertEqual(fn['environment']['METRICS_NAMESPACE'], 'HCM/Unificado/EDA')
        self.assertEqual(fn['environment']['EMAIL_TOPIC_ARN'], {'Ref': 'EmailTopic'})
        resources = self.config['resources']['Resources']
        for resource in resources.values():
            if resource['Type'] == 'AWS::CloudWatch::Alarm':
                for dimension in resource['Properties']['Dimensions']:
                    if dimension['Name'] in ('QueueName', 'TopicName', 'FunctionName'):
                        self.assertTrue(dimension['Value'].startswith('hcm-${sls:stage}-'), dimension)

    def test_artefactos_separados_evitan_colision_de_imports(self):
        self.assertEqual(len({f['package']['artifact'] for f in self.config['functions'].values()}), len(MODULES))
        self.assertEqual(self.config['functions']['usuarios_login']['package']['artifact'], '.build/usuarios.zip')
        self.assertEqual(self.config['functions']['empleados_crearEmpleado']['package']['artifact'], '.build/empleados.zip')

    def test_duplicar_una_ruta_falla_antes_de_desplegar(self):
        config = copy.deepcopy(self.config)
        config['functions']['otra'] = copy.deepcopy(config['functions']['usuarios_login'])
        with self.assertRaisesRegex(ValueError, 'Ruta duplicada'):
            validate(config)
