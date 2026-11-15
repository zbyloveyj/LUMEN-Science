import tempfile
import unittest
from lumen.app import Workbench

class SettingsTests(unittest.TestCase):
    def test_key_preserve_clear_and_conflict(self):
        with tempfile.TemporaryDirectory() as root:
            app = Workbench(root)
            try:
                app.dispatch('settings.save', {'api_key':'fixture-secret'})
                app.dispatch('settings.save', {'model':'model-id'})
                self.assertTrue(app.dispatch('settings.get', {})['has_key'])
                with self.assertRaises(ValueError):
                    app.dispatch('settings.save', {'clear_api_key':'yes','api_key':'new'})
                self.assertEqual(app.secrets.get(),'fixture-secret')
                app.dispatch('settings.save', {'clear_api_key':'yes'})
                self.assertFalse(app.dispatch('settings.get', {})['has_key'])
                self.assertNotIn('fixture-secret',str(app.store.setting('config', {})))
            finally:
                app.execution.shutdown()
