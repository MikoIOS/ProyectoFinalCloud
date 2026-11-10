import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with patch.dict(os.environ, {'AWS_ACCESS_KEY_ID': 'testing', 'AWS_SECRET_ACCESS_KEY': 'testing',
    'AWS_DEFAULT_REGION': 'us-east-1', 'TABLE_NAME': 'test', 'CV_BUCKET': 'test',
    'EVENTS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test'}):
    from handlers import postulaciones


class DocumentoTest(unittest.TestCase):
    def evento(self, **body):
        return {'requestContext': {'authorizer': {'tenant_id': 'andina'}},
                'body': json.dumps({'vacante_id': 'vac-prueba', 'nombre': 'Candidata Prueba', **body})}

    @patch.object(postulaciones, 'table')
    @patch.object(postulaciones, 's3')
    def test_documento_invalido_no_crea_postulacion(self, s3, table):
        for documento in ('ABC', '1234567', '123456789', 12345678, '１２３４５６７８'):
            with self.subTest(documento=documento):
                self.assertEqual(postulaciones.crear(self.evento(documento=documento), None)['statusCode'], 400)
        table.put_item.assert_not_called()
        s3.generate_presigned_url.assert_not_called()

    @patch.object(postulaciones, 'table')
    @patch.object(postulaciones, 's3')
    def test_documento_valido_conserva_ceros_iniciales(self, s3, table):
        s3.generate_presigned_url.return_value = 'https://test.s3.amazonaws.com/cv.pdf'
        self.assertEqual(postulaciones.crear(self.evento(documento='01234567'), None)['statusCode'], 201)
        self.assertEqual(table.put_item.call_args.kwargs['Item']['documento'], '01234567')

    @patch.object(postulaciones, 'table')
    @patch.object(postulaciones, 's3')
    def test_documento_opcional_sigue_soportado(self, s3, table):
        s3.generate_presigned_url.return_value = 'https://test.s3.amazonaws.com/cv.pdf'
        self.assertEqual(postulaciones.crear(self.evento(), None)['statusCode'], 201)
        self.assertNotIn('documento', table.put_item.call_args.kwargs['Item'])
