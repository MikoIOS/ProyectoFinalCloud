"""Liquidación referencial por cese (simplificada). Réplica de LiquidacionService."""
from datetime import date, datetime, timezone
from decimal import Decimal

from src.common.dates import dinero, fecha, meses_completos, seis
from src.repositories import nominas_repo as repo


def _corte_cts(cese):
    if cese.month >= 11:
        return date(cese.year, 11, 1)
    if cese.month >= 5:
        return date(cese.year, 5, 1)
    return date(cese.year - 1, 11, 1)


def _corte_grati(cese):
    if cese.month >= 7:
        return date(cese.year, 7, 1)
    return date(cese.year, 1, 1)


def _mismo_dia_otro_anio(fecha_base, anio):
    """Evita el fallo de date.replace() cuando el ingreso fue un 29 de febrero."""
    try:
        return fecha_base.replace(year=anio)
    except ValueError:
        return date(anio, 2, 28)


def calcular(empleado, cese, motivo):
    salario = Decimal(str(empleado.get("salario_base") or 0))
    if salario <= 0:
        return None
    ingreso = fecha(empleado.get("fecha_ingreso")) or cese.replace(month=1, day=1)

    aniversario = _mismo_dia_otro_anio(ingreso, cese.year)
    if aniversario > cese:
        aniversario = _mismo_dia_otro_anio(ingreso, cese.year - 1)
    if aniversario < ingreso:
        aniversario = ingreso
    meses_vac = meses_completos(aniversario, cese)

    corte_cts = _corte_cts(cese)
    if corte_cts < ingreso:
        corte_cts = ingreso
    meses_cts = meses_completos(corte_cts, cese)

    corte_grati = _corte_grati(cese)
    if corte_grati < ingreso:
        corte_grati = ingreso
    meses_grati = meses_completos(corte_grati, cese)

    doceavo = seis(salario / Decimal("12"))
    sexto = seis(salario / Decimal("6"))
    vacaciones = dinero(doceavo * meses_vac)
    cts = dinero(doceavo * meses_cts)
    grati = dinero(sexto * meses_grati)
    total = dinero(vacaciones + cts + grati)

    item = {
        "tenant_id": empleado["tenant_id"],
        "sk": "LIQUIDACION#" + empleado["empleado_id"],
        "tipo": "LIQUIDACION",
        "empleado_id": empleado["empleado_id"],
        "empleado_periodo": "%s#LIQ" % empleado["empleado_id"],
        "fecha_cese": cese.isoformat(),
        "motivo": motivo or "",
        "vacaciones_truncas": vacaciones,
        "cts_trunca": cts,
        "gratificacion_trunca": grati,
        "total": total,
        "calculado_en": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    repo.put_liquidacion(item)
    return item


def obtener(ctx, empleado_id):
    from src.common.auth import propio_o_supervisor
    from src.common.errors import NoEncontrado

    propio_o_supervisor(ctx, empleado_id, "Solo puedes ver tu propia liquidación")
    item = repo.get_liquidacion(ctx.tenant_id, empleado_id)
    if not item:
        raise NoEncontrado("No hay liquidación para el empleado %s" % empleado_id)
    return {
        "empleado_id": item.get("empleado_id"),
        "fecha_cese": item.get("fecha_cese"),
        "motivo": item.get("motivo"),
        "vacaciones_truncas": item.get("vacaciones_truncas"),
        "cts_trunca": item.get("cts_trunca"),
        "gratificacion_trunca": item.get("gratificacion_trunca"),
        "total": item.get("total"),
        "calculado_en": item.get("calculado_en"),
    }
