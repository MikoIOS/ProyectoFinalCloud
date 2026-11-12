"""Utilidades de fechas y dinero compartidas por el cálculo de nómina."""
import calendar
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from src.common.errors import Validacion

PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
CENTAVOS = Decimal("0.01")
SEIS_DECIMALES = Decimal("0.000001")


def periodo_valido(valor):
    if not isinstance(valor, str) or not PERIODO_RE.match(valor):
        raise Validacion("periodo debe tener formato YYYY-MM")
    anio, mes = (int(x) for x in valor.split("-"))
    if anio < 2000 or anio > 2100:
        raise Validacion("periodo fuera de rango")
    return valor


def mes_actual():
    hoy = date.today()
    return "%04d-%02d" % (hoy.year, hoy.month)


def fecha(valor):
    if isinstance(valor, date):
        return valor
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def inicio_fin_mes(periodo):
    anio, mes = (int(x) for x in periodo.split("-"))
    return date(anio, mes, 1), date(anio, mes, calendar.monthrange(anio, mes)[1])


def dias_laborados(empleado, periodo):
    """Días del periodo, con mes comercial de 30 días. Réplica de CalculoNominaService."""
    inicio_mes, fin_mes = inicio_fin_mes(periodo)
    ingreso = fecha(empleado.get("fecha_ingreso"))
    cese = fecha(empleado.get("fecha_cese"))
    if empleado.get("estado") == "CESADO" and cese is None:
        return 0
    inicio = ingreso if ingreso and ingreso > inicio_mes else inicio_mes
    fin = cese if cese and cese < fin_mes else fin_mes
    if fin < inicio:
        return 0
    if inicio == inicio_mes and fin == fin_mes:
        return 30
    return min(30, fin.day - inicio.day + 1)


def dinero(valor):
    return Decimal(str(valor if valor is not None else 0)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def seis(valor):
    return Decimal(str(valor if valor is not None else 0)).quantize(SEIS_DECIMALES, rounding=ROUND_HALF_UP)


def meses_completos(desde, hasta):
    """Equivalente a ChronoUnit.MONTHS.between(desde, hasta)."""
    meses = (hasta.year - desde.year) * 12 + (hasta.month - desde.month)
    if hasta.day < desde.day:
        meses -= 1
    return max(0, meses)
