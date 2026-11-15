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

    def test_invalid_model_address_does_not_replace_settings_or_key(self):
        with tempfile.TemporaryDirectory() as root:
            app=Workbench(root)
            try:
                app.dispatch('settings.save',{'api_base':'https://example.com/v1','api_key':'original'})
                for url in ('not-a-url','http://example.com/v1','https://user:pass@example.com','https://example.com?key=secret'):
                    with self.subTest(url=url), self.assertRaises(ValueError):
                        app.dispatch('settings.save',{'api_base':url,'api_key':'replacement'})
                    self.assertEqual(app.store.setting('config')['api_base'],'https://example.com/v1')
                    self.assertEqual(app.secrets.get(),'original')
                app.dispatch('settings.save',{'api_base':'http://127.0.0.1:1234/v1'})
            finally:
                app.execution.shutdown()
