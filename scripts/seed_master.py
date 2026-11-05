#!/usr/bin/env python3
"""
Seed Maestro HCM (Grupo 2 · SaaS HCM)

Genera y carga masivamente >= 30,000 registros por microservicio repartidos
en 3 tenants ('andina', 'pacifico', 'sierra'), asegurando coherencia total de IDs:
  - usr-{n:06d}  <--->  emp-{n:06d}
  - Mismo nombre, correo, área y jerarquía sin ciclos.
  - Vacantes -> Postulaciones -> Onboarding.
  - Empleados -> Evaluaciones -> Reconocimientos.
  - Usuarios -> Notificaciones coherentes.

Uso:
  python scripts/seed_master.py --create-tables            # Crea las tablas si no existen y carga 30k por tabla
  python scripts/seed_master.py --stage dev                # Carga en tablas existentes dev
  python scripts/seed_master.py --count 100 --test         # Prueba rápida de 100 registros por tenant
  python scripts/seed_master.py --services notificaciones  # Carga solo un microservicio específico
"""
import argparse
import random
import time
import unicodedata
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError

DEFAULT_TENANTS = ["andina", "pacifico", "sierra"]
PASSWORD_HASH_DEMO = "scrypt$16384$8$1$Vn6EExTVcqi/XiqSgjW5Tg==$Y4ffUq6+JJTED4YtaAUVvmYbBMPlJJTnq1oCIuEDyv4="

NOMBRES = [
    "María", "José", "Luis", "Carmen", "Juan", "Rosa", "Carlos", "Ana", "Miguel", "Lucía",
    "Jorge", "Elena", "Pedro", "Sofía", "Diego", "Valeria", "Andrés", "Camila", "Javier", "Paula",
    "Fernando", "Daniela", "Ricardo", "Fiorella", "Renzo", "Milagros", "Sebastián", "Gabriela"
]
APELLIDOS = [
    "Quispe", "Huamán", "Flores", "Rojas", "Mendoza", "Vargas", "Castillo", "Torres", "Ramos", "Chávez",
    "Salazar", "Paredes", "Gutiérrez", "Cárdenas", "Ríos", "Vega", "Soto", "Ortiz", "Silva", "Peña",
    "Delgado", "Cruz", "Medina", "Campos", "Aguilar", "Espinoza", "Villanueva", "Palomino"
]

CARGOS = {
    "Recursos Humanos": ["Analista de Nóminas", "Asistente de RR. HH.", "Especialista en Bienestar", "Reclutador"],
    "Tecnología": ["Desarrollador Backend", "Desarrollador Frontend", "DevOps Engineer", "Analista de Datos"],
    "Ventas": ["Ejecutivo Comercial", "Asesor de Ventas", "Analista Comercial", "Gerente Comercial"],
    "Finanzas": ["Contador Senior", "Analista Financiero", "Asistente Contable"],
    "Operaciones": ["Supervisor de Operaciones", "Analista de Procesos", "Jefe de Operaciones"],
    "Marketing": ["Community Manager", "Analista de Marketing", "Diseñador UX"],
    "Legal": ["Abogado Corporativo", "Analista de Cumplimiento"],
}
AREAS = list(CARGOS.keys())

TAREAS_ONBOARDING = [
    "Entregar laptop y accesos", "Firmar contrato laboral", "Capacitación de bienvenida",
    "Configurar correo corporativo", "Entregar credencial de acceso", "Firma de código de conducta",
    "Reunión de inducción con jefatura", "Setup de herramientas de trabajo"
]

COMPETENCIAS = [
    "Trabajo en equipo", "Orientación a resultados", "Comunicación efectiva",
    "Liderazgo", "Innovación", "Pensamiento crítico", "Adaptabilidad"
]

RECONOCIMIENTOS = [
    "Excelente trabajo en la entrega del proyecto", "Gracias por tu apoyo y compañerismo",
    "Gran iniciativa e innovación en los procesos", "Compromiso ejemplar con el equipo",
    "Actitud positiva y resolución rápida de problemas"
]

TIPOS_NOTIFICACION = [
    ("BOLETA_DISPONIBLE", "Tu boleta de pago ya se encuentra disponible en el portal."),
    ("EVALUACION_COMPLETADA", "Se ha registrado y completado tu evaluación de desempeño."),
    ("AUSENCIA_APROBADA", "Tu solicitud de vacaciones/permiso ha sido aprobada por tu jefatura."),
    ("BIENVENIDA", "Bienvenido al equipo de trabajo de la empresa."),
    ("RECONOCIMIENTO", "¡Felicitaciones! Has recibido un reconocimiento de un compañero de equipo.")
]


def norm_ascii(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def rand_date(dias_atras=180) -> str:
    fecha = datetime.now(timezone.utc) - timedelta(days=random.randint(0, dias_atras), minutes=random.randint(0, 1440))
    return fecha.isoformat()


def resolver_nombres_tablas(stage: str):
    return {
        "usuarios": f"hcm-usuarios-{stage}",
        "empleados": f"hcm-empleados-{stage}",
        "reclutamiento": f"hcm-reclutamiento-{stage}",
        "desempeno": f"hcm-desempeno-{stage}",
        "notificaciones": f"hcm-notificaciones-{stage}"
    }


def crear_tablas_si_no_existen(ddb_client, ddb_resource, tables_map):
    existentes = ddb_client.list_tables().get("TableNames", [])
    print("\n📦 Verificando tablas DynamoDB...")

    # 1. hcm-usuarios
    tbl_usr = tables_map["usuarios"]
    if tbl_usr not in existentes and "hcm-usuarios" not in existentes:
        print(f"  Creando tabla {tbl_usr}...")
        ddb_client.create_table(
            TableName=tbl_usr,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "tenant_id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "email", "AttributeType": "S"},
                {"AttributeName": "empleado_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "user_id", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "email-index",
                    "KeySchema": [
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "email", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                },
                {
                    "IndexName": "empleado-index",
                    "KeySchema": [
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "empleado_id", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "KEYS_ONLY"}
                }
            ]
        )
        ddb_resource.Table(tbl_usr).wait_until_exists()
        print(f"  ✓ Tabla {tbl_usr} creada.")

    # 2. hcm-empleados
    tbl_emp = tables_map["empleados"]
    if tbl_emp not in existentes and "hcm-empleados" not in existentes:
        print(f"  Creando tabla {tbl_emp}...")
        ddb_client.create_table(
            TableName=tbl_emp,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "tenant_id", "AttributeType": "S"},
                {"AttributeName": "empleado_id", "AttributeType": "S"},
                {"AttributeName": "area", "AttributeType": "S"},
                {"AttributeName": "jefe_id", "AttributeType": "S"},
                {"AttributeName": "estado", "AttributeType": "S"},
                {"AttributeName": "documento", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "empleado_id", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "area-index",
                    "KeySchema": [
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "area", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "INCLUDE", "NonKeyAttributes": ["nombres", "apellidos", "cargo", "estado"]}
                },
                {
                    "IndexName": "jefe-index",
                    "KeySchema": [
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "jefe_id", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "INCLUDE", "NonKeyAttributes": ["nombres", "apellidos", "cargo", "area"]}
                },
                {
                    "IndexName": "estado-index",
                    "KeySchema": [
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "estado", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "INCLUDE", "NonKeyAttributes": ["nombres", "apellidos", "cargo", "area"]}
                },
                {
                    "IndexName": "documento-index",
                    "KeySchema": [
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "documento", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "KEYS_ONLY"}
                }
            ]
        )
        ddb_resource.Table(tbl_emp).wait_until_exists()
        print(f"  ✓ Tabla {tbl_emp} creada.")

    # 3. hcm-reclutamiento
    tbl_rec = tables_map["reclutamiento"]
    if tbl_rec not in existentes:
        print(f"  Creando tabla {tbl_rec}...")
        ddb_client.create_table(
            TableName=tbl_rec,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "tenant_id", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "vacante_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "vacante-index",
                    "KeySchema": [
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "vacante_id", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                }
            ]
        )
        ddb_resource.Table(tbl_rec).wait_until_exists()
        print(f"  ✓ Tabla {tbl_rec} creada.")

    # 4. hcm-desempeno
    tbl_des = tables_map["desempeno"]
    if tbl_des not in existentes:
        print(f"  Creando tabla {tbl_des}...")
        ddb_client.create_table(
            TableName=tbl_des,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "tenant_id", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "empleado_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "empleado-index",
                    "KeySchema": [
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "empleado_id", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                }
            ]
        )
        ddb_resource.Table(tbl_des).wait_until_exists()
        print(f"  ✓ Tabla {tbl_des} creada.")

    # 5. hcm-notificaciones
    tbl_not = tables_map["notificaciones"]
    if tbl_not not in existentes:
        print(f"  Creando tabla {tbl_not}...")
        ddb_client.create_table(
            TableName=tbl_not,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "tenant_id", "AttributeType": "S"},
                {"AttributeName": "notificacion_id", "AttributeType": "S"},
                {"AttributeName": "destinatario_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "notificacion_id", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "destinatario-index",
                    "KeySchema": [
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "destinatario_id", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                }
            ]
        )
        ddb_resource.Table(tbl_not).wait_until_exists()
        print(f"  ✓ Tabla {tbl_not} creada.")


def obtener_referencia_tabla(ddb_resource, ddb_client, base_name, stage_name):
    existentes = ddb_client.list_tables().get("TableNames", [])
    if stage_name in existentes:
        return ddb_resource.Table(stage_name)
    if base_name in existentes:
        return ddb_resource.Table(base_name)
    return ddb_resource.Table(stage_name)


# ==============================================================================
# CARGA DE DATOS POR SERVICIO
# ==============================================================================

def seed_usuarios_y_empleados(tbl_usr, tbl_emp, tenants, count_per_tenant):
    print(f"\n👥 1 & 2. Cargando Usuarios y Empleados ({count_per_tenant} por tenant)...")
    ahora_iso = datetime.now(timezone.utc).isoformat()

    for tenant in tenants:
        t0 = time.time()
        print(f"  🏢 Tenant: [{tenant}]")
        rng = random.Random(42)  # Misma semilla determinista para sincronía

        with tbl_usr.batch_writer() as b_usr, tbl_emp.batch_writer() as b_emp:
            for n in range(1, count_per_tenant + 1):
                nombre = rng.choice(NOMBRES)
                apellido1 = rng.choice(APELLIDOS)
                apellido2 = rng.choice(APELLIDOS)
                apellidos = f"{apellido1} {apellido2}"
                area = AREAS[n % len(AREAS)]
                cargo = CARGOS[area][n % len(CARGOS[area])]

                # Roles demo para n=1..4
                if n == 1:
                    rol, correo_local = "admin_rrhh", "admin"
                elif n == 2:
                    rol, correo_local = "empleado", "empleado"
                elif n == 3:
                    rol, correo_local = "gerente", "gerente"
                elif n == 4:
                    rol, correo_local = "reclutador", "reclutador"
                elif n % 500 == 0:
                    rol, correo_local = "gerente", f"{norm_ascii(nombre)}.{norm_ascii(apellido1)}.{n}"
                elif n % 250 == 0:
                    rol, correo_local = "reclutador", f"{norm_ascii(nombre)}.{norm_ascii(apellido1)}.{n}"
                else:
                    rol, correo_local = "empleado", f"{norm_ascii(nombre)}.{norm_ascii(apellido1)}.{n}"

                email = f"{correo_local}@{tenant}.pe"
                user_id = f"usr-{str(n).zfill(6)}"
                emp_id = f"emp-{str(n).zfill(6)}"

                # Estado
                if n > 4 and n % 40 == 0:
                    estado = "CESADO"
                    activo = False
                elif n % 22 == 0:
                    estado = "VACACIONES"
                    activo = True
                else:
                    estado = "ACTIVO"
                    activo = True

                # Jefe jerárquico
                jefe_id = f"emp-{str((n - 2) // 8 + 1).zfill(6)}" if n >= 2 else None

                # Item Usuario
                usr_item = {
                    "tenant_id": tenant,
                    "user_id": user_id,
                    "email": email,
                    "empleado_id": emp_id,
                    "rol": rol,
                    "activo": activo,
                    "password_hash": PASSWORD_HASH_DEMO,
                    "created_at": ahora_iso
                }
                b_usr.put_item(Item=usr_item)

                # Item Empleado
                emp_item = {
                    "tenant_id": tenant,
                    "empleado_id": emp_id,
                    "user_id": user_id,
                    "nombres": nombre,
                    "apellidos": apellidos,
                    "email": email,
                    "documento": f"DNI{str(10000000 + n)}",
                    "area": area,
                    "cargo": cargo,
                    "estado": estado,
                    "salario_base": Decimal(str(2500 + (n % 40) * 150)),
                    "fecha_ingreso": (datetime.now(timezone.utc) - timedelta(days=random.randint(100, 1000))).strftime("%Y-%m-%d"),
                    "created_at": ahora_iso
                }
                if jefe_id:
                    emp_item["jefe_id"] = jefe_id
                b_emp.put_item(Item=emp_item)

        print(f"    ✓ {count_per_tenant} usuarios y empleados cargados en {time.time()-t0:.1f}s")


def seed_reclutamiento(tbl_rec, tenants, count_per_tenant):
    print(f"\n💼 3. Cargando Reclutamiento ({count_per_tenant} por tenant)...")
    estados_post = ["RECIBIDO", "ENTREVISTA", "OFERTA", "CONTRATADO", "RECHAZADO"]

    for tenant in tenants:
        t0 = time.time()
        print(f"  🏢 Tenant: [{tenant}]")
        vacantes = []

        # Vacantes (~150)
        num_vacantes = max(10, count_per_tenant // 70)
        with tbl_rec.batch_writer() as b:
            for v_idx in range(1, num_vacantes + 1):
                vac_id = f"vac-{tenant[:3]}-{str(v_idx).zfill(4)}"
                area = AREAS[v_idx % len(AREAS)]
                cargo = CARGOS[area][v_idx % len(CARGOS[area])]
                b.put_item(Item={
                    "tenant_id": tenant,
                    "sk": f"VACANTE#{vac_id}",
                    "vacante_id": vac_id,
                    "titulo": cargo,
                    "area": area,
                    "estado": "ABIERTA" if v_idx % 4 != 0 else "CERRADA",
                    "fecha_publicacion": rand_date(90)
                })
                vacantes.append(vac_id)

        # Postulaciones y Onboarding (mitad y mitad del count)
        mitad = count_per_tenant // 2
        with tbl_rec.batch_writer() as b:
            for p_idx in range(1, mitad + 1):
                pos_id = f"pos-{str(p_idx).zfill(6)}"
                cand_nom = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}"
                v_sel = random.choice(vacantes)
                est = random.choices(estados_post, weights=[30, 25, 15, 10, 20])[0]

                b.put_item(Item={
                    "tenant_id": tenant,
                    "sk": f"POSTULACION#{pos_id}",
                    "postulacion_id": pos_id,
                    "vacante_id": v_sel,
                    "nombre": cand_nom,
                    "email": f"{norm_ascii(cand_nom).replace(' ', '.')}@gmail.com",
                    "cv_s3_key": f"{tenant}/cvs/{pos_id}.pdf",
                    "estado": est,
                    "fecha": rand_date(60)
                })

            for o_idx in range(1, mitad + 1):
                emp_id = f"emp-{str(random.randint(1, min(count_per_tenant, 500))).zfill(6)}"
                onb_id = f"onb-{str(o_idx).zfill(6)}"
                b.put_item(Item={
                    "tenant_id": tenant,
                    "sk": f"ONBOARDING#{emp_id}#{onb_id}",
                    "onboarding_id": onb_id,
                    "empleado_id": emp_id,
                    "tarea": random.choice(TAREAS_ONBOARDING),
                    "completada": random.random() < 0.65,
                    "fecha_creacion": rand_date(30)
                })

        print(f"    ✓ {num_vacantes + mitad*2} registros en reclutamiento cargados en {time.time()-t0:.1f}s")


def seed_desempeno(tbl_des, tenants, count_per_tenant):
    print(f"\n⭐ 4. Cargando Desempeño ({count_per_tenant} por tenant)...")
    eval_count = int(count_per_tenant * 0.7)
    rec_count = count_per_tenant - eval_count

    for tenant in tenants:
        t0 = time.time()
        print(f"  🏢 Tenant: [{tenant}]")

        with tbl_des.batch_writer() as b:
            # Evaluaciones
            for e_idx in range(1, eval_count + 1):
                eva_id = f"eva-{str(e_idx).zfill(6)}"
                emp_id = f"emp-{str(random.randint(1, min(count_per_tenant, 500))).zfill(6)}"
                evaluador_id = f"emp-{str(random.randint(1, 10)).zfill(6)}"

                comps = [
                    {"nombre": c, "puntaje": Decimal(str(random.randint(3, 5)))}
                    for c in random.sample(COMPETENCIAS, k=random.randint(2, 4))
                ]
                b.put_item(Item={
                    "tenant_id": tenant,
                    "sk": eva_id,
                    "evaluacion_id": eva_id,
                    "empleado_id": emp_id,
                    "evaluador_id": evaluador_id,
                    "periodo": random.choice(["2026-S1", "2026-S2"]),
                    "puntaje": Decimal(str(round(random.uniform(3.0, 5.0), 1))),
                    "competencias": comps,
                    "comentarios": "Cumplimiento satisfactorio de metas establecidas.",
                    "estado": random.choice(["COMPLETADA", "COMPLETADA", "EN_PROGRESO"]),
                    "fecha_creacion": rand_date(120)
                })

            # Reconocimientos
            for r_idx in range(1, rec_count + 1):
                rec_id = f"rec-{str(r_idx).zfill(6)}"
                de_emp = f"emp-{str(random.randint(1, min(count_per_tenant, 500))).zfill(6)}"
                para_emp = f"emp-{str(random.randint(1, min(count_per_tenant, 500))).zfill(6)}"

                b.put_item(Item={
                    "tenant_id": tenant,
                    "sk": rec_id,
                    "reconocimiento_id": rec_id,
                    "empleado_id": para_emp,
                    "de_empleado_id": de_emp,
                    "mensaje": random.choice(RECONOCIMIENTOS),
                    "fecha": rand_date(60)
                })

        print(f"    ✓ {eval_count + rec_count} registros en desempeño cargados en {time.time()-t0:.1f}s")


def seed_notificaciones(tbl_not, tenants, count_per_tenant):
    print(f"\n🔔 5. Cargando Notificaciones ({count_per_tenant} por tenant)...")
    ahora = datetime.now(timezone.utc)

    for tenant in tenants:
        t0 = time.time()
        print(f"  🏢 Tenant: [{tenant}]")

        with tbl_not.batch_writer() as b:
            for n in range(1, count_per_tenant + 1):
                not_id = f"not-{tenant[:3]}-{str(n).zfill(6)}"
                user_id = f"usr-{str(random.randint(1, min(count_per_tenant, 500))).zfill(6)}"
                tipo, mensaje = random.choice(TIPOS_NOTIFICACION)
                dias_atras = random.randint(0, 180)

                b.put_item(Item={
                    "tenant_id": tenant,
                    "notificacion_id": not_id,
                    "destinatario_id": user_id,
                    "tipo": tipo,
                    "mensaje": mensaje,
                    "leida": random.random() < 0.4,
                    "created_at": (ahora - timedelta(days=dias_atras, minutes=random.randint(0, 1440))).isoformat()
                })

        print(f"    ✓ {count_per_tenant} notificaciones cargadas en {time.time()-t0:.1f}s")


# ==============================================================================
# MAIN RUNNER
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Seed Maestro HCM (>= 30k registros por servicio)")
    parser.add_argument("--stage", default="dev", help="Stage de despliegue (default: dev)")
    parser.add_argument("--count", type=int, default=10000, help="Registros por tenant (default: 10000 -> 30,000 en total)")
    parser.add_argument("--tenants", nargs="+", default=DEFAULT_TENANTS, help="Tenants a poblar")
    parser.add_argument("--create-tables", action="store_true", help="Crea las tablas DynamoDB si no existen en la cuenta")
    parser.add_argument("--services", nargs="+", default=["all"], help="Servicios: all, usuarios, empleados, reclutamiento, desempeno, notificaciones")
    args = parser.parse_args()

    print("=" * 70)
    print("🚀 SEED MAESTRO HCM — CARGA MASIVA MULTI-TENANT (>= 30,000 POR SERVICIO)")
    print(f"   Stage:   {args.stage}")
    print(f"   Tenants: {args.tenants} (x{args.count} por tenant = {args.count * len(args.tenants)} por servicio)")
    print(f"   Región:  us-east-1")
    print("=" * 70)

    ddb_client = boto3.client("dynamodb", region_name="us-east-1")
    ddb_resource = boto3.resource("dynamodb", region_name="us-east-1")

    tables_map = resolver_nombres_tablas(args.stage)

    if args.create_tables:
        crear_tablas_si_no_existen(ddb_client, ddb_resource, tables_map)

    # Tablas referenciadas
    t_usr = obtener_referencia_tabla(ddb_resource, ddb_client, "hcm-usuarios", tables_map["usuarios"])
    t_emp = obtener_referencia_tabla(ddb_resource, ddb_client, "hcm-empleados", tables_map["empleados"])
    t_rec = obtener_referencia_tabla(ddb_resource, ddb_client, "hcm-reclutamiento", tables_map["reclutamiento"])
    t_des = obtener_referencia_tabla(ddb_resource, ddb_client, "hcm-desempeno", tables_map["desempeno"])
    t_not = obtener_referencia_tabla(ddb_resource, ddb_client, "hcm-notificaciones", tables_map["notificaciones"])

    servicios = set(args.services)
    t_inicio = time.time()

    if "all" in servicios or "usuarios" in servicios or "empleados" in servicios:
        seed_usuarios_y_empleados(t_usr, t_emp, args.tenants, args.count)

    if "all" in servicios or "reclutamiento" in servicios:
        seed_reclutamiento(t_rec, args.tenants, args.count)

    if "all" in servicios or "desempeno" in servicios:
        seed_desempeno(t_des, args.tenants, args.count)

    if "all" in servicios or "notificaciones" in servicios:
        seed_notificaciones(t_not, args.tenants, args.count)

    print("\n" + "=" * 70)
    print(f"🎉 CARGA MASIVA FINALIZADA CON ÉXITO EN {time.time() - t_inicio:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()

