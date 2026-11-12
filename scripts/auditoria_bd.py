#!/usr/bin/env python3
"""
Auditoría de Base de Datos y Métricas de Carga (Grupo 2 · SaaS HCM)

Escanea las tablas DynamoDB del sistema y calcula:
  - Total de registros por microservicio.
  - Distribución por tenant (andina, pacifico, sierra).
  - Verificación del cumplimiento del requisito de la rúbrica (>= 30,000 registros).
  - Exportación automática a Markdown en docs/metricas_bd.md para el informe final.

Uso:
  python scripts/auditoria_bd.py
  python scripts/auditoria_bd.py --stage dev
"""
import argparse
import os
import time
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

DEFAULT_TENANTS = ["andina", "pacifico", "sierra"]


def auditar_tabla(tabla, nombre_servicio):
    print(f"  🔍 Analizando {nombre_servicio} ({tabla.name})...")
    total = 0
    por_tenant = {t: 0 for t in DEFAULT_TENANTS}
    otros_tenants = 0

    try:
        resp = tabla.scan(ProjectionExpression="tenant_id")
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
                ExclusiveStartKey=resp["LastEvaluatedKey"]
            )
        return {
            "servicio": nombre_servicio,
            "tabla": tabla.name,
            "total": total,
            "por_tenant": por_tenant,
            "otros": otros_tenants,
            "cumple_rubrica": total >= 30000,
            "error": None
        }
    except ClientError as e:
        code = e.response["Error"]["Code"]
        return {
            "servicio": nombre_servicio,
            "tabla": tabla.name,
            "total": 0,
            "por_tenant": por_tenant,
            "otros": 0,
            "cumple_rubrica": False,
            "error": code
        }


def generar_reporte_markdown(resultados, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fecha_reporte = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    md = []
    md.append("# Reporte de Auditoría de Base de Datos — SaaS HCM")
    md.append(f"**Fecha de ejecución:** `{fecha_reporte}`")
    md.append(f"**Requisito de Rúbrica:** $\\ge 30,000$ registros por microservicio en 3 tenants.\n")
    md.append("---")
    md.append("\n## 1. Resumen de Registros por Microservicio\n")
    md.append("| Microservicio | Nombre de Tabla DynamoDB | Total Registros | Andina | Pacífico | Sierra | Cumple Rúbrica ( $\\ge$ 30k ) |")
    md.append("|---|---|---|---|---|---|:---:|")

    total_general = 0
    cumple_todos = True

    for r in resultados:
        if r["error"]:
            md.append(f"| **{r['servicio']}** | `{r['tabla']}` | *No existe ({r['error']})* | - | - | - | ❌ |")
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

        md.append(f"| **{r['servicio']}** | `{r['tabla']}` | {total_str} | {andina} | {pacifico} | {sierra} | {badge} |")

    md.append(f"\n**Total Global de Registros en DynamoDB:** `{total_general:,}` registros.")
    md.append(f"**Estado General del Requisito:** {'✅ **APROBADO PARA ENTREGA**' if cumple_todos else '⏳ **FALTAN REGISTROS POR COMPLETAR**'}\n")

    md.append("---\n")
    md.append("## 2. Aislamiento por Tenant")
    md.append("Cada registro almacena como clave de partición (`HASH`) el atributo `tenant_id`.")
    md.append("Se cuentan los registros por tenant. Este conteo no demuestra aislamiento de acceso; eso se verifica con pruebas HTTP entre tenants.\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n📄 Reporte Markdown guardado en: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Auditoría de tablas DynamoDB HCM")
    parser.add_argument("--stage", default="dev", help="Stage de las tablas (default: dev)")
    parser.add_argument("--output", default="docs/metricas_bd.md", help="Ruta del reporte Markdown generado")
    args = parser.parse_args()

    print("=" * 70)
    print("📊 AUDITORÍA DE BASE DE DATOS — MÉTRICAS DE VOLUMEN (GRUPO 2 · SAAS HCM)")
    print(f"   Stage:   {args.stage}")
    print(f"   Región:  us-east-1")
    print("=" * 70)

    ddb_resource = boto3.resource("dynamodb", region_name="us-east-1")
    ddb_client = boto3.client("dynamodb", region_name="us-east-1")
    existentes = ddb_client.list_tables().get("TableNames", [])

    def resolver_tabla(base, stage_name):
        if stage_name in existentes:
            return ddb_resource.Table(stage_name)
        if base in existentes:
            return ddb_resource.Table(base)
        return ddb_resource.Table(stage_name)

    tablas = [
        ("ms-usuarios", resolver_tabla("hcm-usuarios", f"hcm-usuarios-{args.stage}")),
        ("ms-empleados", resolver_tabla("hcm-empleados", f"hcm-empleados-{args.stage}")),
        ("ms-reclutamiento", resolver_tabla("hcm-reclutamiento", f"hcm-reclutamiento-{args.stage}")),
        ("ms-desempeno", resolver_tabla("hcm-desempeno", f"hcm-desempeno-{args.stage}")),
        ("ms-notificaciones", resolver_tabla("hcm-notificaciones", f"hcm-notificaciones-{args.stage}")),
        ("ms-nominas", resolver_tabla("hcm-nominas", f"hcm-nominas-{args.stage}")),
        ("ms-asistencia", resolver_tabla("hcm-asistencia", f"hcm-asistencia-{args.stage}")),
    ]

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
            print(f"{r['servicio']:<18} | {r['tabla']:<24} | {'0':<10} | ❌ NO EXISTE")
        else:
            estado = "✅ >= 30,000" if r["cumple_rubrica"] else "⚠️ < 30,000"
            print(f"{r['servicio']:<18} | {r['tabla']:<24} | {r['total']:<10} | {estado}")
    print("=" * 70)
    print(f"Auditoría completada en {time.time()-t0:.1f}s")

    generar_reporte_markdown(resultados, args.output)


if __name__ == "__main__":
    main()
