import json
import unittest
import zipfile
from pathlib import Path

HCM = Path(__file__).resolve().parents[1]


@unittest.skipUnless((HCM / '.build/service.json').exists(), 'Ejecutar hcm/build.py primero')
class ArtifactTest(unittest.TestCase):
    def test_handlers_dependencias_y_limites_de_lambda(self):
        config = json.loads((HCM / '.build/service.json').read_text())
        for key, fn in config['functions'].items():
            with self.subTest(function=key):
                artifact = HCM / fn['package']['artifact']
                self.assertLess(artifact.stat().st_size, 50 * 1024 * 1024)
                with zipfile.ZipFile(artifact) as z:
                    extension = '.js' if fn['runtime'].startswith('node') else '.py'
                    handler = fn['handler'].rsplit('.', 1)[0] + extension
                    self.assertIn(handler, z.namelist())
                    self.assertLess(sum(i.file_size for i in z.infolist()), 250 * 1024 * 1024)
                    self.assertFalse(any(n.startswith('/') or '..' in Path(n).parts for n in z.namelist()))
                    if key == 'usuarios_login':
                        self.assertIn('jwt/__init__.py', z.namelist())
                    if key == 'notificaciones_procesarEventos':
                        self.assertIn('node_modules/@aws-sdk/client-sns/package.json', z.namelist())
                        self.assertIn('node_modules/@aws-sdk/lib-dynamodb/package.json', z.namelist())
