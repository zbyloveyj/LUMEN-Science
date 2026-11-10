"""Regressions for frozen worker dispatch, preventing recursive GUI launches."""
import http.client
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import run
from lumen.runtime import default_data_dir, kernel_command, python_command, python_executable


class DesktopRuntimeTests(unittest.TestCase):
    def stop_workbench(self, url):
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

    def test_second_listener_cannot_take_workbench_port(self):
        with run.LocalServer(("127.0.0.1", 0), None, "web") as first:
            with self.assertRaises(OSError):
                with run.LocalServer(first.server_address, None, "web"):
                    pass

    def test_second_process_waits_for_starting_workbench(self):
        repo = Path(run.__file__).resolve().parent
        slow_start = """
import os, time
import run
create = run.Workbench
def slow_workbench(root):
    (root / 'initializing').write_text(str(os.getpid()), encoding='utf-8')
    time.sleep(1.5)
    return create(root)
run.Workbench = slow_workbench
run.main()
"""
        with tempfile.TemporaryDirectory() as directory:
            args = ["--no-browser", "--port", "0", "--data-dir", directory]
            with subprocess.Popen([sys.executable, "-c", slow_start, *args], cwd=repo,
                                  stdout=subprocess.DEVNULL) as first:
                root = Path(directory)
                marker = root / "initializing"
                owner_pid = first.pid
                try:
                    deadline = time.monotonic() + 10
                    while not marker.is_file() and time.monotonic() < deadline:
                        self.assertIsNone(first.poll())
                        time.sleep(.05)
                    owner_pid = int(marker.read_text(encoding="utf-8"))
                    second = subprocess.run([sys.executable, str(repo / "run.py"), *args], cwd=repo,
                                            capture_output=True, text=True, timeout=15, check=True)
                    info = json.loads((root / "server.json").read_text(encoding="utf-8"))
                    self.assertEqual(info["pid"], owner_pid)
                    self.assertEqual(second.stdout.strip(), info["url"])
                    self.assertTrue(run.service_is_ready(info["url"], info["instance_id"]))
                    self.stop_workbench(info["url"])
                    self.assertEqual(first.wait(timeout=10), 0)
                finally:
                    if first.poll() is None:
                        os.kill(owner_pid, signal.SIGTERM)
                    first.wait(timeout=10)

    def test_failed_desktop_keeps_healthy_service_for_browser(self):
        def open_browser(url, *, browser):
            self.assertTrue(browser)
            self.assertEqual(url, desktop.call_args.args[0])
            self.assertNotEqual(int(url.rsplit(":", 1)[1]), occupied.server_port)
            self.stop_workbench(url)

        with run.LocalServer(("127.0.0.1", 0), None, "web") as occupied, tempfile.TemporaryDirectory() as root:
            with (patch.object(sys, "argv", ["run.py", "--data-dir", root, "--port", str(occupied.server_port)]),
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
