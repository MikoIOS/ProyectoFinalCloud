#!/usr/bin/env python3
"""Siembra hcm-nominas-dev con una planilla GENERADA por tenant.

Uso:
  TABLE_NAME=hcm-nominas-dev TABLE_EMPLEADOS=hcm-empleados \
    python3 scripts/seed_nominas.py --periodo 2026-11

No publica eventos: es una carga masiva para cumplir la rúbrica de >=30k registros.
"""
import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.common.dates import dinero  # noqa: E402
from src.repositories import nominas_repo as repo  # noqa: E402
from src.services import calculo  # noqa: E402

TENANTS = ("andina", "pacifico", "sierra")


def _ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _planilla(tenant, periodo, nominas):
    total_bruto = sum((n["sueldo_base"] + n["bonos"] for n in nominas), Decimal("0"))
    total_desc = sum((n["descuentos"] for n in nominas), Decimal("0"))
    total_neto = sum((n["neto"] for n in nominas), Decimal("0"))
    total_essalud = sum((n["aporte_essalud"] for n in nominas), Decimal("0"))
    item = {
        "tenant_id": tenant,
        "sk": "PLANILLA#" + periodo,
        "tipo": "PLANILLA",
        "planilla_id": "pla-" + periodo,
        "periodo_planilla": periodo,
        "periodo": periodo,
        "estado": "GENERADA",
        "ejecucion_id": "seed-" + periodo,
        "total_empleados": len(nominas),
        "procesados": len(nominas),
        "total_bruto": dinero(total_bruto),
        "total_descuentos": dinero(total_desc),
        "total_neto": dinero(total_neto),
        "total_essalud": dinero(total_essalud),
        "iniciado_en": _ahora(),
        "completado_en": _ahora(),
        "mensaje_error": None,
        "solicitado_por": "seed",
        "notificar": False,
        "actualizado_en": _ahora(),
    }
    repo.put_planilla(item)
    return item


def _bandas(tenant, empleados):
    rangos = defaultdict(lambda: [None, None])
    for e in empleados:
        cargo = e.get("cargo")
        salario = e.get("salario_base")
        if not cargo or salario is None:
            continue
        salario = Decimal(str(salario))
        rango = rangos[cargo]
        rango[0] = salario if rango[0] is None or salario < rango[0] else rango[0]
        rango[1] = salario if rango[1] is None or salario > rango[1] else rango[1]
    for cargo, (minimo, maximo) in rangos.items():
        repo.put_banda({
            "tenant_id": tenant,
            "sk": "BANDA#" + cargo,
            "tipo": "BANDA",
            "banda_cargo": cargo,
            "cargo": cargo,
            "minimo": dinero(minimo),
            "maximo": dinero(maximo),
            "moneda": "PEN",
            "actualizado_en": _ahora(),
        })
    return len(rangos)


def _conceptos(tenant, periodo, nominas, cantidad=500):
    """Conceptos de muestra para superar holgadamente los 30k registros de la tabla."""
    items = []
    for i, n in enumerate(nominas[:cantidad]):
        cid = "seed-%s-%s-%s" % (tenant, periodo, n["empleado_id"])
        items.append({
            "tenant_id": tenant,
            "sk": "CONCEPTO#" + cid,
            "tipo": "CONCEPTO",
            "concepto_id": cid,
            "empleado_id": n["empleado_id"],
            "periodo": periodo,
            "periodo_concepto": "%s#%s" % (periodo, cid),
            "tipo_concepto": "BONO",
            "concepto": "Bono de productividad (seed)",
            "monto": dinero(150 + (i % 10) * 25),
            "origen": "MANUAL",
            "creado_por": "seed",
            "creado_en": _ahora(),
        })
    repo.batch_put_conceptos(items)
    return len(items)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--periodo", default=datetime.now(timezone.utc).strftime("%Y-%m"))
    parser.add_argument("--tenant", choices=TENANTS, action="append")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("TABLE_EMPLEADOS", "hcm-empleados")
    os.environ.setdefault("TABLE_NAME", "hcm-nominas-dev")
    os.environ.setdefault("AWS_REGION", "us-east-1")

    tenants = args.tenant or list(TENANTS)
    total = 0
    for tenant in tenants:
        empleados = repo.listar_empleados(tenant)
        nominas = []
        for e in empleados:
            n = calculo.calcular(e, args.periodo, [])
            if n:
                nominas.append(n)
        if args.dry_run:
            print("%s: %d empleados, %d nóminas, 500 conceptos (dry-run)"
                  % (tenant, len(empleados), len(nominas)))
            total += len(nominas) + 500
            continue
        repo.batch_put_nominas(nominas)
        p = _planilla(tenant, args.periodo, nominas)
        b = _bandas(tenant, empleados)
        c = _conceptos(tenant, args.periodo, nominas)
        total += len(nominas) + c
        print("%s: %d nóminas, %d conceptos, %d bandas, planilla %s (%s)"
              % (tenant, len(nominas), c, b, p["periodo"], p["estado"]))
    print("Total nóminas sembradas: %d" % total)


if __name__ == "__main__":
    main()
