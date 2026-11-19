import json
import unittest
from build import compose, configure_stage
from reuse import apply_existing


class ExistingResourcesTest(unittest.TestCase):
    def setUp(self):
        self.base=compose(); self.manifest={'resources':{}}
        for key,r in self.base['resources']['Resources'].items():
            if r['Type'] not in ('AWS::DynamoDB::Table','AWS::S3::Bucket','AWS::SQS::Queue','AWS::SNS::Topic') or key=='TopicAlarmas':continue
            self.manifest['resources'][key]={'Ref':'original-'+key,'Arn':'arn:aws:test::123:'+key,'StreamArn':'arn:aws:dynamodb:test:stream/'+key}

    def test_reutiliza_tablas_sin_declarar_ni_copiar_bases(self):
        config=apply_existing(self.base,self.manifest,background=False)
        resources=config['resources']['Resources']
        self.assertFalse(any(r['Type']=='AWS::DynamoDB::Table' for r in resources.values()))
        self.assertFalse(any(k in resources for k in self.manifest['resources']))
        self.assertEqual(config['functions']['usuarios_http']['environment']['TABLE_USUARIOS'],'original-TablaUsuarios')
        self.assertEqual(config['functions']['nominas_http']['environment']['TABLE_NAME'],'original-NominaTable')
        self.assertEqual(len(config['functions']),17)

    def test_dev_tiene_siete_tablas_y_recursos_propios(self):
        dev = configure_stage(self.base, 'dev')
        prod = configure_stage(self.base, 'prod', self.manifest)
        tables = [r for r in dev['resources']['Resources'].values() if r['Type'] == 'AWS::DynamoDB::Table']
        self.assertEqual(len(tables), 7)
        for table in tables:
            self.assertTrue(table['Properties']['TableName'].startswith('hcm-${sls:stage}-'))
            self.assertTrue(table['Properties']['PointInTimeRecoverySpecification']['PointInTimeRecoveryEnabled'])
            self.assertEqual(table['DeletionPolicy'], 'Retain')
        self.assertEqual(dev['functions']['usuarios_http']['environment']['TABLE_USUARIOS'], {'Ref': 'TablaUsuarios'})
        self.assertNotEqual(dev['functions']['usuarios_http']['environment']['TABLE_USUARIOS'],
                            prod['functions']['usuarios_http']['environment']['TABLE_USUARIOS'])
        for key in ('asistencia_publicarEventos', 'nominas_procesarPlanilla'):
            self.assertNotEqual(dev['functions'][key]['events'], prod['functions'][key]['events'])

    def test_prod_no_permite_crear_bases_por_falta_de_manifiesto(self):
        with self.assertRaises(ValueError):
            configure_stage(self.base, 'prod')

    def test_conserva_arn_stream_y_sqs_originales(self):
        config=apply_existing(self.base,self.manifest)
        self.assertEqual(config['functions']['asistencia_publicarEventos']['events'][0]['stream']['arn'],'arn:aws:dynamodb:test:stream/AsistenciaTable')
        self.assertEqual(config['functions']['nominas_procesarPlanilla']['events'][0]['sqs']['arn'],'arn:aws:test::123:ColaTrabajos')
        self.assertEqual(config['functions']['asistencia_publicarEventos']['events'][0]['stream']['startingPosition'],'TRIM_HORIZON')

    def test_dev_no_duplica_consumidores_sobre_datos_compartidos(self):
        config=apply_existing(self.base,self.manifest,background=False)
        for fn in config['functions'].values():self.assertTrue(all('http' in e for e in fn.get('events',[])))
        self.assertNotIn('EmailTopicPolicy',config['resources']['Resources'])
        self.assertFalse(any(r['Type']=='AWS::CloudWatch::Alarm' for r in config['resources']['Resources'].values()))

    def test_bootstrap_cerrado_sin_background(self):
        config=apply_existing(compose(bootstrap=True),self.manifest,bootstrap=True)
        self.assertEqual(config['provider']['apiGateway']['resourcePolicy'][0]['Effect'],'Deny')
        for fn in config['functions'].values():self.assertTrue(all('http' in e for e in fn.get('events',[])))


    def test_nombres_de_lambdas_no_se_reemplazan_por_nombres_de_tablas(self):
        config=apply_existing(self.base,self.manifest)
        names=json.loads(config['functions']['monitorizacion_comprobarCanales']['environment']['CANALES'])
        self.assertTrue(all(name.startswith('hcm-${sls:stage}-') for name in names))
        for resource in config['resources']['Resources'].values():
            if resource['Type']=='AWS::CloudWatch::Alarm':
                for dimension in resource['Properties']['Dimensions']:
                    if dimension['Name']=='FunctionName':
                        self.assertTrue(dimension['Value'].startswith('hcm-${sls:stage}-'), dimension)
