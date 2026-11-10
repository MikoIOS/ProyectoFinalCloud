import unittest
from unittest.mock import Mock, patch

from probar_alarmas import esperar, probar


class PruebaAlarmasTest(unittest.TestCase):
    @patch('probar_alarmas.time.sleep')
    def test_metrica_alarma_y_recuperacion(self, sleep):
        cw = Mock()
        cw.describe_alarms.side_effect = [{'MetricAlarms': [{'StateValue': estado,
            'ActionsEnabled': True, 'AlarmActions': ['arn:aws:sns:us-east-1:123:hcm-alarmas-dev']}]} for estado in ('OK', 'ALARM', 'OK')]
        resultado = probar(cw, 'dev')
        self.assertEqual(resultado['estados_verificados'], ['OK', 'ALARM', 'OK'])
        self.assertEqual([c.kwargs['MetricData'][0]['Value'] for c in cw.put_metric_data.call_args_list], [1, 0])
        sleep.assert_not_called()

    def test_no_deja_la_prueba_activa_si_las_acciones_estan_deshabilitadas(self):
        cw = Mock()
        cw.describe_alarms.side_effect = [{'MetricAlarms': [{'StateValue': 'OK'}]},
                                         {'MetricAlarms': [{'StateValue': 'ALARM', 'ActionsEnabled': False}]}]
        with self.assertRaisesRegex(RuntimeError, 'deshabilitadas'):
            probar(cw, 'dev')
        self.assertEqual(cw.put_metric_data.call_args_list[-1].kwargs['MetricData'][0]['Value'], 0)

    def test_alarma_inexistente(self):
        cw = Mock()
        cw.describe_alarms.return_value = {'MetricAlarms': []}
        with self.assertRaisesRegex(RuntimeError, 'No existe'):
            esperar(cw, 'alarma-inexistente', 'OK')

    @patch('probar_alarmas.time.monotonic', side_effect=[0, 1])
    def test_timeout(self, clock):
        with self.assertRaisesRegex(RuntimeError, 'dentro'):
            esperar(Mock(), 'prueba', 'ALARM', timeout=1)
