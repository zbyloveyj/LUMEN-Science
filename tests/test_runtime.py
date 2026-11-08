"""Regressions for frozen worker dispatch, preventing recursive GUI launches."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from lumen.runtime import default_data_dir, kernel_command, python_command, python_executable


class DesktopRuntimeTests(unittest.TestCase):
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
