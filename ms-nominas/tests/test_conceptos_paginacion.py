import unittest
from unittest.mock import patch
from src.common.auth import Ctx
from src.common.errors import Prohibido, Validacion
from src.common.pagination import encode_token, decode_token
from src.services import conceptos
from src.repositories import nominas_repo


class ConceptosPaginacionTest(unittest.TestCase):
    def setUp(self):
        self.ctx = Ctx('andina', 'admin_rrhh', 'usr-1', 'emp-1')
        self.key = {'tenant_id': 'andina', 'sk': 'CONCEPTO#con-1', 'periodo_concepto': '2026-11#con-1'}

    def test_continuacion_con_filtros_y_fin_sin_token(self):
        with patch.object(conceptos.repo, 'query_conceptos_periodo') as query:
            query.return_value = ([{'concepto_id': 'con-1'}], self.key)
            first = conceptos.listar(self.ctx, {'periodo': '2026-11', 'empleado_id': 'emp-2', 'limit': '1'})
            self.assertEqual(decode_token(first['next_token'], 'andina', 'concepto-index'), self.key)
            query.return_value = ([{'concepto_id': 'con-2'}], None)
            second = conceptos.listar(self.ctx, {'periodo': '2026-11', 'empleado_id': 'emp-2', 'limit': '1', 'next_token': first['next_token']})
            query.assert_called_with('andina', '2026-11', 'emp-2', self.key, limit=1)
            self.assertIsNone(second['next_token'])
            self.assertNotEqual(first['items'], second['items'])

    def test_token_ajeno_y_parametros_invalidos(self):
        for extra in ({'next_token': encode_token(dict(self.key, tenant_id='pacifico'))}, {'limit': '0'}, {'limit': '201'}, {'next_token': 'no-valido'}):
            with self.subTest(extra=extra), patch.object(conceptos.repo, 'query_conceptos_periodo') as query:
                with self.assertRaises(Validacion):
                    conceptos.listar(self.ctx, {'periodo': '2026-11', **extra})
                query.assert_not_called()

    def test_empleado_no_consulta_ajenos(self):
        with self.assertRaises(Prohibido):
            conceptos.listar(Ctx('andina', 'empleado', 'usr-1', 'emp-1'), {'periodo': '2026-11', 'empleado_id': 'emp-2'})

    def test_repositorio_aplica_limite_y_cursor(self):
        with patch.object(nominas_repo, '_query', return_value=([], None)) as query:
            nominas_repo.query_conceptos_periodo('andina', '2026-11', 'emp-2', self.key, limit=30)
            self.assertEqual(query.call_args.kwargs['limit'], 30)
            self.assertEqual(query.call_args.kwargs['start_key'], self.key)
            self.assertIsNotNone(query.call_args.kwargs['filter_expression'])
