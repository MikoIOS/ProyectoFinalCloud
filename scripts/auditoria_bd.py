#!/usr/bin/env python3
"""
Auditoría de Base de Datos y Métricas de Carga (Grupo 2 · SaaS HCM)

Escanea las tablas DynamoDB del sistema y calcula:
  - Total de registros por microservicio.
  - Distribución por tenant (andina, pacifico, sierra).
  - Verificación del cumplimiento del requisito de la rúbrica (>= 30,000 registros).
  - Exportación automática a Markdown en docs/metricas_bd_<stage>.md para el informe final.

Uso:
  python scripts/auditoria_bd.py
  python scripts/auditoria_bd.py --stage dev
"""
import argparse
import time
from pathlib import Path
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

DEFAULT_TENANTS = ["andina", "pacifico", "sierra"]


PROD_TABLES = {
    "usuarios": "hcm-usuarios", "empleados": "hcm-empleados",
    "reclutamiento": "hcm-reclutamiento-dev", "desempeno": "hcm-desempeno-dev",
    "notificaciones": "hcm-notificaciones-dev", "nominas": "hcm-nominas-dev",
    "asistencia": "hcm-asistencia-dev",
}


def tablas_por_stage(stage):
    if stage not in ("dev", "prod"):
        raise ValueError("Stage debe ser dev o prod")
    return {"ms-" + modulo: ("hcm-dev-" + modulo if stage == "dev" else tabla)
            for modulo, tabla in PROD_TABLES.items()}


def auditar_tabla(tabla, nombre_servicio):
    print(f"  🔍 Analizando {nombre_servicio} ({tabla.name})...")
    total = 0
    por_tenant = {t: 0 for t in DEFAULT_TENANTS}
    otros_tenants = 0

    try:
        resp = tabla.scan(ProjectionExpression="tenant_id", ConsistentRead=True)
        while True:
            for item in resp.get("Items", []):
                t = item.get("tenant_id", "desconocido")
                if t in por_tenant:
                    por_tenant[t] += 1
                else:
                    otros_tenants += 1
                total += 1

            if "LastEvaluatedKey" not in resp:
                break
            resp = tabla.scan(
                ProjectionExpression="tenant_id",
                ConsistentRead=True,
                ExclusiveStartKey=resp["LastEvaluatedKey"]
            )
        return {
            "servicio": nombre_servicio,
            "tabla": tabla.name,
            "total": total,
            "por_tenant": por_tenant,
            "otros": otros_tenants,
            "cumple_rubrica": sum(por_tenant.values()) >= 30000 and all(por_tenant.values()),
            "error": None
        }
    except (ClientError, BotoCoreError) as e:
        code = e.response["Error"]["Code"] if isinstance(e, ClientError) else type(e).__name__
        return {
            "servicio": nombre_servicio,
            "tabla": tabla.name,
            "total": 0,
            "por_tenant": por_tenant,
            "otros": 0,
            "cumple_rubrica": False,
            "error": code
        }


def generar_reporte_markdown(resultados, output_path, stage="prod"):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fecha_reporte = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    md = []
    md.append("# Reporte de Auditoría de Base de Datos — SaaS HCM")
    md.append(f"**Entorno auditado:** `{stage}` (sin fallback a otro entorno)")
    md.append("Conteo consistente por página; no es una instantánea transaccional entre tablas. Evitar escrituras durante la auditoría.")
    md.append(f"**Fecha de ejecución:** `{fecha_reporte}`")
    md.append(f"**Requisito de Rúbrica:** $\\ge 30,000$ registros por microservicio en 3 tenants.\n")
    md.append("---")
    md.append("\n## 1. Resumen de Registros por Microservicio\n")
    md.append("| Microservicio | Nombre de Tabla DynamoDB | Total Registros | Andina | Pacífico | Sierra | Otros | Cumple Rúbrica ( $\\ge$ 30k ) |")
    md.append("|---|---|---|---|---|---|---|:---:|")

    total_general = 0
    cumple_todos = len(resultados) == len(PROD_TABLES)

    for r in resultados:
        if r["error"]:
            md.append(f"| **{r['servicio']}** | `{r['tabla']}` | *Error ({r['error']})* | - | - | - | - | ❌ |")
            cumple_todos = False
            continue

        total_general += r["total"]
        if not r["cumple_rubrica"]:
            cumple_todos = False

        badge = "✅ CUMPLE" if r["cumple_rubrica"] else "⚠️ EN PROGRESO"
        andina = f"{r['por_tenant'].get('andina', 0):,}"
        pacifico = f"{r['por_tenant'].get('pacifico', 0):,}"
        sierra = f"{r['por_tenant'].get('sierra', 0):,}"
        total_str = f"**{r['total']:,}**"

        md.append(f"| **{r['servicio']}** | `{r['tabla']}` | {total_str} | {andina} | {pacifico} | {sierra} | {r['otros']:,} | {badge} |")

    md.append(f"\n**Total Global de Registros en DynamoDB:** `{total_general:,}` registros.")
    md.append(f"**Estado General del Requisito:** {'✅ **VOLUMEN VERIFICADO EN ESTE ENTORNO**' if cumple_todos else '⚠️ **VOLUMEN NO ACREDITADO EN TODAS LAS TABLAS**'}\n")

    md.append("\nEl cumplimiento exige ≥30.000 ítems sumados entre Andina, Pacífico y Sierra y presencia de los tres; otros tenants no sustituyen esa distribución. Incluye entidades y registros de control, no solo empleados.\n")
    md.append("---\n")
    md.append("## 2. Aislamiento por Tenant")
    md.append("Cada registro almacena como clave de partición (`HASH`) el atributo `tenant_id`.")
    md.append("Se cuentan los registros por tenant. Este conteo no demuestra aislamiento de acceso; eso se verifica con pruebas HTTP entre tenants.\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n📄 Reporte Markdown guardado en: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Auditoría de tablas DynamoDB HCM")
    parser.add_argument("--stage", choices=("dev", "prod"), default="dev", help="Entorno exacto (default: dev)")
    parser.add_argument("--output", default=None, help="Ruta del reporte; por defecto docs/metricas_bd_<stage>.md")
    args = parser.parse_args()

    print("=" * 70)
    print("📊 AUDITORÍA DE BASE DE DATOS — MÉTRICAS DE VOLUMEN (GRUPO 2 · SAAS HCM)")
    print(f"   Stage:   {args.stage}")
    print(f"   Región:  us-east-1")
    print("=" * 70)

    config = Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 1})
    ddb_resource = boto3.resource("dynamodb", region_name="us-east-1", config=config)
    tablas = [(servicio, ddb_resource.Table(nombre))
              for servicio, nombre in tablas_por_stage(args.stage).items()]

    t0 = time.time()
    resultados = []
    for servicio, tabla in tablas:
        res = auditar_tabla(tabla, servicio)
        resultados.append(res)

    print("\n" + "=" * 70)
    print(f"{'MICROSERVICIO':<18} | {'TABLA':<24} | {'TOTAL':<10} | {'ESTADO':<12}")
    print("-" * 70)
    for r in resultados:
        if r["error"]:
            print(f"{r['servicio']:<18} | {r['tabla']:<24} | {'0':<10} | ❌ {r['error']}")
        else:
            estado = "✅ >= 30,000" if r["cumple_rubrica"] else "⚠️ VOLUMEN/DISTRIBUCIÓN"
            print(f"{r['servicio']:<18} | {r['tabla']:<24} | {r['total']:<10} | {estado}")
    print("=" * 70)
    print(f"Auditoría completada en {time.time()-t0:.1f}s")

    generar_reporte_markdown(resultados, args.output or f"docs/metricas_bd_{args.stage}.md", args.stage)
    return 0 if all(r["cumple_rubrica"] for r in resultados) else 1


if __name__ == "__main__":
    raise SystemExit(main())
