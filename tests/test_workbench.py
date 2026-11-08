from __future__ import annotations

import base64
import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lumen.app import Workbench
from lumen.agent import ModelClient
from lumen.files import safe_path, sha256
from lumen.runners import environments
from lumen.server import LocalServer
from lumen.store import Store

BASE = Path(__file__).resolve().parents[1]
RESULTS = BASE / "test-results"
RESULTS.mkdir(exist_ok=True)


class ModelFixture(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path.endswith("/responses"):
            answer={"output":[{"type":"message","content":[{"type":"output_text","text":"OK"}]}],
                    "usage":{"input_tokens":4,"output_tokens":1}}
        elif body.get("tools") and body["messages"][-1]["role"]=="user":
            answer={"choices":[{"message":{"role":"assistant","content":"",
                "tool_calls":[{"id":"fixture-call","type":"function","function":{"name":"run_code",
                "arguments":json.dumps({"language":"python","code":"print(42)"})}}]}}],
                "usage":{"prompt_tokens":6,"completion_tokens":4}}
        else:
            answer={"choices":[{"message":{"role":"assistant","content":"OK 42"}}],
                    "usage":{"prompt_tokens":4,"completion_tokens":2}}
        raw=json.dumps(answer).encode()
        self.send_response(200);self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)


class WorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="lumen-verification-",dir=RESULTS)
        cls.app=Workbench(cls.temp.name)
        boot=cls.app.dispatch("bootstrap",{})
        cls.pid=boot["project_id"];cls.sid=boot["sessions"][0]["id"]
        cls.root=Path(cls.app.project(cls.pid)["path"])
        cls.model=ThreadingHTTPServer(("127.0.0.1",0),ModelFixture)
        threading.Thread(target=cls.model.serve_forever,daemon=True).start()
        cls.app.store.set_setting("config",{"api_base":"http://127.0.0.1:"+str(cls.model.server_port)+"/v1",
                                           "model":"test-fixture","protocol":"chat"})
        cls.server=LocalServer(("127.0.0.1",0),cls.app,BASE/"web")
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
        cls.baseurl="http://127.0.0.1:"+str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
        cls.model.shutdown();cls.model.server_close()
        cls.app.execution.shutdown()
        cls.temp.cleanup()

    def wait(self,run,timeout=120):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            run=self.app.store.run(run["id"])
            if run["status"] not in ("queued","running"):return run
            time.sleep(.15)
        self.app.execution.cancel(run["id"])
        self.fail("Run timed out: "+run["language"])

    def run_code(self,language,code,timeout=120):
        return self.wait(self.app.execution.submit(self.pid,self.sid,language,code,timeout=timeout),timeout+15)

    def assert_success(self,run):
        self.assertEqual(run["status"],"success",json.dumps(run["detail"],ensure_ascii=False))

    def test_01_path_and_project_isolation(self):
        for bad in ("../private.txt","C:/private.txt","outputs/../../outside",""):
            with self.assertRaises(ValueError):safe_path(self.root,bad)
        other=self.app.create_project("isolation")
        with self.assertRaises(ValueError):self.app.session(self.sid,other["id"])
        with self.assertRaises(ValueError):
            self.app.dispatch("files.save",{"project_id":self.pid,"path":"data/overwrite.csv","text":"bad"})

    def test_02_table_quality_and_import_no_overwrite(self):
        data=self.app.dispatch("data.preview",{"project_id":self.pid,"path":"data/synthetic_experiment.csv"})
        self.assertEqual(data["rows"],120)
        self.assertEqual(sum(c["missing"] for c in data["columns"]),7)
        with self.assertRaises(FileExistsError):
            self.app.dispatch("files.import",{"project_id":self.pid,"name":"synthetic_experiment.csv",
                                             "content":base64.b64encode(b"x\n1\n").decode()})

    def test_03_python_state_and_error_recovery(self):
        self.assert_success(self.run_code("python","retained_value=41\nprint(retained_value)"))
        run=self.run_code("python","print(retained_value+1)")
        self.assert_success(run)
        self.assertIn("42",str(run["detail"]["outputs"]))
        failed=self.run_code("python","raise ValueError('intentional verification')")
        self.assertEqual(failed["status"],"failed")
        self.assert_success(self.run_code("python","assert retained_value==41"))

    def test_04_javascript_typescript_sql_powershell_bash_R(self):
        cases=[("javascript","console.log(6*7)"),("typescript","const x: number=42; console.log(x);"),
               ("sql","SELECT 6*7 AS answer;"),("powershell","Write-Output (6*7)"),
               ("bash","printf '42\\n'"),("R","print(6*7)")]
        ready={item["id"]:item["ready"] for item in environments(self.app.store.setting("config",{}))}
        for language,code in cases:
            with self.subTest(language=language):
                if not ready[language]:self.skipTest("toolchain not configured: "+language)
                run=self.run_code(language,code)
                self.assert_success(run);self.assertIn("42",str(run["detail"]["outputs"]))

    def test_05_java_compiles_and_runs(self):
        run=self.run_code("java",'public class Main { public static void main(String[] a) { System.out.println(42); }}',45)
        self.assert_success(run)
        self.assertIn("42",str(run["detail"]["outputs"]))
        self.assertEqual(len(run["detail"]["environment"]["commands"]),2)

    def test_06_c_cpp_compile_and_run(self):
        for language,code in [("c",'#include <stdio.h>\nint main(void){printf("%d\\n",42);return 0;}'),
                              ("cpp",'#include <cstdio>\nint main(){std::printf("%d\\n",42);return 0;}')]:
            with self.subTest(language=language):
                run=self.run_code(language,code,240)
                self.assert_success(run)
                self.assertIn("42",str(run["detail"]["outputs"]))

    def test_07_cancel_running_and_queued_isolated(self):
        first=self.app.execution.submit(self.pid,self.sid,"python","import time\nprint('started',flush=True)\ntime.sleep(25)")
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if "started" in str(self.app.store.run(first["id"])["detail"]["outputs"]):break
            time.sleep(.1)
        second=self.app.execution.submit(self.pid,self.sid,"python","should_never_exist=123")
        self.app.execution.cancel(second["id"])
        self.assertEqual(self.wait(second)["status"],"cancelled")
        self.assertEqual(self.app.store.run(first["id"])["status"],"running")
        self.app.execution.cancel(first["id"])
        self.assertEqual(self.wait(first)["status"],"cancelled")
        self.assert_success(self.run_code("python","assert 'should_never_exist' not in globals()"))

    def test_08_workflows_outputs_snapshot_and_reproduction(self):
        params={"quality":{},"group":{"group":"group","value":"marker_a"},
                "correlation":{},"regression":{"target":"response","predictors":["age","marker_a"]}}
        quality=None
        for template,parameters in params.items():
            with self.subTest(template=template):
                run=self.wait(self.app.dispatch("workflow.run",{"project_id":self.pid,"session_id":self.sid,
                    "template_id":template,"path":"data/synthetic_experiment.csv","parameters":parameters}))
                self.assert_success(run);self.assertGreaterEqual(len(run["detail"]["artifacts"]),3)
                for item in run["detail"]["artifacts"]:
                    snapshot=self.root/".lumen"/"runs"/run["id"]/"artifacts"/item["path"]
                    self.assertEqual(sha256(snapshot),item["sha256"])
                if template=="quality":quality=run
        result=self.app.dispatch("run.reproduce",{"project_id":self.pid,"run_id":quality["id"]})
        rerun=self.wait(result["run"])
        self.assert_success(rerun)
        self.assertNotEqual(rerun["project_id"],self.pid)
        self.assertEqual(rerun["detail"]["origin_run_id"],quality["id"])

    def test_09_version_and_export_exclude_credentials(self):
        self.app.dispatch("files.save",{"project_id":self.pid,"path":"outputs/version.csv","text":"x\n1\n"})
        version=self.app.dispatch("artifact.retain",{"project_id":self.pid,"path":"outputs/version.csv"})
        self.app.dispatch("files.save",{"project_id":self.pid,"path":"outputs/version.csv","text":"x\n2\n","overwrite":True})
        comparison=self.app.dispatch("artifact.compare",{"project_id":self.pid,"version_id":version["id"]})
        self.assertFalse(comparison["same"]);self.assertFalse(comparison["exact_table_equal"])
        result=self.app.dispatch("project.export",{"project_id":self.pid,"include_data":False})
        with zipfile.ZipFile(self.root/result["path"]) as archive:
            names=archive.namelist()
            self.assertFalse(any(x.startswith("project/data/") for x in names))
            self.assertFalse(any("workbench.sqlite" in x or "credential" in x for x in names))
            self.assertIn("manifest.json",names)

    def test_10_http_auth_and_asset_safety(self):
        page=urllib.request.urlopen(self.baseurl).read().decode()
        self.assertIn(self.server.token,page);self.assertNotIn("__LUMEN_TOKEN__",page)
        for name in ("app.js","core.js","workspace.js","research.js","notebook.js","servers.js","styles.css"):
            self.assertEqual(urllib.request.urlopen(self.baseurl+"/"+name).status,200)
        request=urllib.request.Request(self.baseurl+"/api",data=b'{"action":"bootstrap"}',
                                       headers={"Content-Type":"application/json"})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,403)
        request.add_header("X-Lumen-Token",self.server.token)
        self.assertTrue(json.load(urllib.request.urlopen(request))["ok"])
        request=urllib.request.Request(self.baseurl+"/api",data=b'{"action":"bootstrap"}',
            headers={"Content-Type":"application/json","X-Lumen-Token":self.server.token,"Origin":"https://untrusted.example"})
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(request)

    def test_11_model_protocols_and_tool_validation(self):
        config=self.app.store.setting("config")
        answer,_=ModelClient(config,"").request([{"role":"user","content":"ping"}])
        self.assertIn("OK",answer["content"])
        answer,_=ModelClient({**config,"protocol":"responses"},"").request([{"role":"user","content":"ping"}])
        self.assertEqual(answer["content"],"OK")
        from lumen.agent import TOOLS
        with self.assertRaises(ValueError):self.app.agent._validate("run_code",{"language":"python","code":"1","other":True},TOOLS)

    def test_12_agent_execution_requires_approval(self):
        session=self.app.create_session(self.pid,"agent fixture")
        job=self.app.agent.start(self.pid,session["id"],"run fixture",mode="review")
        deadline=time.monotonic()+15
        while time.monotonic()<deadline and self.app.agent.view(job["id"])["status"]=="running":time.sleep(.1)
        pending=self.app.agent.view(job["id"])
        self.assertEqual(pending["status"],"needs_approval")
        self.assertEqual(pending["pending"]["arguments"]["code"],"print(42)")
        self.app.agent.approve(job["id"],True)
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            result=self.app.agent.view(job["id"])
            if result["status"] in ("success","failed","cancelled"):break
            time.sleep(.1)
        self.assertEqual(result["status"],"success",str(result))
        messages=self.app.store.messages(session["id"])
        tool=next(m["content"] for m in messages if m["role"]=="tool")
        self.assertEqual(json.loads(tool["content"])["status"],"success")

    def test_13_pipeline_stops_on_failure(self):
        pipeline=self.app.dispatch("pipeline.save",{"project_id":self.pid,"name":"stop-on-error","steps":[
            {"language":"python","code":"raise RuntimeError('stop here')","title":"first"},
            {"language":"python","code":"never_executed=True","title":"second"}]})
        job=self.app.dispatch("pipeline.start",{"project_id":self.pid,"session_id":self.sid,"workflow_id":pipeline["id"]})
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            result=self.app.dispatch("pipeline.status",{"job_id":job["id"]})
            if result["status"]!="running":break
            time.sleep(.1)
        self.assertEqual(result["status"],"failed");self.assertEqual(len(result["steps"]),1)

    def test_14_secret_never_returned(self):
        self.app.dispatch("settings.save",{"api_key":"synthetic-test-key-not-a-real-credential"})
        result=self.app.dispatch("settings.get",{})
        self.assertTrue(result["has_key"])
        self.assertNotIn("synthetic-test-key",json.dumps(result))
        self.assertEqual(self.app.secrets.get(),"synthetic-test-key-not-a-real-credential")

    def test_15_notebook_export(self):
        result=self.app.dispatch("notebook.export",{"project_id":self.pid,"session_id":self.sid})
        notebook=json.loads((self.root/result["path"]).read_text(encoding="utf-8"))
        self.assertEqual(notebook["nbformat"],4)
        self.assertEqual(len(notebook["cells"]),2)
        self.assertTrue(notebook["cells"][0]["source"].startswith("import pandas"))


if __name__=="__main__":
    unittest.main(verbosity=2)
