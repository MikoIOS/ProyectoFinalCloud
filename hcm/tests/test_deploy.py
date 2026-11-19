import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import deploy


class DeploymentSecretTest(unittest.TestCase):
    def execute(self, responses):
        aws = Mock()
        aws.client.return_value.get_caller_identity.return_value = {'Account': '123456789012'}
        aws.client.return_value.get_function_configuration.side_effect = responses
        with tempfile.TemporaryDirectory() as tmp, patch.object(deploy, '__file__', str(Path(tmp) / 'deploy.py')), \
                patch.object(deploy.boto3, 'Session', return_value=aws), \
                patch.object(deploy.subprocess, 'run') as run, \
                patch.object(sys, 'argv', ['deploy.py', '--stage', 'dev']), \
                patch.dict(os.environ, {'PATH': '/test'}, clear=True):
            deploy.main()
            return aws, run.call_args_list[0].kwargs['env']['HCM_JWT_SECRET_dev']

    def test_conserva_secreto_de_lambda_agrupada(self):
        secret = 'secreto-real-guardado-para-el-test-1234567890'
        aws, actual = self.execute([{'Environment': {'Variables': {'JWT_SECRET': secret}}}])
        self.assertEqual(actual, secret)
        aws.client.return_value.get_function_configuration.assert_called_once_with(FunctionName='hcm-dev-usuarios_http')

    def test_primera_migracion_conserva_secreto_del_login_anterior(self):
        missing = ClientError({'Error': {'Code': 'ResourceNotFoundException'}}, 'GetFunctionConfiguration')
        secret = 'secreto-anterior-de-login-12345678901234567890'
        aws, actual = self.execute([missing, {'Environment': {'Variables': {'JWT_SECRET': secret}}}])
        self.assertEqual(actual, secret)
        self.assertEqual(aws.client.return_value.get_function_configuration.call_args.kwargs['FunctionName'], 'hcm-dev-usuarios_login')

    def test_falta_de_permisos_no_genera_otro_secreto(self):
        denied = ClientError({'Error': {'Code': 'AccessDeniedException'}}, 'GetFunctionConfiguration')
        with self.assertRaises(ClientError):
            self.execute([denied])
