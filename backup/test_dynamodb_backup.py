import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from dynamodb_backup import prepare_bucket, run


class BackupTest(unittest.TestCase):
    def client(self):
        client = Mock()
        client.describe_table.return_value = {'Table': {'TableName': 'hcm-dev-usuarios', 'TableArn': 'arn:aws:dynamodb:us-east-1:123:table/hcm-dev-usuarios'}}
        client.describe_continuous_backups.return_value = {'ContinuousBackupsDescription': {'PointInTimeRecoveryDescription': {'PointInTimeRecoveryStatus': 'ENABLED'}}}
        client.export_table_to_point_in_time.return_value = {'ExportDescription': {'ExportArn': 'arn:export:test', 'ExportStatus': 'IN_PROGRESS'}}
        client.describe_export.return_value = {'ExportDescription': {'ExportStatus': 'COMPLETED', 'ItemCount': 10, 'ExportManifest': 'data/manifest-summary.json'}}
        return client

    def test_exporta_directo_a_s3_sin_scan(self):
        client, s3 = self.client(), Mock()
        with tempfile.TemporaryDirectory() as tmp:
            directory = run(client, s3, 'bucket-test', tmp, ['hcm-dev-usuarios'])
            manifest = json.loads((directory / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'COMPLETE')
            self.assertEqual(manifest['tables'][0]['item_count'], 10)
            params = client.export_table_to_point_in_time.call_args.kwargs
            self.assertEqual(params['S3Bucket'], 'bucket-test')
            self.assertEqual(params['S3SseAlgorithm'], 'AES256')
            self.assertEqual(params['ExportFormat'], 'DYNAMODB_JSON')
            client.get_paginator.assert_not_called()
            client.update_continuous_backups.assert_not_called()
            self.assertEqual(json.loads(s3.put_object.call_args.kwargs['Body'])['status'], 'COMPLETE')
            self.assertEqual(list(directory.iterdir()), [directory / 'manifest.json'])
            self.assertEqual((directory / 'manifest.json').stat().st_mode & 0o777, 0o600)

    def test_error_aws_no_confirma_copia(self):
        client = self.client()
        client.describe_export.return_value = {'ExportDescription': {'ExportStatus': 'FAILED', 'FailureMessage': 'Acceso denegado'}}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, 'Acceso denegado'):
                run(client, Mock(), 'bucket-test', tmp, ['hcm-dev-usuarios'])
            manifest = json.loads(next(Path(tmp).glob('*/manifest.json')).read_text())
            self.assertEqual(manifest['status'], 'FAILED')
            self.assertEqual(manifest['tables'][0]['export_arn'], 'arn:export:test')

    def test_ctrl_c_conserva_identificador_y_marca_interrupcion(self):
        client = self.client()
        client.describe_export.side_effect = KeyboardInterrupt
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(KeyboardInterrupt):
                run(client, Mock(), 'bucket-test', tmp, ['hcm-dev-usuarios'])
            manifest = json.loads(next(Path(tmp).glob('*/manifest.json')).read_text())
            self.assertEqual(manifest['status'], 'INTERRUPTED')
            self.assertEqual(manifest['tables'][0]['export_arn'], 'arn:export:test')

    def test_fallo_de_subida_no_inicia_exportaciones(self):
        client, s3 = self.client(), Mock()
        s3.put_object.side_effect = RuntimeError('sin red')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                run(client, s3, 'bucket-test', tmp, ['hcm-dev-usuarios'])
            client.export_table_to_point_in_time.assert_not_called()
            manifest = json.loads(next(Path(tmp).glob('*/manifest.json')).read_text())
            self.assertEqual(manifest['status'], 'FAILED')

    def test_espera_exportacion_y_habilita_pitr(self):
        client = self.client()
        disabled = {'ContinuousBackupsDescription': {'PointInTimeRecoveryDescription': {'PointInTimeRecoveryStatus': 'DISABLED'}}}
        enabled = client.describe_continuous_backups.return_value
        client.describe_continuous_backups.side_effect = [disabled, enabled]
        client.describe_export.side_effect = [{'ExportDescription': {'ExportStatus': 'IN_PROGRESS'}}, {'ExportDescription': {'ExportStatus': 'COMPLETED'}}]
        with tempfile.TemporaryDirectory() as tmp, patch('dynamodb_backup.time.sleep') as sleep:
            run(client, Mock(), 'bucket-test', tmp, ['hcm-dev-usuarios'])
            client.update_continuous_backups.assert_called_once()
            sleep.assert_called_once_with(30)

    def test_no_confirma_cero_tablas(self):
        client = self.client()
        client.get_paginator.return_value.paginate.return_value = [{'TableNames': ['ajena']}]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                run(client, Mock(), 'bucket-test', tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_no_crea_bucket_tras_error_de_acceso(self):
        s3 = Mock()
        s3.head_bucket.side_effect = ClientError({'Error': {'Code': '403'}}, 'HeadBucket')
        with self.assertRaises(ClientError):
            prepare_bucket(s3, 'bucket-test', '123', 'us-east-1')
        s3.create_bucket.assert_not_called()
        s3.put_public_access_block.assert_not_called()

    def test_crea_bucket_y_bloquea_acceso_publico(self):
        s3 = Mock()
        s3.head_bucket.side_effect = [ClientError({'Error': {'Code': '404'}}, 'HeadBucket'), {}]
        prepare_bucket(s3, 'bucket-test', '123', 'us-east-1')
        s3.create_bucket.assert_called_once_with(Bucket='bucket-test')
        self.assertEqual(s3.head_bucket.call_args.kwargs['ExpectedBucketOwner'], '123')
        self.assertTrue(all(s3.put_public_access_block.call_args.kwargs['PublicAccessBlockConfiguration'].values()))


if __name__ == '__main__':
    unittest.main()
