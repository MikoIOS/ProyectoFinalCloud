"""Verifica los templates reales generados por Serverless, sin llamar a AWS."""
import json
import unittest
from pathlib import Path

BUILD = Path(__file__).resolve().parents[1] / '.build'


def references(value):
    if isinstance(value, list):
        return set().union(*(references(v) for v in value))
    if not isinstance(value, dict):
        return set()
    refs = set()
    if 'Ref' in value and not value['Ref'].startswith('AWS::'):
        refs.add(value['Ref'])
    if 'Fn::GetAtt' in value:
        v = value['Fn::GetAtt']
        refs.add(v[0] if isinstance(v, list) else v.split('.')[0])
    depends = value.get('DependsOn', [])
    refs.update([depends] if isinstance(depends, str) else depends)
    for v in value.values():
        refs.update(references(v))
    return refs


@unittest.skipUnless((BUILD / 'check-dev/cloudformation-template-update-stack.json').exists() and
                     (BUILD / 'check-prod/cloudformation-template-update-stack.json').exists(),
                     'Primero empaquetar dev y prod como indica hcm/README.md')
class PackagedTemplatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.templates = {stage: json.loads((BUILD / ('check-' + stage) / 'cloudformation-template-update-stack.json').read_text())
                         for stage in ('dev', 'prod')}

    def test_api_unica_68_lambdas_y_stage_correcto(self):
        for stage, template in self.templates.items():
            resources = list(template['Resources'].values())
            with self.subTest(stage=stage):
                for kind, count in [('AWS::ApiGateway::RestApi', 1), ('AWS::Lambda::Function', 68), ('AWS::DynamoDB::Table', 7)]:
                    self.assertEqual(sum(r['Type'] == kind for r in resources), count)
                self.assertLessEqual(len(resources), 500)
                self.assertEqual([r['Properties']['StageName'] for r in resources if r['Type'] == 'AWS::ApiGateway::Deployment'], [stage])

    def test_referencias_existentes_y_sin_ciclos(self):
        for stage, template in self.templates.items():
            resources = template['Resources']
            graph = {key: references(value) for key, value in resources.items()}
            self.assertFalse(references(template) - resources.keys(), stage)
            visited = set()
            def visit(key, path):
                self.assertNotIn(key, path, (stage, path, key))
                if key in visited:
                    return
                for dep in graph[key]:
                    visit(dep, path | {key})
                visited.add(key)
            for key in graph:
                visit(key, set())

    def test_recursos_y_secretos_separados(self):
        names = {}
        secrets = {}
        for stage, template in self.templates.items():
            names[stage] = set()
            for r in template['Resources'].values():
                p = r.get('Properties', {})
                for key in ('TableName', 'QueueName', 'BucketName', 'TopicName', 'FunctionName', 'AlarmName'):
                    if isinstance(p.get(key), str):
                        names[stage].add(p[key])
                if r['Type'] == 'AWS::Lambda::Function' and 'JWT_SECRET' in p.get('Environment', {}).get('Variables', {}):
                    secrets[stage] = p['Environment']['Variables']['JWT_SECRET']
        self.assertFalse(names['dev'] & names['prod'])
        self.assertNotEqual(secrets['dev'], secrets['prod'])

    def test_filtros_esperan_a_sus_grupos_de_logs(self):
        for template in self.templates.values():
            resources = template['Resources']
            for r in resources.values():
                if r['Type'] == 'AWS::Logs::MetricFilter':
                    ref = r['Properties']['LogGroupName']['Ref']
                    self.assertEqual(resources[ref]['Type'], 'AWS::Logs::LogGroup')
