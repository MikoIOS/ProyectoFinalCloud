import json
import os
import unittest
from datetime import datetime
from unittest.mock import patch

import boto3
from boto3.dynamodb.types import TypeSerializer
from moto import mock_aws

from src.common.auth import Ctx
from src.common.errors import Conflicto, NoEncontrado, Prohibido, Validacion
from src.handlers import calendario, eventos, http
from src.repositories import asistencia as repo
from src.services import asistencia as svc


@mock_aws
class AsistenciaTest(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'AWS_DEFAULT_REGION': 'us-east-1', 'TABLE_NAME': 'asistencia',
            'TABLE_EMPLEADOS': 'empleados', 'TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:eventos'})
        env.start()
        self.addCleanup(env.stop)
        db = boto3.resource('dynamodb')
        for name, key in [('asistencia', 'sk'), ('empleados', 'empleado_id')]:
            db.create_table(TableName=name, BillingMode='PAY_PER_REQUEST',
                AttributeDefinitions=[{'AttributeName': 'tenant_id', 'AttributeType': 'S'},
                                      {'AttributeName': key, 'AttributeType': 'S'}],
                KeySchema=[{'AttributeName': 'tenant_id', 'KeyType': 'HASH'}, {'AttributeName': key, 'KeyType': 'RANGE'}])
        for tenant in ('andina', 'pacifico'):
            for emp in ('emp-1', 'emp-2', 'emp-3'):
                db.Table('empleados').put_item(Item={'tenant_id': tenant, 'empleado_id': emp,
                    'estado': 'ACTIVO', 'jefe_id': 'emp-3'})
        self.admin = Ctx('andina', 'admin_rrhh', 'usr-1', 'emp-1')
        self.emp = Ctx('andina', 'empleado', 'usr-2', 'emp-2')
        self.jefe = Ctx('andina', 'gerente', 'usr-3', 'emp-3')
        clock = patch.object(svc, 'ahora', return_value=datetime(2026, 11, 9, 18, 0, tzinfo=svc.ZONA))
        clock.start()
        self.addCleanup(clock.stop)

    def solicitar(self, **kw):
        return svc.solicitar(self.emp, {'tipo': 'PERMISO', 'desde': '2026-11-10',
            'hasta': '2026-11-11', 'motivo': 'E2E', **kw})

    def resolver(self, item, estado='APROBADA', ctx=None):
        return svc.resolver(ctx or self.admin, item['ausencia_id'], {'empleado_id': 'emp-2', 'estado': estado})

    def test_marcaciones(self):
        b = {'empleado_id': 'emp-2', 'fecha': '2026-11-08'}
        self.assertEqual(svc.marcar(self.admin, {**b, 'hora': '09:25', 'tipo': 'ENTRADA'})['tardanza_minutos'], 15)
        with self.assertRaises(Conflicto):
            svc.marcar(self.admin, {**b, 'hora': '09:25', 'tipo': 'ENTRADA'})
        with self.assertRaises(Validacion):
            svc.marcar(self.admin, {**b, 'hora': '08:00', 'tipo': 'SALIDA'})
        self.assertEqual(svc.marcar(self.admin, {**b, 'hora': '17:55', 'tipo': 'SALIDA'})['horas'], 8.5)
        with self.assertRaises(Conflicto):
            svc.marcar(self.admin, {**b, 'hora': '18:00', 'tipo': 'SALIDA'})

    def test_permisos_marcacion(self):
        for b in ({'fecha': '2026-11-08'}, {'empleado_id': 'emp-1'}):
            with self.assertRaises(Prohibido):
                svc.marcar(self.emp, b)
        with self.assertRaises(Validacion):
            svc.marcar(self.admin, {'fecha': '2026-11-10', 'hora': '09:00'})

    def test_cruce_cancelacion(self):
        a = self.solicitar()
        with self.assertRaises(Conflicto):
            self.solicitar()
        self.resolver(a, 'CANCELADA', self.emp)
        self.assertEqual(self.solicitar()['estado'], 'PENDIENTE')

    def test_roles_transiciones_tenants(self):
        a = self.solicitar()
        with self.assertRaises(Prohibido):
            self.resolver(a, ctx=self.emp)
        with self.assertRaises(NoEncontrado):
            svc.obtener(Ctx('pacifico', 'admin_rrhh', 'usr-1', 'emp-1'), a['ausencia_id'], 'emp-2')
        self.assertEqual(self.resolver(a, ctx=self.jefe)['estado'], 'APROBADA')
        for estado in ('RECHAZADA', 'FINALIZADA'):
            with self.assertRaises(Conflicto):
                self.resolver(a, estado)

    def test_validacion_y_saldo(self):
        for kw in ({'desde': '2026-02-30'}, {'hasta': '2026-11-01'}, {'tipo': []},
                   {'hasta': '2027-11-01'}, {'motivo': ''}):
            with self.subTest(kw=kw), self.assertRaises(Validacion):
                self.solicitar(**kw)
        a = self.solicitar(tipo='VACACIONES', desde='2026-12-01', hasta='2026-12-30')
        self.assertEqual(svc.saldo_de(repo.ausencias('andina', 'emp-2'), 2026)['dias_disponibles'], 0)
        with self.assertRaises(Conflicto):
            self.solicitar(tipo='VACACIONES', desde='2026-12-31', hasta='2026-12-31')
        self.resolver(a, 'RECHAZADA')
        self.assertEqual(svc.saldo_de(repo.ausencias('andina', 'emp-2'), 2026)['dias_disponibles'], 30)

    def test_concurrencia(self):
        a = self.solicitar()
        a['estado'] = 'APROBADA'
        with self.assertRaises(Conflicto):
            repo.guardar_ausencia(a, 0)
        self.assertEqual(repo.get('andina', a['sk'])['estado'], 'PENDIENTE')

    def test_paginacion_aislada(self):
        self.solicitar()
        self.solicitar(desde='2026-11-20', hasta='2026-11-21')
        page = repo.listar('andina', 'AUS', {'limit': '1'}, 'emp-2')
        self.assertEqual(len(page['items']), 1)
        token = page['next_token']
        self.assertTrue(token)
        self.assertEqual(len(repo.listar('andina', 'AUS', {'next_token': token}, 'emp-2')['items']), 1)
        for tenant, emp in [('pacifico', 'emp-2'), ('andina', 'emp-1')]:
            with self.assertRaises(Validacion):
                repo.listar(tenant, 'AUS', {'next_token': token}, emp)

    def test_http_auth_y_body(self):
        self.assertEqual(http.solicitar({'body': '{}'})['statusCode'], 401)
        event = {'requestContext': {'authorizer': {'tenant_id': 'andina', 'rol': 'empleado',
            'user_id': 'usr-2', 'empleado_id': 'emp-2'}}, 'body': '[]'}
        self.assertEqual(http.solicitar(event)['statusCode'], 400)

    def test_calendario(self):
        a = self.resolver(self.solicitar(tipo='VACACIONES', desde='2026-11-10', hasta='2026-11-11'))
        self.assertFalse(a['iniciada'])
        with patch.object(calendario, 'ahora', return_value=datetime(2026, 11, 10, 0, 5, tzinfo=svc.ZONA)):
            self.assertEqual(calendario.handler({})['actualizadas'], 1)
            self.assertTrue(repo.get('andina', a['sk'])['iniciada'])
            self.assertEqual(calendario.handler({})['actualizadas'], 0)
        with patch.object(calendario, 'ahora', return_value=datetime(2026, 11, 12, 0, 5, tzinfo=svc.ZONA)):
            calendario.handler({})
        self.assertEqual(repo.get('andina', a['sk'])['estado'], 'FINALIZADA')

    def test_stream_publica_y_reintenta(self):
        a = self.solicitar()
        ser = TypeSerializer()
        rec = {'eventName': 'INSERT', 'eventID': 'event-1', 'dynamodb': {
            'SequenceNumber': '123', 'NewImage': {k: ser.serialize(v) for k, v in a.items()}}}
        sns = boto3.client('sns')
        topic = sns.create_topic(Name='eventos')['TopicArn']
        with patch.dict(os.environ, {'TOPIC_ARN': topic}):
            with patch.object(eventos.boto3, 'client', return_value=sns), patch.object(sns, 'publish', wraps=sns.publish) as publish:
                self.assertEqual(eventos.handler({'Records': [rec]}), {'batchItemFailures': []})
                evt = json.loads(publish.call_args.kwargs['Message'])
                self.assertEqual(evt['tipo_evento'], 'AusenciaSolicitada')
                self.assertEqual(evt['timestamp'], a['updated_at'])
            with patch.object(eventos.boto3, 'client', side_effect=RuntimeError('SNS caído')):
                self.assertEqual(eventos.handler({'Records': [rec]})['batchItemFailures'], [{'itemIdentifier': '123'}])

    def test_seed_deterministico(self):
        from scripts.seed_asistencia import registro
        self.assertEqual(registro('andina', 2), registro('andina', 2))
        self.assertNotEqual(registro('andina', 2)['tenant_id'], registro('pacifico', 2)['tenant_id'])
        self.assertEqual(registro('andina', 2)['horas'], 8)
        self.assertTrue(registro('andina', 2)['seed'])
