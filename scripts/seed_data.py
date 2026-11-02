#!/usr/bin/env python3
"""Carga masiva: 30K+ items por tabla (10K × 3 tenants)."""
import boto3
import uuid
import random
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal

ddb = boto3.resource('dynamodb', region_name='us-east-1')
TABLE_RECL = ddb.Table('hcm-reclutamiento-dev')
TABLE_DESE = ddb.Table('hcm-desempeno-dev')

TENANTS = ['andina', 'pacifico', 'sierra']

AREAS = ['Tecnología', 'Finanzas', 'RR.HH.', 'Operaciones', 'Comercial', 'Legal', 'Marketing']
TITULOS = [
    'Desarrollador Backend', 'Desarrollador Frontend', 'Data Scientist',
    'DevOps Engineer', 'Product Manager', 'Analista Financiero', 'Contador Senior',
    'Reclutador', 'Especialista en Nómina', 'Jefe de Operaciones', 'Vendedor',
    'Gerente Comercial', 'Abogado Corporativo', 'Diseñador UX', 'Marketing Digital',
]
NOMBRES = ['Juan', 'María', 'Carlos', 'Ana', 'Luis', 'Rosa', 'Pedro', 'Lucia',
           'Jorge', 'Carmen', 'Diego', 'Elena', 'Fernando', 'Gabriela', 'Hugo']
APELLIDOS = ['García', 'Rodríguez', 'López', 'Martínez', 'Pérez', 'González',
             'Sánchez', 'Fernández', 'Torres', 'Ramírez', 'Flores', 'Castro']
ESTADOS_POST = ['RECIBIDO', 'ENTREVISTA', 'OFERTA', 'CONTRATADO', 'RECHAZADO']
TAREAS_ONB = [
    'Entregar laptop', 'Firmar contrato', 'Acceso a sistemas',
    'Capacitación de bienvenida', 'Configurar email', 'Entregar credencial',
    'Revisar manual', 'Reunión con jefe', 'Setup workspace', 'Firma NDA',
]
COMPETENCIAS = ['Trabajo en equipo', 'Comunicación', 'Puntualidad', 'Liderazgo',
                'Innovación', 'Orientación a resultados', 'Pensamiento crítico']
MENSAJES_REC = [
    'Excelente trabajo en el proyecto', 'Gracias por tu dedicación',
    'Gran colaboración', 'Siempre dispuesto a ayudar',
    'Resultados sobresalientes', 'Mentor increíble', 'Hiciste la diferencia',
]
OBJETIVOS = [
    'Automatizar reporte mensual', 'Capacitación en cloud',
    'Reducir tiempos de respuesta', 'Mejorar comunicación',
    'Finalizar proyecto X', 'Certificación profesional',
]

EMPLEADOS = [f'emp-{str(i).zfill(6)}' for i in range(1, 501)]  # 500 empleados pool


def rand_date(dias=180):
    return (datetime.now(timezone.utc) - timedelta(days=random.randint(0, dias))).isoformat()


def rand_name():
    return f'{random.choice(NOMBRES)} {random.choice(APELLIDOS)}'


def norm_email(nombre):
    tr = str.maketrans('áéíóúÁÉÍÓÚñÑ', 'aeiouAEIOUnN')
    return nombre.translate(tr).lower().replace(' ', '.') + '@test.com'


def seed_reclutamiento():
    print('\n🏢 Reclutamiento')
    for tenant in TENANTS:
        t0 = time.time()
        print(f'  [{tenant}]')
        vacantes_ids = []

        with TABLE_RECL.batch_writer() as batch:
            for _ in range(150):
                vac_id = f'vac-{uuid.uuid4().hex[:8]}'
                vacantes_ids.append(vac_id)
                batch.put_item(Item={
                    'tenant_id': tenant,
                    'sk': f'VACANTE#{vac_id}',
                    'titulo': random.choice(TITULOS),
                    'area': random.choice(AREAS),
                    'estado': random.choice(['ABIERTA', 'ABIERTA', 'ABIERTA', 'CERRADA']),
                    'fecha_publicacion': rand_date(90),
                })
        print(f'    ✓ 150 vacantes')

        contratados = 0
        with TABLE_RECL.batch_writer() as batch:
            for _ in range(5000):
                post_id = f'pos-{uuid.uuid4().hex[:8]}'
                estado = random.choices(ESTADOS_POST, weights=[30, 25, 15, 10, 20])[0]
                if estado == 'CONTRATADO':
                    contratados += 1
                nombre = rand_name()
                batch.put_item(Item={
                    'tenant_id': tenant,
                    'sk': f'POSTULACION#{post_id}',
                    'postulacion_id': post_id,
                    'vacante_id': random.choice(vacantes_ids),
                    'nombre': nombre,
                    'email': norm_email(nombre),
                    'cv_s3_key': f'{tenant}/cvs/{post_id}.pdf',
                    'estado': estado,
                    'fecha': rand_date(60),
                })
        print(f'    ✓ 5000 postulaciones ({contratados} CONTRATADO)')

        with TABLE_RECL.batch_writer() as batch:
            for _ in range(5000):
                emp_id = random.choice(EMPLEADOS)
                onb_id = f'onb-{uuid.uuid4().hex[:8]}'
                batch.put_item(Item={
                    'tenant_id': tenant,
                    'sk': f'ONBOARDING#{emp_id}#{onb_id}',
                    'onboarding_id': onb_id,
                    'empleado_id': emp_id,
                    'tarea': random.choice(TAREAS_ONB),
                    'completada': random.random() < 0.6,
                    'fecha_creacion': rand_date(30),
                })
        print(f'    ✓ 5000 onboarding ({time.time()-t0:.1f}s)')


def seed_desempeno():
    print('\n⭐ Desempeño')
    for tenant in TENANTS:
        t0 = time.time()
        print(f'  [{tenant}]')

        with TABLE_DESE.batch_writer() as batch:
            for _ in range(7000):
                eva_id = f'eva-{uuid.uuid4().hex[:8]}'
                empleado_id = random.choice(EMPLEADOS)
                evaluador_id = random.choice(EMPLEADOS)
                while evaluador_id == empleado_id:
                    evaluador_id = random.choice(EMPLEADOS)
                comps = [
                    {'nombre': c, 'puntaje': Decimal(str(random.randint(2, 5)))}
                    for c in random.sample(COMPETENCIAS, k=random.randint(2, 4))
                ]
                batch.put_item(Item={
                    'tenant_id': tenant,
                    'sk': eva_id,
                    'evaluacion_id': eva_id,
                    'empleado_id': empleado_id,
                    'evaluador_id': evaluador_id,
                    'periodo': random.choice(['2026-S1', '2026-S2', '2025-S2']),
                    'puntaje': Decimal(str(round(random.uniform(2.5, 5.0), 1))),
                    'competencias': comps,
                    'objetivos': random.sample(OBJETIVOS, k=random.randint(1, 3)),
                    'comentarios': 'Buen desempeño en el periodo',
                    'estado': random.choice(['PENDIENTE', 'EN_PROGRESO', 'COMPLETADA', 'COMPLETADA']),
                    'fecha_creacion': rand_date(180),
                })
        print(f'    ✓ 7000 evaluaciones')

        with TABLE_DESE.batch_writer() as batch:
            for _ in range(3000):
                rec_id = f'rec-{uuid.uuid4().hex[:8]}'
                de = random.choice(EMPLEADOS)
                para = random.choice(EMPLEADOS)
                while para == de:
                    para = random.choice(EMPLEADOS)
                batch.put_item(Item={
                    'tenant_id': tenant,
                    'sk': rec_id,
                    'reconocimiento_id': rec_id,
                    'empleado_id': para,
                    'de_empleado_id': de,
                    'mensaje': random.choice(MENSAJES_REC),
                    'fecha': rand_date(90),
                })
        print(f'    ✓ 3000 reconocimientos ({time.time()-t0:.1f}s)')


def verificar():
    print('\n🔍 Verificación (puede tardar ~30s)')
    for nombre, tabla in [('reclutamiento', TABLE_RECL), ('desempeno', TABLE_DESE)]:
        total = 0
        por_tenant = {}
        resp = tabla.scan(ProjectionExpression='tenant_id')
        while True:
            for it in resp['Items']:
                t = it['tenant_id']
                por_tenant[t] = por_tenant.get(t, 0) + 1
                total += 1
            if 'LastEvaluatedKey' not in resp:
                break
            resp = tabla.scan(
                ProjectionExpression='tenant_id',
                ExclusiveStartKey=resp['LastEvaluatedKey']
            )
        print(f'  {nombre}: {total} total → {por_tenant}')


if __name__ == '__main__':
    t0 = time.time()
    print('🚀 Carga masiva (30K+ por tabla, 3 tenants)')
    seed_reclutamiento()
    seed_desempeno()
    print(f'\n✅ Insertado en {time.time()-t0:.1f}s')
    verificar()
