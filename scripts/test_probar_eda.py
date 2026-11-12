import unittest
from unittest.mock import patch

from probar_eda import probar


class PruebaEdaTest(unittest.TestCase):
    def ejecutar(self, acceso_cruzado=404, lectura=True):
        andina = {"token": "token-andina", "usuario": {
            "rol": "admin_rrhh", "user_id": "usr-admin",
        }}
        aviso = {
            "notificacion_id": "not-prueba", "destinatario_id": "usr-admin",
            "metadata": {"evaluacion_id": "eva-prueba"}, "tenant_id": "andina",
            "tipo": "EvaluacionCompletada", "leida": False,
        }
        respuestas = [
            (201, {"evaluacion_id": "eva-prueba"}), (200, {}),
            (200, {"items": [aviso]}), (acceso_cruzado, {}),
            (401, {}), (200, {"leida": lectura}),
        ]
        with patch("probar_eda.http", side_effect=respuestas) as http, patch("builtins.print"):
            probar("https://desempeno", "https://notificaciones", andina, {"token": "token-pacifico"})
            self.assertEqual(http.call_count, 6)
            self.assertEqual(http.call_args_list[3].args[-1], "token-pacifico")
            self.assertEqual(http.call_args_list[-1].args[-1], "token-andina")

    def test_flujo_completo(self):
        self.ejecutar()

    def test_rechaza_acceso_cruzado_permitido(self):
        with self.assertRaisesRegex(RuntimeError, "Acceso desde pacifico"):
            self.ejecutar(acceso_cruzado=200)

    def test_rechaza_lectura_no_confirmada(self):
        with self.assertRaisesRegex(RuntimeError, "lectura"):
            self.ejecutar(lectura=False)


if __name__ == "__main__":
    unittest.main()
