"""Carga empleados ficticios: 10 000 por tenant (30 000 en total), coherentes con seed_usuarios.py de ms-usuarios.

Convención compartida (n = 1..10000 por tenant):
  empleado_id = emp-{n:06d}  <->  user_id = usr-{n:06d}; mismo email y mismo nombre completo.
  n = 1..4 -> cuentas de demo (admin, empleado, gerente, reclutador); n % 500 == 0 gerente; n % 250 == 0 reclutador.
  CESADO     si n > 4 y n % 40 == 0   (su usuario está desactivado en ms-usuarios)
  VACACIONES si n % 22 == 0 y no cesado (~4,5 %)
  Jerarquía: jefe de n (n >= 2) = (n - 2) // 8 + 1, saltando a jefes cesados -> árbol de ancho 8, sin ciclos.
Los nombres salen de la misma secuencia aleatoria que usa seed_usuarios.py (misma semilla y mismas listas).

Uso:
  python -m scripts.seed_empleados                       # los 3 tenants, tabla hcm-empleados en AWS
  python -m scripts.seed_empleados --tenant andina --count 100
  python -m scripts.seed_empleados --endpoint-url http://localhost:8000 --create-table
"""
import argparse
import random
import unicodedata
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import boto3

from scripts.tabla import crear_tabla

TENANTS = ["andina", "pacifico", "sierra"]

# --- DEBEN ser idénticas a las de ms-usuarios/scripts/seed_usuarios.py (misma secuencia aleatoria) ---
NOMBRES = ["María", "José", "Luis", "Carmen", "Juan", "Rosa", "Carlos", "Ana", "Miguel", "Lucía",
           "Jorge", "Elena", "Pedro", "Sofía", "Diego", "Valeria", "Andrés", "Camila", "Javier", "Paula",
           "Fernando", "Daniela", "Ricardo", "Fiorella", "Renzo", "Milagros", "Sebastián", "Gabriela"]
APELLIDOS = ["Quispe", "Huamán", "Flores", "Rojas", "Mendoza", "Vargas", "Castillo", "Torres", "Ramos", "Chávez",
             "Salazar", "Paredes", "Gutiérrez", "Cárdenas", "Ríos", "Vega", "Soto", "Ortiz", "Silva", "Peña",
             "Delgado", "Cruz", "Medina", "Campos", "Aguilar", "Espinoza", "Villanueva", "Palomino"]
DEMO = {1: ("admin", "admin_rrhh", "Administrador", "RR. HH.", "Recursos Humanos", "Jefe de RR. HH."),
        2: ("empleado", "empleado", "Empleado", "Demo", "Recursos Humanos", "Analista de Nóminas"),
        3: ("gerente", "gerente", "Gerente", "Demo", "Operaciones", "Gerente de Operaciones"),
        4: ("reclutador", "reclutador", "Reclutador", "Demo", "Recursos Humanos", "Reclutador")}
# ------------------------------------------------------------------------------------------------

CARGOS = {
    "Recursos Humanos": ["Analista de Nóminas", "Asistente de RR. HH.", "Especialista en Bienestar"],
    "Tecnología": ["Desarrollador Backend", "Desarrollador Frontend", "Analista de Datos"],
    "Ventas": ["Ejecutivo Comercial", "Asesor de Ventas", "Analista Comercial"],
    "Finanzas": ["Contador", "Analista Financiero", "Asistente Contable"],
    "Operaciones": ["Supervisor de Operaciones", "Analista de Procesos", "Coordinador de Planta"],
    "Marketing": ["Community Manager", "Analista de Marketing", "Diseñador Gráfico"],
    "Logística": ["Coordinador de Almacén", "Analista de Compras", "Operador Logístico"],
    "Legal": ["Abogado Corporativo", "Asistente Legal", "Analista de Cumplimiento"],
    "Atención al Cliente": ["Asesor de Servicio", "Supervisor de Call Center", "Analista de Calidad de Servicio"],
    "Calidad": ["Inspector de Calidad", "Analista de Calidad", "Auditor Interno"],
}
AREAS = list(CARGOS)


def ascii_min(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def rol_de(n):
    if n in DEMO:
        return DEMO[n][1]
    if n % 500 == 0:
        return "gerente"
    if n % 250 == 0:
        return "reclutador"
    return "empleado"


def es_cesado(n):
    return n > 4 and n % 40 == 0


def estado_de(n):
    if es_cesado(n):
        return "CESADO"
    return "VACACIONES" if n % 22 == 0 else "ACTIVO"


def jefe_de(n):
    if n == 1:
        return None
    m = (n - 2) // 8 + 1
    while es_cesado(m):
        m -= 1
    return m


def construir(tenant, idx_tenant, n, rng_nombres, rng, ahora):
    # 1) misma secuencia que seed_usuarios.py: SIEMPRE dos sorteos por n, en este orden
    nombre, apellido = rng_nombres.choice(NOMBRES), rng_nombres.choice(APELLIDOS)
    if n in DEMO:
        email = "%s@%s.pe" % (DEMO[n][0], tenant)
        nombres, apellidos, area, cargo = DEMO[n][2], DEMO[n][3], DEMO[n][4], DEMO[n][5]
    else:
        email = "%s.%s%d@%s.pe" % (ascii_min(nombre), ascii_min(apellido), n, tenant)
        nombres, apellidos = nombre, apellido
        area = rng.choice(AREAS)
        cargo = ("Gerente de %s" % area) if rol_de(n) == "gerente" else (
            "Reclutador" if rol_de(n) == "reclutador" else rng.choice(CARGOS[area]))
    ingreso = date(2015, 1, 1) + timedelta(days=rng.randint(0, 4200))          # hasta ~ago-2026
    salario = rng.uniform(8000, 15000) if rol_de(n) in ("gerente", "admin_rrhh") else rng.uniform(1500, 6500)
    item = {
        "tenant_id": tenant,
        "empleado_id": "emp-%06d" % n,
        "nombres": nombres,
        "apellidos": apellidos,
        "documento": "%08d" % (20000000 + n * 7919 + idx_tenant),          # único por tenant
        "email": email,
        "area": area,
        "cargo": cargo,
        "fecha_ingreso": ingreso.isoformat(),
        "salario_base": Decimal(str(round(salario, 2))),
        "telefono": "9%08d" % rng.randint(0, 99999999),
        "estado": estado_de(n),
        "created_at": ahora,
        "updated_at": ahora,
    }
    m = jefe_de(n)
    if m:
        item["jefe_id"] = "emp-%06d" % m
    if item["estado"] == "CESADO":
        item["fecha_cese"] = min(ingreso + timedelta(days=rng.randint(90, 2500)), date(2026, 10, 31)).isoformat()
    return item


def sembrar(tabla, tenants, count, log=print):
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total = 0
    for tenant in tenants:
        idx = TENANTS.index(tenant)
        rng_nombres, rng = random.Random(tenant), random.Random(tenant + "-empleados")
        with tabla.batch_writer() as batch:
            for n in range(1, count + 1):
                batch.put_item(Item=construir(tenant, idx, n, rng_nombres, rng, ahora))
                total += 1
                if n % 2000 == 0:
                    log("  %s: %d/%d" % (tenant, n, count))
        log("%s listo (%d empleados)" % (tenant, count))
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", choices=TENANTS, help="un solo tenant (por defecto los 3)")
    ap.add_argument("--count", type=int, default=10000, help="empleados por tenant")
    ap.add_argument("--table", default="hcm-empleados")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--endpoint-url", help="DynamoDB local (por defecto AWS)")
    ap.add_argument("--create-table", action="store_true", help="crear la tabla (solo para DynamoDB local)")
    args = ap.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=args.region, endpoint_url=args.endpoint_url)
    tabla = crear_tabla(dynamodb, args.table) if args.create_table else dynamodb.Table(args.table)
    total = sembrar(tabla, [args.tenant] if args.tenant else TENANTS, args.count)
    print("Total: %d empleados." % total)


if __name__ == "__main__":
    main()
