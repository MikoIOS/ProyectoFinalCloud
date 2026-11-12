"""Activa vacaciones al comenzar y finaliza ausencias al terminar el último día."""
from boto3.dynamodb.conditions import Attr

from src.common.errors import Conflicto
from src.repositories import asistencia as repo
from src.services.asistencia import ahora


def handler(event, context=None):
    hoy = ahora().date().isoformat()
    args = {'FilterExpression': Attr('clase').eq('AUS') & Attr('estado').eq('APROBADA')}
    cambios = 0
    while True:
        page = repo.tabla().scan(**args)
        for snapshot in page['Items']:
            tenant, emp = snapshot['tenant_id'], snapshot['empleado_id']
            version = repo.version(tenant, emp)
            item = repo.get(tenant, snapshot['sk'])
            if not item or item['estado'] != 'APROBADA':
                continue
            if item['hasta'] < hoy:
                item['estado'] = 'FINALIZADA'
            elif item['tipo'] == 'VACACIONES' and item['desde'] <= hoy and not item.get('iniciada'):
                item['iniciada'] = True
            else:
                continue
            item['updated_at'] = ahora().isoformat()
            try:
                repo.guardar_ausencia(item, version)
                cambios += 1
            except Conflicto:
                continue  # La próxima ejecución revisará la versión nueva.
        if not page.get('LastEvaluatedKey'):
            return {'actualizadas': cambios}
        args['ExclusiveStartKey'] = page['LastEvaluatedKey']
