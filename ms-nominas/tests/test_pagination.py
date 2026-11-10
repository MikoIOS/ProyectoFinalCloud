import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("AWS_REGION", "us-east-1")

from src.common.errors import Validacion  # noqa: E402
from src.common.pagination import decode_token, encode_token  # noqa: E402
from src.repositories.nominas_repo import _token_desde  # noqa: E402


class PaginationTest(unittest.TestCase):
    def test_token_gsi_incluye_clave_de_tabla(self):
        item = {
            "tenant_id": "andina",
            "sk": "NOMINA#nom-2026-11-emp-000206",
            "periodo_empleado": "2026-11#emp-000206",
        }
        key = _token_desde(item, "periodo-index", None)
        self.assertEqual(key["tenant_id"], "andina")
        self.assertEqual(key["sk"], "NOMINA#nom-2026-11-emp-000206")
        self.assertEqual(key["periodo_empleado"], "2026-11#emp-000206")

    def test_roundtrip_y_aislamiento_de_token(self):
        key = {
            "tenant_id": "andina",
            "sk": "PLANILLA#2026-11",
            "periodo_planilla": "2026-11",
        }
        token = encode_token(key)
        self.assertEqual(decode_token(token, "andina", "planilla-index"), key)
        with self.assertRaises(Validacion):
            decode_token(token, "pacifico", "planilla-index")

    def test_token_incompleto_es_rechazado(self):
        token = encode_token({"tenant_id": "andina", "periodo_empleado": "2026-11#emp-1"})
        with self.assertRaises(Validacion):
            decode_token(token, "andina", "periodo-index")


if __name__ == "__main__":
    unittest.main()
