import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("AWS_REGION", "us-east-1")

from src.services import planillas  # noqa: E402


class PlanillasTest(unittest.TestCase):
    def test_mensaje_repetido_no_recalcula_planilla_finalizada(self):
        for estado in ("GENERADA", "PAGADA"):
            with self.subTest(estado=estado), patch.object(planillas, "repo") as repo:
                repo.get_planilla.return_value = {
                    "ejecucion_id": "ejecucion-1", "estado": estado,
                }
                resultado = planillas.procesar_planilla("andina", "2026-11", "ejecucion-1")
                self.assertEqual(resultado, {"omitida": True})
                repo.update_planilla.assert_not_called()
                repo.borrar_nominas_periodo.assert_not_called()

    def test_ejecucion_fallida_se_puede_reintentar(self):
        with patch.object(planillas, "repo") as repo, patch.object(planillas, "events") as events:
            repo.get_planilla.return_value = {
                "ejecucion_id": "ejecucion-1", "estado": "FALLIDA",
            }
            repo.listar_empleados.return_value = []
            repo.query_conceptos_periodo.return_value = ([], None)
            resultado = planillas.procesar_planilla("andina", "2026-11", "ejecucion-1")
            self.assertEqual(resultado, {"periodo": "2026-11", "procesados": 0})
            repo.borrar_nominas_periodo.assert_called_once_with("andina", "2026-11")
            self.assertEqual(repo.update_planilla.call_args.args[2]["estado"], "GENERADA")
            events.publish_event.assert_not_called()


if __name__ == "__main__":
    unittest.main()
