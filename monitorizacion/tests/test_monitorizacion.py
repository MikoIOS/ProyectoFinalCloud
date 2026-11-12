import json
import os
import unittest
from unittest.mock import Mock, patch

import avisos
import canales


class AvisosTest(unittest.TestCase):
    def evento(self, estado='ALARM', anterior='OK'):
        alarma = {'AlarmName': 'hcm-dev-eda-notificaciones-dlq', 'NewStateValue': estado,
                  'OldStateValue': anterior, 'AlarmDescription': 'Hay mensajes en la cola de fallos.',
                  'StateChangeTime': '2026-11-09T23:00:00Z', 'NewStateReason': 'Threshold Crossed'}
        return {'Records': [{'Sns': {'Message': json.dumps(alarma)}}]}

    @patch.dict(os.environ, {'EMAIL_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:email', 'AWS_REGION': 'us-east-1'})
    @patch('avisos.boto3.client')
    def test_alerta_y_recuperacion_legibles(self, client):
        for estado, anterior, etiqueta in [('ALARM', 'OK', 'ALERTA'), ('OK', 'ALARM', 'RECUPERADO')]:
            with self.subTest(estado=estado):
                self.assertEqual(avisos.handler(self.evento(estado, anterior)), {'avisos': 1})
                correo = client.return_value.publish.call_args.kwargs
                self.assertIn(etiqueta, correo['Subject'])
                self.assertIn('Hay mensajes en la cola de fallos.', correo['Message'])
                self.assertIn('cloudwatch/home', correo['Message'])
                with self.assertRaises(ValueError):
                    json.loads(correo['Message'])
                self.assertLessEqual(len(correo['Subject']), 99)

    @patch('avisos.boto3.client')
    def test_no_envia_ok_inicial(self, client):
        self.assertEqual(avisos.handler(self.evento('OK', 'INSUFFICIENT_DATA')), {'avisos': 0})
        client.return_value.publish.assert_not_called()

    @patch.dict(os.environ, {'EMAIL_TOPIC_ARN': 'topic'})
    @patch('avisos.boto3.client')
    def test_fallo_sns_no_se_oculta(self, client):
        client.return_value.publish.side_effect = RuntimeError('SNS no disponible')
        with self.assertRaisesRegex(RuntimeError, 'SNS no disponible'):
            avisos.handler(self.evento())


class CanalesTest(unittest.TestCase):
    @patch.dict(os.environ, {'CANALES': '["consumidor", "publicador"]', 'STAGE': 'dev'})
    def comprobar(self, paginas):
        lambdas, cloudwatch = Mock(), Mock()
        lambdas.get_paginator.return_value.paginate.side_effect = paginas
        with patch('canales.boto3.client', side_effect=[lambdas, cloudwatch]):
            resultado = canales.handler({})
        return resultado, cloudwatch.put_metric_data.call_args.kwargs['MetricData'][0]

    def test_conexiones_habilitadas(self):
        pagina = [{'EventSourceMappings': [{'State': 'Enabled'}]}]
        resultado, metrica = self.comprobar([pagina, pagina])
        self.assertEqual(resultado['canales_no_habilitados'], [])
        self.assertEqual(metrica['Value'], 0)
        self.assertEqual(metrica['MetricName'], 'CanalesDeshabilitados-dev')

    def test_detecta_deshabilitados_y_conexiones_inexistentes(self):
        resultado, metrica = self.comprobar([
            [{'EventSourceMappings': [{'State': 'Disabled'}]}], [{'EventSourceMappings': []}]])
        self.assertEqual(resultado['canales_no_habilitados'], ['consumidor', 'publicador'])
        self.assertEqual(metrica['Value'], 2)

    @patch.dict(os.environ, {'CANALES': '["consumidor"]', 'STAGE': 'dev'})
    @patch('canales.boto3.client')
    def test_error_de_permisos_no_se_reporta_como_saludable(self, client):
        client.return_value.get_paginator.return_value.paginate.side_effect = RuntimeError('AccessDenied')
        with self.assertRaisesRegex(RuntimeError, 'AccessDenied'):
            canales.handler({})
        client.return_value.put_metric_data.assert_not_called()


if __name__ == '__main__':
    unittest.main()
