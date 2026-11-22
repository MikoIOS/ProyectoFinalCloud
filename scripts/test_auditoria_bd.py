import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditoria_bd import auditar_tabla, generar_reporte_markdown, tablas_por_stage


class AuditoriaTests(unittest.TestCase):
    def test_entornos_no_comparten_tablas(self):
        dev, prod = tablas_por_stage('dev'), tablas_por_stage('prod')
        self.assertEqual(len(dev), 7)
        self.assertFalse(set(dev.values()) & set(prod.values()))
        self.assertEqual(dev['ms-nominas'], 'hcm-dev-nominas')
        self.assertEqual(prod['ms-nominas'], 'hcm-nominas-dev')
        with self.assertRaises(ValueError):
            tablas_por_stage('qa')

    def test_paginacion_y_tres_tenants(self):
        tabla = Mock(name='tabla'); tabla.name = 'prueba'
        tabla.scan.side_effect = [
            {'Items': [{'tenant_id': 'andina'}] * 10000, 'LastEvaluatedKey': {'tenant_id': 'andina', 'sk': 'ultimo'}},
            {'Items': [{'tenant_id': t} for t in ('pacifico', 'sierra') for _ in range(10000)]},
        ]
        resultado = auditar_tabla(tabla, 'ms-prueba')
        self.assertEqual(resultado['total'], 30000)
        self.assertTrue(resultado['cumple_rubrica'])
        self.assertEqual(tabla.scan.call_args.kwargs['ExclusiveStartKey']['sk'], 'ultimo')
        self.assertTrue(tabla.scan.call_args.kwargs['ConsistentRead'])

    def test_total_sin_distribucion_no_cumple(self):
        for tenants in (['andina'] * 30000, ['andina', 'pacifico', 'sierra'] + ['otro'] * 30000):
            tabla = Mock(); tabla.name = 'prueba'
            tabla.scan.return_value = {'Items': [{'tenant_id': t} for t in tenants]}
            self.assertFalse(auditar_tabla(tabla, 'ms-prueba')['cumple_rubrica'])

    def test_error_no_se_presenta_como_tabla_inexistente(self):
        from botocore.exceptions import ClientError
        tabla = Mock(); tabla.name = 'prueba'
        tabla.scan.side_effect = ClientError({'Error': {'Code': 'AccessDeniedException'}}, 'Scan')
        resultado = auditar_tabla(tabla, 'ms-prueba')
        self.assertEqual(resultado['error'], 'AccessDeniedException')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'reporte.md'
            generar_reporte_markdown([resultado], output, 'dev')
            texto = output.read_text()
            self.assertIn('Error (AccessDeniedException)', texto)
            self.assertIn('VOLUMEN NO ACREDITADO', texto)
            self.assertIn('`dev`', texto)

    def test_error_conectividad_no_acredita_volumen(self):
        from botocore.exceptions import EndpointConnectionError
        tabla = Mock(); tabla.name = 'prueba'
        tabla.scan.side_effect = EndpointConnectionError(endpoint_url='https://dynamodb.us-east-1.amazonaws.com')
        resultado = auditar_tabla(tabla, 'ms-prueba')
        self.assertEqual(resultado['error'], 'EndpointConnectionError')
        self.assertFalse(resultado['cumple_rubrica'])

    def test_documentacion_claves_e_indices_reales(self):
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / 'hcm'))
        from build import CloudFormationLoader
        import yaml
        texto = (root / 'docs/arquitectura-y-diseno.md').read_text()
        for modulo in ('usuarios', 'empleados', 'nominas', 'asistencia', 'reclutamiento', 'desempeno', 'notificaciones'):
            with self.subTest(modulo=modulo):
                seccion = texto.split(f'`ms-{modulo}` (PK', 1)[1].split('\n### ', 1)[0].split('\n---', 1)[0]
                config = yaml.load((root / f'ms-{modulo}/serverless.yml').read_text(), Loader=CloudFormationLoader)
                tabla = next(r['Properties'] for r in config['resources']['Resources'].values() if r['Type'] == 'AWS::DynamoDB::Table')
                for bloque in re.findall(r'```json\n(.*?)\n```', seccion, re.S):
                    item = json.loads(bloque)
                    for clave in tabla['KeySchema']:
                        self.assertIsInstance(item[clave['AttributeName']], str)
                for indice in tabla.get('GlobalSecondaryIndexes', []):
                    claves = {k['KeyType']: k['AttributeName'] for k in indice['KeySchema']}
                    fila = f'| `{indice["IndexName"]}` | `{claves["HASH"]}` | '
                    fila += '`' + claves['RANGE'] + '`' if 'RANGE' in claves else '—'
                    self.assertIn(fila + ' |', seccion)


if __name__ == '__main__':
    unittest.main()
