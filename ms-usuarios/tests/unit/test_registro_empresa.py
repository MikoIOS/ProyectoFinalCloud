import json
import os
import unittest
from unittest.mock import patch

import boto3
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from src.common.errors import Conflicto
from src.common.security import decode_token, verify_password
from src.handlers import auth
from src.repositories import usuarios_repo


class RegistroEmpresaTest(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'JWT_SECRET': 'secreto-unitario-no-produccion-1234567890'})
        env.start()
        self.addCleanup(env.stop)
        self.body = {'empresa': 'Mi Empresa', 'ruc': '20123456789', 'nombre': 'Ana', 'email': 'ana@empresa.pe', 'password': 'Demo1234!'}
        parche = patch('src.services.auth_service.usuarios_repo')
        self.repo = parche.start()
        self.addCleanup(parche.stop)
        self.repo.email_existe.return_value = False

    def registrar(self, **cambios):
        respuesta = auth.registrar_empresa({'body': json.dumps(dict(self.body, **cambios))})
        return respuesta['statusCode'], json.loads(respuesta['body'])

    def test_crea_empresa_admin_y_login(self):
        status, datos = self.registrar(email='  ANA@Empresa.pe ')
        self.assertEqual(status, 201)
        user = datos['usuario']
        self.assertEqual(user['empresa_nombre'], 'Mi Empresa')
        self.assertEqual(user['ruc'], self.body['ruc'])
        self.assertEqual(user['rol'], 'admin_rrhh')
        self.assertNotIn(user['tenant_id'], ('andina', 'pacifico', 'sierra'))
        self.assertFalse(user['debe_cambiar_password'])
        self.assertEqual(decode_token(datos['token'])['tenant_id'], user['tenant_id'])
        item = self.repo.registrar_empresa.call_args.args[0]
        self.assertTrue(verify_password(self.body['password'], item['password_hash']))
        self.assertEqual(item['email'], 'ana@empresa.pe')
        self.assertEqual(item['ruc'], self.body['ruc'])
        self.assertNotIn('password_hash', json.dumps(datos))
        self.assertNotIn(self.body['password'], json.dumps(datos))
        self.repo.get_by_login_email.return_value = item
        respuesta = auth.login({'body': json.dumps({'email': item['email'], 'password': self.body['password']})})
        self.assertEqual(respuesta['statusCode'], 200)
        self.assertEqual(json.loads(respuesta['body'])['usuario']['empresa_nombre'], 'Mi Empresa')

    def test_correo_existente(self):
        self.repo.email_existe.return_value = True
        self.assertEqual(self.registrar()[0], 409)
        self.repo.registrar_empresa.assert_not_called()

    def test_conflicto_concurrente_no_devuelve_sesion(self):
        self.repo.registrar_empresa.side_effect = Conflicto('Correo reservado')
        status, datos = self.registrar()
        self.assertEqual(status, 409)
        self.assertNotIn('token', datos)

    def test_campos_invalidos_no_escriben(self):
        for cambio in ({'empresa': ' '}, {'empresa': []}, {'nombre': None},
                       {'email': 'incorrecto'}, {'password': 'corta'}, {'password': 123},
                       {'empresa': 'x' * 121}, {'password': 'x' * 129},
                       {'ruc': None}, {'ruc': ''}, {'ruc': 20123456789},
                       {'ruc': '1234567890'}, {'ruc': '123456789012'},
                       {'ruc': '2012345678a'}, {'ruc': '２０１２３４５６７８９'},
                       {'tenant_id': 'andina'}, {'rol': 'admin_rrhh'}):
            with self.subTest(cambio=cambio):
                self.assertEqual(self.registrar(**cambio)[0], 400)
        self.repo.registrar_empresa.assert_not_called()

    def test_ruc_ausente_no_crea_empresa(self):
        del self.body['ruc']
        self.assertEqual(self.registrar()[0], 400)
        self.repo.registrar_empresa.assert_not_called()

    def test_empresas_nuevas_aisladas(self):
        _, a = self.registrar()
        _, b = self.registrar(email='otra@empresa.pe')
        self.assertNotEqual(a['usuario']['tenant_id'], b['usuario']['tenant_id'])
        self.assertNotEqual(a['usuario']['user_id'], b['usuario']['user_id'])

    def test_json_invalido(self):
        for body in ('no-json', '[]', 'null'):
            self.assertEqual(auth.registrar_empresa({'body': body})['statusCode'], 400)


class ReservaEmpresaTest(unittest.TestCase):
    def test_transaccion_valida_y_conflictos(self):
        tabla = boto3.resource('dynamodb', region_name='us-east-1',
                               aws_access_key_id='test', aws_secret_access_key='test').Table('hcm-usuarios')
        usuario = {'tenant_id': 'empresa-123', 'user_id': 'usr-123', 'email': 'ana@empresa.pe'}
        with patch.object(usuarios_repo, '_table', return_value=tabla), Stubber(tabla.meta.client) as stub:
            stub.add_response('transact_write_items', {})
            self.assertEqual(usuarios_repo.registrar_empresa(usuario)['email'], usuario['email'])
            stub.add_client_error('transact_write_items', service_error_code='TransactionCanceledException',
                                  modeled_fields={'CancellationReasons': [{'Code': 'ConditionalCheckFailed'}]})
            with self.assertRaises(Conflicto):
                usuarios_repo.registrar_empresa(usuario)
            stub.add_client_error('transact_write_items', service_error_code='AccessDeniedException')
            with self.assertRaises(ClientError):
                usuarios_repo.registrar_empresa(usuario)
            stub.assert_no_pending_responses()


if __name__ == '__main__':
    unittest.main()
