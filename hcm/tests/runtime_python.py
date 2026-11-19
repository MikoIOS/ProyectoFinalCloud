"""Invoca el router empaquetado con handlers reales y AWS simulado, en un proceso aislado."""
import importlib
import json
import os
import sys
from unittest.mock import Mock, patch

artifact, module = sys.argv[1:3]
worker = sys.argv[3] if len(sys.argv) > 3 else None
sys.path.insert(0, artifact)
os.environ.update(AWS_DEFAULT_REGION='us-east-1', AWS_REGION='us-east-1',
                  AWS_ACCESS_KEY_ID='test', AWS_SECRET_ACCESS_KEY='test', AWS_EC2_METADATA_DISABLED='true',
                  JWT_SECRET='secreto-solo-pruebas-de-router-123456789', TABLE_NAME='test',
                  TABLE_USUARIOS='test', TABLE_EMPLEADOS='test',
                  CV_BUCKET='test', BOLETAS_BUCKET='test', TOPIC_ARN='arn:test', EVENTS_TOPIC_ARN='arn:test',
                  EMAIL_TOPIC_ARN='arn:test', STAGE='dev', CANALES='["funcion-de-prueba"]')


def event(method, path, rol='empleado', body=None):
    return {'httpMethod': method, 'resource': path, 'body': json.dumps(body or {}),
            'requestContext': {'authorizer': {'tenant_id': 'andina', 'user_id': 'usr-1', 'rol': rol}},
            'pathParameters': {}}


with patch('boto3.resource') as resource, patch('boto3.client') as client:
    if worker:
        path, name = worker.rsplit('.', 1)
        function = getattr(importlib.import_module(path.replace('/', '.')), name)
        if worker == 'src/handlers/authorizer.handler':
            try:
                function({'authorizationToken': 'inválido'})
            except Exception as error:
                assert str(error) == 'Unauthorized'
            else:
                raise AssertionError('El authorizer aceptó un token inválido')
            from src.common.security import create_token
            token, _ = create_token({'user_id': 'usr-1', 'tenant_id': 'andina', 'rol': 'admin_rrhh'})
            result = function({'authorizationToken': 'Bearer ' + token,
                               'methodArn': 'arn:aws:execute-api:us-east-1:123:api/dev/GET/empleados'})
            assert result['context']['tenant_id'] == 'andina'
            assert result['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        elif worker == 'src/handlers/calendario.handler':
            resource.return_value.Table.return_value.scan.return_value = {'Items': []}
            assert function({}) == {'actualizadas': 0}
        elif worker == 'canales.handler':
            client.return_value.get_paginator.return_value.paginate.return_value = [{'EventSourceMappings': [{'State': 'Disabled'}]}]
            assert function({}) == {'canales_no_habilitados': ['funcion-de-prueba']}
            assert client.return_value.put_metric_data.call_args.kwargs['MetricData'][0]['Value'] == 1
        elif worker == 'avisos.handler':
            alarma = {'AlarmName': 'prueba', 'NewStateValue': 'ALARM', 'StateChangeTime': 'hoy', 'NewStateReason': 'prueba'}
            assert function({'Records': [{'Sns': {'Message': json.dumps(alarma)}}]}) == {'avisos': 1}
            assert 'ALERTA' in client.return_value.publish.call_args.kwargs['Subject']
        else:
            assert function({'Records': []}) == {'batchItemFailures': []}
            if module == 'asistencia':
                record = {'eventName': 'INSERT', 'dynamodb': {'SequenceNumber': 'm-1'}}
            else:
                record = {'messageId': 'm-1', 'body': 'no-json'}
            assert function({'Records': [record]}) == {'batchItemFailures': [{'itemIdentifier': 'm-1'}]}
        print(json.dumps({'module': module, 'worker': worker, 'aws': 'mocked', 'result': 'passed'}))
        sys.exit(0)
    router = importlib.import_module('hcm_http')
    if module in ('usuarios', 'empleados', 'nominas', 'asistencia'):
        method, path = {'usuarios': ('POST', '/usuarios'), 'empleados': ('POST', '/empleados'),
                        'nominas': ('POST', '/nominas/generar'),
                        'asistencia': ('GET', '/asistencia/reportes')}[module]
        response = router.handler(event(method, path))
        assert response['statusCode'] == 403, response
        resource.assert_not_called()
        if module == 'usuarios':
            assert router.handler(event('POST', '/auth/login'))['statusCode'] == 400
            assert router.handler(event('POST', '/auth/register'))['statusCode'] == 400
        if module in ('usuarios', 'empleados', 'asistencia'):
            path = '/ping' if module == 'usuarios' else '/' + module + '/ping'
            assert router.handler({'httpMethod': 'GET', 'resource': path})['statusCode'] == 200
    else:
        path = '/vacantes' if module == 'reclutamiento' else '/evaluaciones'
        body = {'tenant_id': 'pacifico', 'titulo': 'Prueba', 'empleado_id': 'emp-1'}
        response = router.handler(event('POST', path, rol='admin_rrhh', body=body))
        assert response['statusCode'] == 201, response
        table = resource.return_value.Table.return_value
        item = table.put_item.call_args.kwargs['Item']
        assert item['tenant_id'] == 'andina', item
        assert json.loads(response['body'])['tenant_id'] == 'andina'
    print(json.dumps({'module': module, 'real_handlers': 'passed', 'aws': 'mocked'}))
