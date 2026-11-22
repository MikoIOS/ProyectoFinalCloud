import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from demo_dos_tenants import Curl, comprobar_tenant, guardar, ciclo, cargar_continuacion, BASE


class DemoTests(unittest.TestCase):
    @patch('demo_dos_tenants.subprocess.run')
    def test_curl_no_expone_secretos_en_argumentos(self, run):
        run.return_value = Mock(returncode=0, stdout=b'{"token":"response"}\n201')
        client = Curl('https://test.invalid/dev')
        data = client.request('POST', '/auth/register', {'password': 'secret"\\value'},
                              'token-secret', (201,))
        self.assertEqual(data['token'], 'response')
        args, kwargs = run.call_args
        self.assertNotIn('token-secret', str(args))
        config = kwargs['input'].decode()
        self.assertIn('Authorization: Bearer token-secret', config)
        data_line = next(line for line in config.splitlines() if line.startswith('data = '))
        self.assertEqual(json.loads(json.loads(data_line.split(' = ', 1)[1]))['password'], 'secret"\\value')
        self.assertTrue(client.checks[0]['ok'])

    @patch('demo_dos_tenants.subprocess.run')
    def test_fallo_no_reintenta_escritura(self, run):
        run.return_value = Mock(returncode=6, stderr=b'Could not resolve host')
        with self.assertRaisesRegex(RuntimeError, 'curl falló'):
            Curl('https://test.invalid').request('POST', '/vacantes', {})
        self.assertEqual(run.call_count, 1)

    @patch('demo_dos_tenants.subprocess.run')
    def test_acceso_cruzado_200_falla(self, run):
        run.return_value = Mock(returncode=0, stdout=b'{}\n200')
        client = Curl('https://test.invalid')
        with self.assertRaisesRegex(RuntimeError, 'HTTP 200'):
            client.request('GET', '/empleados/otro', expected=(403, 404))
        self.assertFalse(client.checks[0]['ok'])

    @patch('demo_dos_tenants.subprocess.run')
    def test_pdf_invalido_se_rechaza(self, run):
        run.return_value = Mock(returncode=0, stdout=b'{"error":"no pdf"}\n200')
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'boleta.pdf'
            with self.assertRaisesRegex(RuntimeError, 'PDF válido'):
                Curl('https://test.invalid').request('GET', '/boleta', pdf=output)
            self.assertFalse(output.exists())

    def test_tenant_en_listados_anidados(self):
        comprobar_tenant({'items': [{'tenant_id': 'andina'}]}, 'andina')
        with self.assertRaisesRegex(RuntimeError, 'otro tenant'):
            comprobar_tenant({'items': [{'tenant_id': 'pacifico'}]}, 'andina')

    def test_credenciales_archivo_privado(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'cuentas.json'
            guardar(output, {'password': 'test'})
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    def test_continuacion_reutiliza_empleado_sin_recontratar(self):
        api = Mock()
        api.esperar.side_effect = RuntimeError('parada antes del login')
        account = {'admin_token': 'test', 'tenant_id': 't1', 'alias': 'demo', 'empleado_id': 'emp-p123'}
        with self.assertRaisesRegex(RuntimeError, 'parada'):
            ciclo(api, account, Path('/tmp'), Mock())
        api.request.assert_not_called()
        self.assertEqual(api.esperar.call_args.args[0], 'empleado por SNS/SQS')

    def test_continuacion_rechaza_escrituras_ya_avanzadas(self):
        with tempfile.TemporaryDirectory() as tmp, patch('demo_dos_tenants.ROOT', Path(tmp)):
            directory = Path(tmp) / 'hcm' / '.runtime' / 'demo-test'
            directory.mkdir(parents=True)
            accounts = [{'tenant_id': 't1', 'empleado_token': 'test'}, {'tenant_id': 't2'}]
            guardar(directory / 'cuentas.json', {'base_url': BASE, 'cuentas': accounts})
            with self.assertRaisesRegex(ValueError, 'avanzó'):
                cargar_continuacion(directory)

    @patch('demo_dos_tenants.time.sleep')
    def test_evento_que_no_llega_no_se_aprueba(self, sleep):
        action = Mock(return_value={})
        with self.assertRaisesRegex(RuntimeError, 'Tiempo agotado'):
            Curl('https://test.invalid').esperar('SNS', action, lambda d: 'id' in d, attempts=2)
        self.assertEqual(action.call_count, 2)
        sleep.assert_called_once_with(3)


if __name__ == '__main__':
    unittest.main()
