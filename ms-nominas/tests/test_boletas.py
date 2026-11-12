import base64
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.auth import Ctx
from src.common.errors import NoEncontrado, Prohibido
from src.handlers import nominas
from src.repositories import boletas_s3
from src.services import planillas


class BoletasTest(unittest.TestCase):
    def setUp(self):
        self.ctx = Ctx('andina', 'empleado', 'usr-000002', 'emp-000002')
        self.item = {'tenant_id': 'andina', 'nomina_id': 'nom-2026-11-emp-000002',
                     'periodo': '2026-11', 'empleado_id': 'emp-000002', 'nombre_empleado': 'Empleado Demo',
                     'sueldo_base': 3500, 'bonos': 0, 'descuentos': 455, 'neto': 3045}

    @patch.object(planillas.repo, 'get_nomina')
    @patch.object(boletas_s3.boto3, 'client')
    @patch.dict(os.environ, {'BOLETAS_BUCKET': 'boletas-privadas'})
    def test_pdf_y_json_archivan_los_mismos_bytes_sin_aceptar_claves_del_cliente(self, client, get):
        get.return_value = self.item
        contenido, nombre = planillas.boleta(self.ctx, self.item['nomina_id'], {})
        self.assertTrue(contenido.startswith(b'%PDF-1.4'))
        result = planillas.boleta(self.ctx, self.item['nomina_id'], {
            'formato': 'json', 'tenant_id': 'pacifico', 'key': 'pacifico/archivo.pdf', 'bucket': 'otro',
        })
        self.assertEqual(base64.b64decode(result['contenido_base64']), contenido)
        self.assertEqual(result['nombre_archivo'], nombre)
        almacenado = client.return_value.put_object.call_args.kwargs
        self.assertEqual(almacenado['Body'], contenido)
        self.assertEqual(almacenado['Bucket'], 'boletas-privadas')
        self.assertEqual(almacenado['Key'], 'andina/boletas/2026-11/nom-2026-11-emp-000002.pdf')
        self.assertEqual(almacenado['ServerSideEncryption'], 'AES256')
        self.assertNotIn('ACL', almacenado)

    @patch.object(planillas.repo, 'get_nomina')
    @patch.object(boletas_s3, 'guardar')
    def test_no_escribe_ni_entrega_boleta_ajena(self, guardar, get):
        get.return_value = {**self.item, 'empleado_id': 'emp-000003'}
        with self.assertRaises(Prohibido):
            planillas.boleta(self.ctx, self.item['nomina_id'], {})
        guardar.assert_not_called()

    @patch.object(planillas.repo, 'get_nomina', return_value=None)
    @patch.object(boletas_s3, 'guardar')
    def test_consulta_otro_tenant_no_alcanza_s3(self, guardar, get):
        ctx = Ctx('pacifico', 'admin_rrhh', 'usr-000001', 'emp-000001')
        with self.assertRaises(NoEncontrado):
            planillas.boleta(ctx, self.item['nomina_id'], {})
        get.assert_called_once_with('pacifico', self.item['nomina_id'])
        guardar.assert_not_called()

    @patch.object(boletas_s3, 'guardar')
    def test_sin_contexto_no_alcanza_s3(self, guardar):
        result = nominas.boleta({'pathParameters': {'nomina_id': self.item['nomina_id']}})
        self.assertEqual(result['statusCode'], 401)
        guardar.assert_not_called()

    @patch.object(planillas.repo, 'get_nomina')
    @patch.object(boletas_s3, 'guardar', side_effect=RuntimeError('S3 no disponible'))
    def test_fallo_de_persistencia_no_se_oculta(self, guardar, get):
        get.return_value = self.item
        with self.assertRaisesRegex(RuntimeError, 'S3 no disponible'):
            planillas.boleta(self.ctx, self.item['nomina_id'], {})


if __name__ == '__main__':
    unittest.main()
