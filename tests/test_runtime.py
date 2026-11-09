"""Regressions for frozen worker dispatch, preventing recursive GUI launches."""
import http.client
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run
from lumen.runtime import default_data_dir, kernel_command, python_command, python_executable


class DesktopRuntimeTests(unittest.TestCase):
    def test_failed_desktop_keeps_healthy_service_for_browser(self):
        def open_browser(url, *, browser):
            self.assertTrue(browser)
            self.assertEqual(url, desktop.call_args.args[0])
            connection = http.client.HTTPConnection(url.removeprefix("http://"), timeout=3)
            try:
                connection.request("GET", "/")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                token = response.read().split(b'name="lumen-token" content="')[1].split(b'"')[0].decode()
                connection.request("POST", "/api", json.dumps({"action": "system.shutdown"}),
                                   {"Content-Type": "application/json", "X-Lumen-Token": token})
                self.assertEqual(connection.getresponse().status, 200)
            finally:
                connection.close()

        with tempfile.TemporaryDirectory() as root:
            with (patch.object(sys, "argv", ["run.py", "--data-dir", root, "--port", "0"]),
                  patch.object(run, "frozen", return_value=True),
                  patch.object(run, "desktop_window", return_value=False) as desktop,
                  patch.object(run, "offer_browser", return_value=True),
                  patch.object(run, "open_window", side_effect=open_browser),
                  patch.dict("os.environ", {"HTTP_PROXY": "http://127.0.0.1:1", "NO_PROXY": ""})):
                run.main()
            self.assertFalse((Path(root) / "server.json").exists())

    def test_frozen_default_uses_worker_for_scripts_and_kernel(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(Path.cwd() / "LUMENScience.exe")):
            worker = python_executable({})
            self.assertIn("lumen-runtime", worker)
            self.assertEqual(python_command({}, "analysis.py"), [worker, "--python-worker", "analysis.py"])
            self.assertEqual(kernel_command({}), [worker, "--kernel-worker", "-f", "{connection_file}"])
            self.assertEqual(kernel_command({"python_path": worker}), [worker, "--kernel-worker", "-f", "{connection_file}"])
            self.assertEqual(python_command({"python_path": worker}, "analysis.py"), [worker, "--python-worker", "analysis.py"])
            self.assertNotIn(".state", str(default_data_dir()))

    def test_user_interpreter_keeps_regular_python_protocol(self):
        config = {"python_path": "/custom/python"}
        with patch.object(sys, "frozen", True, create=True):
            self.assertEqual(python_command(config, "test.py"), ["/custom/python", "-u", "test.py"])
            self.assertEqual(kernel_command(config)[:3], ["/custom/python", "-m", "ipykernel_launcher"])
