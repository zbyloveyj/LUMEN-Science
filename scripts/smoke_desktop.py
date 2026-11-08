"""Exercise a packaged app through its public local API, with no Python on PATH."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--report", type=Path, default=Path("test-results/desktop-smoke.json"))
    parser.add_argument("--extended", action="store_true", help="Also check external languages, cancellation, AI and SSH fixtures")
    args = parser.parse_args()
    executable = args.executable.resolve()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    checks = []
    with tempfile.TemporaryDirectory(prefix="lumen-installed-", dir=args.report.parent) as directory:
        root = Path(directory).resolve()
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV")}
        env.update(PYTHONUTF8="1", JUPYTER_PLATFORM_DIRS="1", PYDEVD_DISABLE_FILE_VALIDATION="1",
                   JUPYTER_PATH=str(root / "empty-jupyter"), JUPYTER_CONFIG_DIR=str(root / "jupyter-config"),
                   JUPYTER_DATA_DIR=str(root / "jupyter-data"))
        if os.name == "nt":
            env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        expected_project = None
        for attempt in range(2):
            with (root / ("launch-" + str(attempt) + ".log")).open("wb") as log:
                process = subprocess.Popen([str(executable), "--no-browser", "--port", "0", "--data-dir", str(root / "state")],
                                           cwd=root, env=env, stdout=log, stderr=log)
                url = None
                token = None
                try:
                    deadline = time.monotonic() + 70
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise AssertionError("Packaged app exited: " + (root / ("launch-" + str(attempt) + ".log")).read_text(errors="replace"))
                        try:
                            info = json.loads((root / "state/server.json").read_text())
                            url = info["url"]
                            html = urllib.request.urlopen(url, timeout=2).read().decode()
                            token = re.search(r'name="lumen-token" content="([^"]+)"', html).group(1)
                            break
                        except (OSError, ValueError, AttributeError):
                            time.sleep(.2)
                    assert token, "Packaged app startup timed out"
                    assert b"translucent navigation" in urllib.request.urlopen(url + "/apple.css", timeout=5).read()

                    def api(action, **params):
                        request = urllib.request.Request(url + "/api", json.dumps({"action": action, "params": params}).encode(),
                                                        {"Content-Type": "application/json", "X-Lumen-Token": token})
                        with urllib.request.urlopen(request, timeout=30) as response:
                            result = json.load(response)
                        assert result["ok"], result
                        return result["data"]

                    boot = api("bootstrap")
                    project_id = boot["project_id"]
                    session_id = boot["sessions"][0]["id"]
                    assert boot["environment"]["bundled_runtime"] is True
                    assert boot["environment"]["packages"]["pandas"]
                    if attempt:
                        assert project_id == expected_project
                        assert len(api("runs.list", project_id=project_id)) >= 4
                        checks.append("restart_preserves_project_and_run_history")
                        continue
                    expected_project = project_id
                    checks.append("isolated_start_without_system_python")
                    api("settings.save", python_path=boot["environment"]["python"])
                    assert api("data.preview", project_id=project_id, path="data/synthetic_experiment.csv")["rows"] == 120
                    checks.append("bundled_csv_preview")

                    def wait(run):
                        deadline = time.monotonic() + 120
                        while time.monotonic() < deadline:
                            run = api("run.read", project_id=project_id, run_id=run["id"])
                            if run["status"] not in ("queued", "running"):
                                if run["status"] != "success":
                                    logs = "\n".join(p.read_text(encoding="utf-8", errors="replace")[-5000:]
                                                     for p in (root / "state/projects").glob("*/.lumen/kernels/*.log"))
                                    raise AssertionError(json.dumps(run, ensure_ascii=False) + "\n" + logs)
                                return run
                            time.sleep(.2)
                        raise AssertionError("Packaged computation timed out")

                    def code(language, source):
                        return wait(api("cell.run", project_id=project_id, session_id=session_id, language=language, code=source))

                    code("python", "import pandas as pd\nlumen_packaged_value=42\nprint(pd.read_csv('data/synthetic_experiment.csv').shape)")
                    result = code("python", "assert lumen_packaged_value==42\nprint('PERSISTENT_OK')")
                    assert "PERSISTENT_OK" in json.dumps(result)
                    checks.append("bundled_persistent_python_kernel")
                    result = code("sql", "CREATE TABLE IF NOT EXISTS smoke(x); INSERT INTO smoke VALUES(42); SELECT * FROM smoke;")
                    assert "42" in json.dumps(result)
                    checks.append("bundled_sql_worker")
                    workflow = wait(api("workflow.run", project_id=project_id, session_id=session_id,
                                        template_id="quality", path="data/synthetic_experiment.csv"))
                    assert workflow["detail"]["artifacts"], workflow
                    checks.append("independent_pandas_scipy_matplotlib_workflow_and_artifacts")
                    export = api("notebook.export", project_id=project_id, session_id=session_id)
                    assert export["path"].endswith(".ipynb")
                    checks.append("notebook_export")
                    if args.extended:
                        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
                        from desktop_api_checks import extended_checks
                        checks.extend(extended_checks(api, code, wait, boot, url))
                finally:
                    if token and process.poll() is None:
                        try:
                            api("system.shutdown")
                        except OSError:
                            pass
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        raise AssertionError("Packaged app did not stop after shutdown")
                    assert process.returncode == 0, "Packaged app failed during shutdown"
    report = {"status": "passed", "checks": [c for c in checks if "_skipped_" not in c],
              "skipped": [c for c in checks if "_skipped_" in c],
              "scope": "Packaged Windows API/runtime; graphical window is checked separately"}
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
