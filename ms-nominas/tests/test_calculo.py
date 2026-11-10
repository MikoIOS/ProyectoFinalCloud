import os
import sys
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("AWS_REGION", "us-east-1")

from src.services import calculo, liquidacion, pdf  # noqa: E402


def empleado(**overrides):
    base = {
        "tenant_id": "andina",
        "empleado_id": "emp-000001",
        "nombres": "Ana",
        "apellidos": "Pérez",
        "documento": "12345678",
        "area": "Finanzas",
        "cargo": "Analista",
        "email": "ana@andina.pe",
        "salario_base": Decimal("3500"),
        "estado": "ACTIVO",
        "fecha_ingreso": "2020-01-01",
    }
    base.update(overrides)
    return base


class CalculoNominaTest(unittest.TestCase):
    def test_mes_completo_sin_conceptos(self):
        n = calculo.calcular(empleado(), "2026-11", [])
        self.assertEqual(n["dias_laborados"], 30)
        self.assertEqual(n["sueldo_base"], Decimal("3500.00"))
        self.assertEqual(n["bonos"], Decimal("0.00"))
        self.assertEqual(n["descuentos"], Decimal("455.00"))
        self.assertEqual(n["neto"], Decimal("3045.00"))
        self.assertEqual(n["aporte_essalud"], Decimal("315.00"))

    def test_bono_no_afecta_base_de_pension(self):
        n = calculo.calcular(empleado(), "2026-11", [
            {"tipo": "BONO", "concepto": "Bono de productividad", "monto": Decimal("300")},
        ])
        self.assertEqual(n["bonos"], Decimal("300.00"))
        self.assertEqual(n["descuentos"], Decimal("455.00"))
        self.assertEqual(n["neto"], Decimal("3345.00"))

    def test_descuento_manual(self):
        n = calculo.calcular(empleado(), "2026-11", [
            {"tipo": "DESCUENTO", "concepto": "Adelanto", "monto": Decimal("100")},
        ])
        self.assertEqual(n["descuentos"], Decimal("555.00"))
        self.assertEqual(n["neto"], Decimal("2945.00"))

    def test_sin_goce(self):
        n = calculo.calcular(empleado(), "2026-11", [
            {"tipo": "SIN_GOCE", "concepto": "Ausencia", "dias": 2, "monto": 0},
        ])
        self.assertEqual(n["sueldo_base"], Decimal("3500.00"))
        self.assertEqual(n["descuentos"], Decimal("658.00"))
        self.assertEqual(n["neto"], Decimal("2842.00"))
        self.assertTrue(any("Ausencia sin goce" in d["concepto"] for d in n["detalle"]))

    def test_ingreso_a_mitad_de_mes(self):
        n = calculo.calcular(empleado(fecha_ingreso="2026-11-16"), "2026-11", [])
        self.assertEqual(n["dias_laborados"], 15)
        self.assertEqual(n["sueldo_base"], Decimal("1750.00"))
        self.assertEqual(n["descuentos"], Decimal("227.50"))
        self.assertEqual(n["neto"], Decimal("1522.50"))

    def test_cesado_antes_del_periodo_no_genera(self):
        self.assertIsNone(calculo.calcular(empleado(estado="CESADO", fecha_cese="2026-10-31"), "2026-11", []))

    def test_sin_salario_no_genera(self):
        self.assertIsNone(calculo.calcular(empleado(salario_base=0), "2026-11", []))

    def test_liquidacion_ingreso_29_febrero(self):
        with patch("src.services.liquidacion.repo.put_liquidacion"):
            item = liquidacion.calcular(
                empleado(fecha_ingreso="2020-02-29", salario_base=Decimal("3600")),
                date(2026, 2, 28),
                "Renuncia",
            )
        self.assertIsNotNone(item)
        self.assertEqual(item["fecha_cese"], "2026-02-28")
        self.assertGreater(item["total"], 0)

    def test_pdf_valido(self):
        n = calculo.calcular(empleado(), "2026-11", [])
        contenido = pdf.generar(n)
        self.assertTrue(contenido.startswith(b"%PDF-1.4"))
        self.assertIn(b"BOLETA DE PAGO", contenido)
        self.assertGreater(len(contenido), 1000)


if __name__ == "__main__":
    unittest.main()
