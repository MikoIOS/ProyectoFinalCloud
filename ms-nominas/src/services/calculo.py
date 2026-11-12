"""Cálculo de la boleta mensual (reglas simplificadas de planilla peruana).

Réplica de Backend_B/CalculoNominaService:
  sueldo_base = salario_mensual × días_laborados / 30
  sin_goce    = salario_mensual / 30 × días sin goce aprobados
  pensión     = (sueldo_base − sin_goce) × 13% (ONP)
  descuentos  = pensión + sin_goce + otros descuentos
  neto        = sueldo_base + bonos − descuentos (nunca negativo)
  EsSalud 9%  = aporte del empleador, informativo
"""
import os
from datetime import datetime, timezone
from decimal import Decimal

from src.common.dates import dinero, dias_laborados, seis

TREINTA = Decimal("30")
TASA_PENSION = Decimal(os.environ.get("TASA_PENSION", "0.13"))
TASA_ESSALUD = Decimal(os.environ.get("TASA_ESSALUD", "0.09"))


def _linea(tipo, concepto, monto):
    return {"tipo": tipo, "concepto": concepto, "monto": dinero(monto)}


def _porcentaje(tasa):
    valor = (tasa * 100).normalize()
    texto = format(valor, "f")
    return texto + "%"


def nomina_id(periodo, empleado_id):
    return "nom-%s-%s" % (periodo, empleado_id)


def calcular(empleado, periodo, conceptos):
    """Devuelve el item DynamoDB de la nómina, o None si no corresponde al periodo."""
    salario = Decimal(str(empleado.get("salario_base") or 0))
    dias = dias_laborados(empleado, periodo)
    if salario <= 0 or dias <= 0:
        return None

    valor_dia = seis(salario / TREINTA)
    sueldo = dinero(salario if dias == 30 else valor_dia * dias)

    detalle = [_linea("INGRESO", "Remuneración básica (%d días)" % dias, sueldo)]
    bonos = Decimal("0")
    otros_descuentos = Decimal("0")
    dias_sin_goce = 0

    for c in conceptos or []:
        tipo = c.get("tipo")
        monto = Decimal(str(c.get("monto") or 0))
        if tipo == "BONO":
            bonos += monto
            detalle.append(_linea("INGRESO", c.get("concepto", "Bono"), monto))
        elif tipo == "DESCUENTO":
            otros_descuentos += monto
            detalle.append(_linea("DESCUENTO", c.get("concepto", "Descuento"), monto))
        elif tipo == "SIN_GOCE":
            dias_sin_goce += int(c.get("dias") or 0)

    dias_sin_goce = min(dias_sin_goce, dias)
    sin_goce = dinero(valor_dia * dias_sin_goce)
    if sin_goce > sueldo:
        sin_goce = sueldo

    computable = sueldo - sin_goce
    pension = dinero(computable * TASA_PENSION)
    detalle.append(_linea("DESCUENTO", "Aporte pensión ONP (%s)" % _porcentaje(TASA_PENSION), pension))
    if dias_sin_goce > 0:
        detalle.append(_linea("DESCUENTO", "Ausencia sin goce (%d días)" % dias_sin_goce, sin_goce))

    essalud = dinero(computable * TASA_ESSALUD)
    detalle.append(_linea("APORTE_EMPLEADOR", "EsSalud (%s)" % _porcentaje(TASA_ESSALUD), essalud))

    total_descuentos = dinero(pension + sin_goce + otros_descuentos)
    neto = dinero(sueldo + bonos - total_descuentos)
    if neto < 0:
        neto = dinero(0)

    nid = nomina_id(periodo, empleado["empleado_id"])
    nombre = " ".join(x for x in [empleado.get("nombres"), empleado.get("apellidos")] if x).strip()
    return {
        "tenant_id": empleado["tenant_id"],
        "sk": "NOMINA#" + nid,
        "tipo": "NOMINA",
        "nomina_id": nid,
        "empleado_id": empleado["empleado_id"],
        "empleado_periodo": "%s#%s" % (empleado["empleado_id"], periodo),
        "periodo_empleado": "%s#%s" % (periodo, empleado["empleado_id"]),
        "nombre_empleado": nombre,
        "documento": empleado.get("documento"),
        "area": empleado.get("area"),
        "cargo": empleado.get("cargo"),
        "email": empleado.get("email"),
        "periodo": periodo,
        "salario_mensual": dinero(salario),
        "dias_laborados": dias,
        "sueldo_base": sueldo,
        "bonos": dinero(bonos),
        "descuentos": total_descuentos,
        "neto": neto,
        "aporte_essalud": essalud,
        "estado": "GENERADO",
        "detalle": detalle,
        "generado_en": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
