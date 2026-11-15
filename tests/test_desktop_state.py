import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from lumen.server import LocalServer
from lumen.window_state import load_window_state, save_window_state


class DesktopStateTests(unittest.TestCase):
    def test_geometry_roundtrip_and_disconnected_monitor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            screen = SimpleNamespace(x=0, y=0, width=1920, height=1080)
            window = SimpleNamespace(x=80, y=60, width=1200, height=800)
            save_window_state(root, window)
            self.assertEqual(load_window_state(root, [screen]), vars(window))
            window.x = 4000
            save_window_state(root, window)
            self.assertNotIn('x', load_window_state(root, [screen]))

    def test_corrupt_and_invalid_geometry_does_not_prevent_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for raw in ('{', '[]', 'null', '{"width":true}',
                        '{"x":0,"y":0,"width":-1,"height":800}'):
                (root / 'window.json').write_text(raw, encoding='utf-8')
                self.assertEqual(load_window_state(root, []), {'width':1440, 'height':960})

    def test_cross_site_file_request_rejected_before_access(self):
        with LocalServer(('127.0.0.1', 0), None, 'web') as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            try:
                connection.request('GET', '/file?project=private&path=secret.png',
                                   headers={'Sec-Fetch-Site':'cross-site'})
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                connection.request('GET', '/health')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())['service'], 'lumen-science')
            finally:
                connection.close()
                server.shutdown()
                thread.join(timeout=5)
