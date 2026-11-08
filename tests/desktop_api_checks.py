"""Additional acceptance checks against an installed app, never an in-process Workbench."""
from __future__ import annotations

import hashlib
import io
import json
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer

from test_workbench import ModelFixture
from test_remote import RemoteTests
from lumen.runners import resolve_tool


def extended_checks(api, code, wait, boot, url):
    checks = []
    pid = boot["project_id"]
    sid = boot["sessions"][0]["id"]

    def poll_run(run, expected):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            run = api("run.read", project_id=pid, run_id=run["id"])
            if run["status"] not in ("queued", "running"):
                assert run["status"] == expected, run
                return run
            time.sleep(.1)
        raise AssertionError("Run failed to reach " + expected)

    def read_file(path):
        query = urllib.parse.urlencode({"project": pid, "path": path, "download": "1"})
        return urllib.request.urlopen(url + "/file?" + query, timeout=20).read()

    failed = api("cell.run", project_id=pid, session_id=sid, language="python", code="raise ValueError('EXPECTED_TEST_ERROR')")
    poll_run(failed, "failed")
    code("python", "assert lumen_packaged_value == 42\nprint('ERROR_RECOVERY_OK')")
    checks.append("kernel_recovers_after_user_code_error")

    running = api("cell.run", project_id=pid, session_id=sid, language="python", code="import time\nwhile True: time.sleep(.1)")
    deadline = time.monotonic() + 15
    while api("run.read", project_id=pid, run_id=running["id"])["status"] == "queued" and time.monotonic() < deadline:
        time.sleep(.1)
    time.sleep(.3)
    queued = api("cell.run", project_id=pid, session_id=sid, language="python", code="must_not_execute=True")
    api("run.cancel", project_id=pid, run_id=queued["id"])
    api("run.cancel", project_id=pid, run_id=running["id"])
    poll_run(running, "cancelled")
    poll_run(queued, "cancelled")
    code("python", "assert 'must_not_execute' not in globals()\nprint('CANCEL_RECOVERY_OK')")
    checks.append("active_and_queued_cancellation_with_kernel_recovery")

    templates = {"group": {"group": "group", "value": "marker_a"}, "correlation": {},
                 "regression": {"target": "response", "predictors": ["age", "marker_a"]}}
    for template, parameters in templates.items():
        run = wait(api("workflow.run", project_id=pid, session_id=sid, template_id=template,
                       path="data/synthetic_experiment.csv", parameters=parameters))
        assert len(run["detail"]["artifacts"]) >= 3, run
        for artifact in run["detail"]["artifacts"]:
            snapshot = ".lumen/runs/" + run["id"] + "/artifacts/" + artifact["path"]
            assert hashlib.sha256(read_file(snapshot)).hexdigest() == artifact["sha256"]
        checks.append("bundled_workflow_" + template + "_and_snapshot_hashes")

    samples = {
        "javascript": ("node", "console.log(42)"),
        "typescript": ("node", "const x: number = 42; console.log(x)"),
        "R": ("Rscript", "cat(42)"),
        "c": ("cc", '#include <stdio.h>\nint main(void){printf("42\\n");return 0;}'),
        "cpp": ("cxx", '#include <iostream>\nint main(){std::cout<<42<<std::endl;}'),
        "java": ("java", 'public class Main {public static void main(String[] args){System.out.println(42);}}'),
        "go": ("go", 'package main\nimport "fmt"\nfunc main(){fmt.Println(42)}'),
        "rust": ("rustc", 'fn main(){println!("42");}'),
        "powershell": ("pwsh", "Write-Output 42"), "bash": ("bash", "printf '42\\n'"),
    }
    for language, (tool, source) in samples.items():
        path = resolve_tool(tool, {})
        if not path:
            checks.append("external_" + language + "_skipped_tool_not_installed")
            continue
        settings = {"runner_" + tool: path}
        if language == "java":
            javac = resolve_tool("javac", {})
            if not javac:
                checks.append("external_java_skipped_jdk_not_installed")
                continue
            settings["runner_javac"] = javac
        api("settings.save", **settings)
        result = code(language, source)
        assert "42" in json.dumps(result["detail"]["outputs"]), result
        checks.append("installed_app_executes_external_" + language)

    api("settings.save", python_path=sys.executable)
    external_session = api("session.create", project_id=pid, title="External Python check")
    wait(api("cell.run", project_id=pid, session_id=external_session["id"], language="python",
             code="import pandas as pd\nprint('EXTERNAL_PYTHON_OK', pd.__version__)"))
    api("settings.save", python_path="")
    checks.append("installed_app_executes_user_configured_python")

    fixture = ThreadingHTTPServer(("127.0.0.1", 0), ModelFixture)
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    try:
        api("settings.save", api_base="http://127.0.0.1:" + str(fixture.server_port) + "/v1",
            model="fixture", api_key="test-fixture-credential", protocol="chat")
        assert api("settings.test")["connected"]
        assert api("settings.test", protocol="responses")["connected"]
        session = api("session.create", project_id=pid, title="Packaged agent fixture")
        job = api("chat.start", project_id=pid, session_id=session["id"], text="run fixture", mode="review")
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            state = api("chat.status", job_id=job["id"])
            if state["status"] != "running":
                break
            time.sleep(.1)
        assert state["status"] == "needs_approval", state
        api("chat.approve", job_id=job["id"], approved=True)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            state = api("chat.status", job_id=job["id"])
            if state["status"] in ("success", "failed", "cancelled"):
                break
            time.sleep(.1)
        assert state["status"] == "success", state
        checks.append("packaged_model_protocols_and_approved_agent_execution_fixture")
    finally:
        fixture.shutdown()
        fixture.server_close()

    RemoteTests.setUpClass()
    try:
        probe = api("remote.probe", host="127.0.0.1", port=RemoteTests.port)
        profile = api("remote.save", host="127.0.0.1", port=RemoteTests.port, username="tester",
                      password="local-fixture-only", root="/", name="Packaged SSH fixture", probe_id=probe["probe_id"])
        profile_id = profile["id"]
        assert api("remote.test", profile_id=profile_id)["connected"]
        listing = api("remote.files", project_id=pid, profile_id=profile_id)
        assert "source.txt" in [f["name"] for f in listing["files"]]
        download = api("remote.transfer", project_id=pid, profile_id=profile_id, direction="download", remote="source.txt")
        assert read_file(download["path"]).decode() == "fixture source"
        api("remote.transfer", project_id=pid, profile_id=profile_id, direction="upload",
            local="data/synthetic_experiment.csv", remote="packaged-upload.csv")
        assert (RemoteTests.remote_root / "packaged-upload.csv").is_file()
        command = wait(api("remote.execute", project_id=pid, profile_id=profile_id, command="printf fixture"))
        assert command["detail"]["exit_code"] == 0
        assert "remote-fixture-42" in json.dumps(command["detail"]["outputs"])
        checks.append("packaged_pinned_ssh_sftp_and_remote_command_fixture")
    finally:
        RemoteTests.tearDownClass()

    delivery = api("project.export", project_id=pid, include_data=False)
    with zipfile.ZipFile(io.BytesIO(read_file(delivery["path"]))) as archive:
        assert not any("kernels/" in name or name.startswith("project/data/") for name in archive.namelist())
        assert "manifest.json" in archive.namelist()
        assert all(b"test-fixture-credential" not in archive.read(name) for name in archive.namelist())
    checks.append("delivery_zip_excludes_api_credential_kernel_keys_and_raw_data")
    return checks
