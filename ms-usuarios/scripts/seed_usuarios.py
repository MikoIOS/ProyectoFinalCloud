"""Carga usuarios ficticios: 10 000 por tenant (30 000 en total).

Convención (la misma que usará seed_empleados.py de ms-empleados):
  n = 1..10000 por tenant  ->  user_id = usr-{n:06d}, empleado_id = emp-{n:06d}
  cuentas de demo (una por rol, mismo correo en cada tenant):
    n=1 admin@<tenant>.pe (admin_rrhh) | n=2 empleado@<tenant>.pe | n=3 gerente@<tenant>.pe | n=4 reclutador@<tenant>.pe
  n % 500 == 0       -> gerente
  n % 250 == 0       -> reclutador (si no es gerente)
  n % 40 == 0        -> usuario desactivado (empleado CESADO), n > 4
  resto              -> empleado
Todos usan la misma clave de demo; el hash se calcula UNA vez (scrypt/bcrypt son lentos a propósito).

Uso:
  python -m scripts.seed_usuarios                       # los 3 tenants, tabla hcm-usuarios en AWS
  python -m scripts.seed_usuarios --tenant andina --count 100
  python -m scripts.seed_usuarios --endpoint-url http://localhost:8000 --create-table
"""
import argparse
import random
import unicodedata
from datetime import datetime, timezone

import boto3

from scripts.tabla import crear_tabla
from src.common.security import hash_password

TENANTS = ["andina", "pacifico", "sierra"]
PASSWORD_DEMO = "Demo1234!"

NOMBRES = ["María", "José", "Luis", "Carmen", "Juan", "Rosa", "Carlos", "Ana", "Miguel", "Lucía",
           "Jorge", "Elena", "Pedro", "Sofía", "Diego", "Valeria", "Andrés", "Camila", "Javier", "Paula",
           "Fernando", "Daniela", "Ricardo", "Fiorella", "Renzo", "Milagros", "Sebastián", "Gabriela"]
APELLIDOS = ["Quispe", "Huamán", "Flores", "Rojas", "Mendoza", "Vargas", "Castillo", "Torres", "Ramos", "Chávez",
             "Salazar", "Paredes", "Gutiérrez", "Cárdenas", "Ríos", "Vega", "Soto", "Ortiz", "Silva", "Peña",
             "Delgado", "Cruz", "Medina", "Campos", "Aguilar", "Espinoza", "Villanueva", "Palomino"]


def ascii_min(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


DEMO = {1: ("admin", "admin_rrhh", "Administrador RR. HH."),
        2: ("empleado", "empleado", "Empleado Demo"),
        3: ("gerente", "gerente", "Gerente Demo"),
        4: ("reclutador", "reclutador", "Reclutador Demo")}


def rol_de(n):
    if n in DEMO:
        return DEMO[n][1]
    if n % 500 == 0:
        return "gerente"
    if n % 250 == 0:
        return "reclutador"
    return "empleado"


def construir(tenant, n, pwd_hash, rng, ahora):
    nombre = rng.choice(NOMBRES)
    apellido = rng.choice(APELLIDOS)
    if n in DEMO:
        email, nombre_completo = "%s@%s.pe" % (DEMO[n][0], tenant), DEMO[n][2]
    else:
        email = "%s.%s%d@%s.pe" % (ascii_min(nombre), ascii_min(apellido), n, tenant)
        nombre_completo = "%s %s" % (nombre, apellido)
    return {
        "tenant_id": tenant,
        "user_id": "usr-%06d" % n,
        "email": email,
        "password_hash": pwd_hash,
        "nombre": nombre_completo,
        "rol": rol_de(n),
        "activo": not (n > 4 and n % 40 == 0),
        "empleado_id": "emp-%06d" % n,
        "debe_cambiar_password": False,
        "created_at": ahora,
        "updated_at": ahora,
    }


def sembrar(tabla, tenants, count, pwd_hash, log=print):
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total = 0
    for tenant in tenants:
        rng = random.Random(tenant)  # reproducible
        with tabla.batch_writer() as batch:
            for n in range(1, count + 1):
                batch.put_item(Item=construir(tenant, n, pwd_hash, rng, ahora))
                total += 1
                if n % 2000 == 0:
                    log("  %s: %d/%d" % (tenant, n, count))
        log("%s listo (%d usuarios)" % (tenant, count))
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", choices=TENANTS, help="un solo tenant (por defecto los 3)")
    ap.add_argument("--count", type=int, default=10000, help="usuarios por tenant")
    ap.add_argument("--table", default="hcm-usuarios")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--endpoint-url", help="DynamoDB local (por defecto AWS)")
    ap.add_argument("--create-table", action="store_true", help="crear la tabla (solo para DynamoDB local)")
    args = ap.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=args.region, endpoint_url=args.endpoint_url)
    tabla = crear_tabla(dynamodb, args.table) if args.create_table else dynamodb.Table(args.table)

    pwd_hash = hash_password(PASSWORD_DEMO)
    total = sembrar(tabla, [args.tenant] if args.tenant else TENANTS, args.count, pwd_hash)
    print("Total: %d usuarios. Clave de demo: %s | cuentas: admin|empleado|gerente|reclutador@<tenant>.pe" % (total, PASSWORD_DEMO))


if __name__ == "__main__":
    main()
