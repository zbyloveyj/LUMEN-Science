from __future__ import annotations

import base64
import importlib.util
import json
import os
import random
import re
import shutil
import sys
import threading
import time
import zipfile
from pathlib import Path

from . import __version__, literature
from .agent import Agent, ModelClient
from .execution import Execution
from .files import (MAX_FILE, identity, import_file, read_text, safe_path, sha256,
                    table_preview, walk_files, write_text)
from .secrets import Secrets
from .store import Store, dumps, now, uid
from .workflows import TEMPLATES, build_workflow
from .runners import LANGUAGES, environments
from .runtime import python_executable, frozen, default_data_dir
from .remote import Remote


class Workbench:
    def __init__(self, root):
        self.store = Store(root)
        self.secrets = Secrets(self.store)
        self.execution = Execution(self.store, self.project)
        self.agent = Agent(self)
        self.remote = Remote(self)
        self.pipelines = {}
        self.reference_searches = {}
        if not self.store.one("SELECT id FROM projects LIMIT 1"):
            self._demo()

    def project(self, project_id):
        project = self.store.one("SELECT * FROM projects WHERE id=?", (project_id,))
        if not project or not Path(project["path"]).is_dir():
            raise ValueError("项目不存在或目录不可用")
        return project

    def session(self, session_id, project_id=None):
        session = self.store.one("SELECT * FROM sessions WHERE id=?", (session_id,))
        if not session or (project_id and session["project_id"] != project_id):
            raise ValueError("会话不属于当前项目")
        return session

    def create_project(self, name, path="", description=""):
        name = str(name).strip()
        if not name or len(name) > 100:
            raise ValueError("项目名称需要为 1–100 字")
        project_id = uid()
        if path:
            root = Path(path).expanduser().resolve()
            if not root.is_dir():
                raise ValueError("连接已有项目时，请填写已经存在的目录")
        else:
            root = self.store.root / "projects" / (re.sub(r'[<>:"/\\|?*]', "-", name)[:45] + "-" + project_id[:6])
            root.mkdir(parents=True, exist_ok=False)
        if self.store.one("SELECT id FROM projects WHERE path=?", (str(root),)):
            raise ValueError("此目录已经连接为项目")
        for folder in ("data", "scripts", "outputs", "reports", ".lumen"):
            safe_path(root,folder).mkdir(exist_ok=True)
        self.store.execute("INSERT INTO projects VALUES(?,?,?,?,?)",
                           (project_id, name, str(root), description[:2000], now()))
        session = self.create_session(project_id, "研究对话")
        return {**self.project(project_id), "session_id": session["id"]}

    def create_session(self, project_id, title="新对话"):
        self.project(project_id)
        session_id = uid()
        self.store.execute("INSERT INTO sessions VALUES(?,?,?,?)",
                           (session_id, project_id, str(title)[:100] or "新对话", now()))
        return self.session(session_id)

    def _demo(self):
        project = self.create_project("示例 · 实验数据探索", description="合成数据示例，可离线体验全部本地分析流程。")
        rng = random.Random(2026)
        lines = ["sample_id,group,age,marker_a,marker_b,response"]
        for i in range(120):
            group = "Control" if i < 60 else "Treatment"
            age = rng.randint(23, 68)
            a = rng.gauss(5, 1.2) + (0.65 if i >= 60 else 0)
            b = a * 0.4 + rng.gauss(2, 0.7)
            response = 10 + .2 * age + 1.3 * a + rng.gauss(0, 2)
            lines.append(",".join([f"S{i+1:03d}", group, str(age), "" if i in (8, 25, 89) else f"{a:.4f}",
                                   "" if i in (2, 31, 85, 110) else f"{b:.4f}", f"{response:.4f}"]))
        (Path(project["path"]) / "data" / "synthetic_experiment.csv").write_text("\n".join(lines), encoding="utf-8")
        write_text(project["path"], "reports/关于示例数据.md",
                   "# 示例数据\n\n此项目的120行数据由固定随机种子2026生成，全部为合成数据，不代表任何实际研究或受试者。\n")
        self.save_cell(project["id"], project["session_id"], "python",
                       "import pandas as pd\n"
                       "df = pd.read_csv('data/synthetic_experiment.csv')\n"
                       "print('合成示例数据，非真实研究数据')\n"
                       "print(df.shape)\ndf.head()", None)
        self.save_cell(project["id"], project["session_id"], "python",
                       "# 上一单元加载的 df 可以继续使用\n"
                       "df.groupby('group')[['marker_a', 'response']].agg(['count', 'mean', 'std'])", None)

    def save_cell(self, project_id, session_id, language, code, cell_id=None):
        self.session(session_id, project_id)
        if language not in LANGUAGES or not isinstance(code, str) or len(code) > 200_000:
            raise ValueError("代码单元格式无效")
        if cell_id:
            row = self.store.one("SELECT * FROM cells WHERE id=? AND session_id=?", (cell_id, session_id))
            if not row:
                raise ValueError("代码单元不存在")
            self.store.execute("UPDATE cells SET language=?,code=? WHERE id=?", (language, code, cell_id))
        else:
            cell_id = uid()
            count = self.store.one("SELECT COUNT(*) AS n FROM cells WHERE session_id=?", (session_id,))["n"]
            self.store.execute("INSERT INTO cells VALUES(?,?,?,?,?,?,?)",
                               (cell_id, project_id, session_id, language, code, count, now()))
        return self.store.one("SELECT * FROM cells WHERE id=?", (cell_id,))

    def environment(self):
        packages = {}
        for name in ("pandas", "numpy", "scipy", "matplotlib", "openpyxl", "jupyter_client", "ipykernel"):
            try:
                from importlib.metadata import version
                packages[name] = version(name)
            except Exception:
                packages[name] = None
        specs = []
        try:
            from jupyter_client.kernelspec import KernelSpecManager
            specs = list(KernelSpecManager().find_kernel_specs())
        except ImportError:
            pass
        config = self.store.setting("config", {})
        return {"python": python_executable(config), "version": sys.version.split()[0], "platform": sys.platform,
                "bundled_runtime": frozen(), "default_data_dir": str(default_data_dir()),
                "packages": packages, "kernels": specs,
                "rscript": config.get("rscript_path") or shutil.which("Rscript"),
                "languages": environments(config),
                "credential_storage": "Windows DPAPI 加密" if os.name == "nt" else "仅本次进程内存"}

    def _bootstrap(self, project_id=None):
        projects = self.store.all("SELECT * FROM projects ORDER BY created")
        if not project_id or not any(p["id"] == project_id for p in projects):
            project_id = projects[0]["id"] if projects else None
        sessions = self.store.all("SELECT * FROM sessions WHERE project_id=? ORDER BY created", (project_id,))
        config = self.store.setting("config", {})
        return {"version": __version__, "projects": projects, "project_id": project_id, "sessions": sessions,
                "config": {**config, "has_key": bool(self.secrets.get())}, "templates": TEMPLATES,
                "runs": self.store.runs(project_id) if project_id else [],
                "environment": self.environment()}

    def _retain(self, project_id, relative):
        project = self.project(project_id)
        info = identity(project["path"], relative)
        if info["bytes"] > MAX_FILE:
            raise ValueError("单份结果留存上限为 32 MiB")
        version_id = uid()
        dest = Path(project["path"]) / ".lumen" / "versions" / version_id / Path(relative).name
        dest.parent.mkdir(parents=True)
        shutil.copyfile(safe_path(project["path"], relative, True), dest)
        if sha256(dest) != info["sha256"]:
            raise ValueError("文件在保存过程中变化，请重新核对")
        self.store.execute("INSERT INTO artifact_versions VALUES(?,?,?,?,?,?)",
                           (version_id, project_id, relative, info["sha256"], str(dest), now()))
        return {"id": version_id, **info}

    def _compare(self, project_id, version_id):
        project = self.project(project_id)
        version = self.store.one("SELECT * FROM artifact_versions WHERE id=? AND project_id=?",
                                 (version_id, project_id))
        if not version:
            raise ValueError("留存版本不存在")
        current = safe_path(project["path"], version["path"])
        if not current.exists():
            return {"same": False, "current_missing": True, "version": version}
        result = {"same": sha256(current) == version["sha256"], "version": version,
                  "current_sha256": sha256(current)}
        if current.suffix.lower() in (".csv", ".tsv") and current.stat().st_size < 4_000_000:
            from .files import load_table
            previous, actual = load_table(version["stored_path"]), load_table(current)
            result.update({"old_shape": list(previous.shape), "new_shape": list(actual.shape),
                           "columns_equal": list(previous.columns) == list(actual.columns),
                           "exact_table_equal": previous.equals(actual)})
        return result

    def _reproduce(self, run_id):
        run = self.store.run(run_id)
        if run["status"] in ("queued", "running"):
            raise ValueError("请等待原运行结束")
        source = self.project(run["project_id"])
        for item in run["detail"]["inputs"]:
            if identity(source["path"], item["path"])["sha256"] != item["sha256"]:
                raise ValueError("输入文件已变化，无法按原输入重跑：" + item["path"])
        target = self.create_project("独立验证 · " + run["title"][:25],
                                     description="来源运行 " + run_id + "；新目录、独立解释器，复制已声明输入。")
        for item in run["detail"]["inputs"]:
            dest = safe_path(target["path"], item["path"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_path(source["path"], item["path"], True), dest)
        result = self.execution.submit(target["id"], target["session_id"], run["language"], run["code"],
                                       "独立重跑 · " + run["title"], inputs=[x["path"] for x in run["detail"]["inputs"]],
                                       kind="reproduction", independent=True)
        self.store.update_run(result["id"], origin_run_id=run_id,
                              validation_scope="独立进程执行；数值与科学结论的一致性需要另行比较")
        return {"project": target, "run": self.store.run(result["id"])}

    def _export(self, project_id, include_data=False):
        project = self.project(project_id)
        root = Path(project["path"])
        folder = root / ".lumen" / "exports"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / ("LUMEN-" + uid() + ".zip")
        runs = self.store.runs(project_id, 200)
        total, skipped = 0, []
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("README.md", "# LUMEN Science 项目交付\n\n"
                "此包包含项目文件、运行代码、环境和结果记录。运行通过不代表科学结论已核验。\n\n"
                "数据文件：" + ("已选择包含；受大小上限限制，缺失项见 manifest.json。" if include_data else
                              "默认不包含，请按 manifest.json 中的输入路径与指纹准备。") +
                "\n\n持续内核中的代码片段可能依赖前序变量。请优先运行自包含 scripts，或按运行记录整理顺序后独立验证。\n")
            for item in walk_files(root, 2500)["files"]:
                if not include_data and item["path"].startswith("data/"):
                    continue
                if item["bytes"] > MAX_FILE or total + item["bytes"] > 150 * 1024 * 1024:
                    skipped.append(item["path"])
                    continue
                archive.write(safe_path(root, item["path"], True), "project/" + item["path"])
                total += item["bytes"]
            for run in runs:
                detail = self.store.run(run["id"])
                archive.writestr("runs/" + run["id"] + "/record.json", dumps(detail))
                archive.writestr("runs/" + run["id"] + "/" + LANGUAGES.get(run["language"], {"file":"code.txt"})["file"],
                                 run["code"])
                snapshot = root / ".lumen" / "runs" / run["id"] / "artifacts"
                if snapshot.is_dir():
                    for base, _, names in os.walk(snapshot):
                        for name in names:
                            p = Path(base) / name
                            if p.is_symlink() or p.stat().st_size > MAX_FILE or total + p.stat().st_size > 200 * 1024 * 1024:
                                continue
                            archive.write(p, "runs/" + run["id"] + "/artifacts/" + p.relative_to(snapshot).as_posix())
                            total += p.stat().st_size
            archive.writestr("manifest.json", dumps({"project": project, "created": now(), "version": __version__,
                                                     "include_data": include_data, "skipped": skipped, "runs": len(runs)}))
        return {"path": target.relative_to(root).as_posix(), "bytes": target.stat().st_size, "skipped": skipped}

    def _pipeline_start(self, project_id, session_id, workflow_id):
        self.session(session_id, project_id)
        workflow = self.store.one("SELECT * FROM workflows WHERE id=? AND project_id=?", (workflow_id, project_id))
        if not workflow:
            raise ValueError("流程不存在")
        steps = json.loads(workflow["content"])
        job_id = uid()
        state = {"id": job_id, "project_id": project_id, "status": "running", "steps": [],
                 "cancel": threading.Event(), "active_run": None, "error": None}
        self.pipelines[job_id] = state
        def work():
            try:
                for step in steps:
                    if state["cancel"].is_set():
                        break
                    run = self.execution.submit(project_id, session_id, step["language"], step["code"],
                                                step.get("title", workflow["name"]), inputs=step.get("inputs", []),
                                                kind="pipeline")
                    state["steps"].append({"run_id": run["id"], "title": run["title"]})
                    state["active_run"] = run["id"]
                    while run["status"] in ("queued", "running"):
                        if state["cancel"].is_set():
                            self.execution.cancel(run["id"])
                        time.sleep(.2)
                        run = self.store.run(run["id"])
                    if run["status"] != "success":
                        raise ValueError("流程在步骤「" + run["title"] + "」停止：" + (run["detail"].get("error") or run["status"]))
                state["status"] = "cancelled" if state["cancel"].is_set() else "success"
            except Exception as exc:
                state["status"] = "cancelled" if state["cancel"].is_set() else "failed"
                state["error"] = str(exc)
            finally:
                state["active_run"] = None
        threading.Thread(target=work, daemon=True).start()
        return {k: v for k, v in state.items() if k != "cancel"}

    def dispatch(self, action, p):
        if action == "remote.list":
            return self.remote.list()
        if action == "remote.probe":
            return self.remote.probe(p["host"],p.get("port",22))
        if action == "remote.save":
            return self.remote.save(p)
        if action == "remote.test":
            return self.remote.test(p["profile_id"])
        if action == "remote.files":
            return self.remote.files(p["profile_id"],p.get("path",""))
        if action == "bootstrap":
            return self._bootstrap(p.get("project_id"))
        if action == "project.create":
            return self.create_project(p.get("name"), p.get("path", ""), p.get("description", ""))
        if action == "session.create":
            return self.create_session(p["project_id"], p.get("title", "新对话"))
        if action == "session.read":
            session = self.session(p["session_id"], p.get("project_id"))
            return {"session": session, "messages": self.store.messages(session["id"]),
                    "cells": self.store.all("SELECT * FROM cells WHERE session_id=? ORDER BY position", (session["id"],))}
        if action == "settings.get":
            return {**self.store.setting("config", {}), "has_key": bool(self.secrets.get()),
                    "environment": self.environment()}
        if action == "settings.save":
            allowed = ("api_base", "model", "protocol", "python_path", "rscript_path", "r_kernel", "tool_temp_dir")
            config = self.store.setting("config", {})
            for key in allowed:
                if key in p:
                    value = str(p[key]).strip()
                    if len(value) > 1000:
                        raise ValueError("配置项过长")
                    config[key] = value
            if config.get("protocol", "chat") not in ("chat", "responses"):
                raise ValueError("未知接口协议")
            for key in ("python_path", "rscript_path"):
                if config.get(key) and not Path(config[key]).is_file():
                    raise ValueError("解释器路径不存在：" + key)
            if config.get("tool_temp_dir"):
                from .scratch import compatible_base
                compatible_base(config["tool_temp_dir"])
            paths = dict(config.get("runner_paths", {}))
            for key,value in p.items():
                if key.startswith("runner_") and isinstance(value,str):
                    name=key[7:];value=value.strip()
                    if value and not Path(value).is_file():
                        raise ValueError("工具路径不存在："+name)
                    if value:
                        paths[name]=value
                    else:
                        paths.pop(name,None)
            config["runner_paths"]=paths
            if p.get("api_key"):
                self.secrets.set(str(p["api_key"]))
            self.store.set_setting("config", config)
            return {"saved": True, "has_key": bool(self.secrets.get())}
        if action == "settings.test":
            config = {**self.store.setting("config", {}), **{k: p[k] for k in ("api_base", "model", "protocol") if k in p}}
            answer, usage = ModelClient(config, p.get("api_key") or self.secrets.get()).request(
                [{"role": "user", "content": "Reply with OK."}])
            return {"connected": True, "reply": answer["content"][:300], "usage": usage}
        if action == "chat.start":
            return self.agent.start(p["project_id"], p["session_id"], p["text"],
                                    p.get("mode", "review"), p.get("auto", False))
        if action == "chat.status":
            return self.agent.view(p["job_id"])
        if action == "chat.approve":
            return self.agent.approve(p["job_id"], p.get("approved", False))
        if action == "chat.cancel":
            return self.agent.cancel(p["job_id"])
        if action == "environment":
            return self.environment()
        if action == "pipeline.status":
            state = self.pipelines.get(p["job_id"])
            if not state:
                raise ValueError("流程任务已结束或应用已重启")
            return {k: v for k, v in state.items() if k != "cancel"}
        if action == "pipeline.cancel":
            state = self.pipelines.get(p["job_id"])
            if not state:
                raise ValueError("找不到流程任务")
            state["cancel"].set()
            if state["active_run"]:
                self.execution.cancel(state["active_run"])
            return {"requested": True}
        # Every project-scoped operation validates the project first.
        if "project_id" not in p:
            raise ValueError("缺少项目")
        project_id = p["project_id"]
        project = self.project(project_id)
        root = project["path"]
        if action == "files.list":
            return walk_files(root)
        if action == "remote.execute":
            return self.remote.execute(project_id,p["profile_id"],p["command"],p.get("timeout",300))
        if action == "remote.transfer":
            return self.remote.transfer(project_id,p["profile_id"],p["direction"],p.get("local",""),p.get("remote",""))
        if action == "files.read":
            return read_text(root, p["path"])
        if action == "files.save":
            return write_text(root, p["path"], p["text"], bool(p.get("overwrite", False)))
        if action == "files.import":
            return import_file(root, p["name"], p["content"])
        if action == "data.preview":
            return table_preview(root, p["path"], p.get("sheet"))
        if action == "cell.save":
            return self.save_cell(project_id, p["session_id"], p["language"], p["code"], p.get("cell_id"))
        if action == "cell.run":
            cell = self.save_cell(project_id, p["session_id"], p["language"], p["code"], p.get("cell_id"))
            return self.execution.submit(project_id, p["session_id"], cell["language"], cell["code"],
                                          p.get("title", "Notebook 单元"), cell["id"], p.get("inputs", []))
        if action == "notebook.export":
            self.session(p["session_id"],project_id)
            cells=self.store.all("SELECT * FROM cells WHERE session_id=? ORDER BY position",(p["session_id"],))
            history=self.store.runs(project_id,200)
            exported=[]
            for cell in cells:
                run=next((r for r in history if r["cell_id"]==cell["id"]),None)
                cell_outputs=[]
                if run:
                    record=self.store.run(run["id"])
                    for item in record["detail"]["outputs"]:
                        if item["type"]=="image":
                            snapshot=Path(root)/".lumen"/"runs"/run["id"]/"artifacts"/item["path"]
                            if snapshot.is_file():
                                cell_outputs.append({"output_type":"display_data","metadata":{},"data":{
                                    "image/jpeg" if snapshot.suffix.lower() in (".jpg",".jpeg") else "image/png":
                                    base64.b64encode(snapshot.read_bytes()).decode()}})
                        elif item["type"] in ("stream","result","notice","error"):
                            cell_outputs.append({"output_type":"stream","name":"stderr" if item["type"]=="error" else "stdout",
                                                 "text":item.get("text","")})
                exported.append({"id":cell["id"],"cell_type":"code","execution_count":None,"metadata":{"lumen_language":cell["language"],
                    "lumen_run_id":run["id"] if run else None},"source":cell["code"],"outputs":cell_outputs})
            languages={cell["language"] for cell in cells}
            metadata={"lumen":{"mixed_language":len(languages)>1,"note":"混合语言单元使用 lumen_language 元数据标记；通用 Jupyter 需要切换匹配内核。"}}
            if languages<= {"python"}:
                metadata["kernelspec"]={"display_name":"Python 3","language":"python","name":"python3"}
            target=safe_path(root,"reports/notebook-"+uid()+".ipynb")
            target.write_text(dumps({"nbformat":4,"nbformat_minor":5,"metadata":metadata,"cells":exported}),encoding="utf-8")
            return {"path":target.relative_to(Path(root)).as_posix()}
        if action == "kernel.variables":
            self.session(p["session_id"], project_id)
            return self.execution.variables(project_id, p["session_id"], p.get("language", "python"))
        if action == "runs.list":
            return self.store.runs(project_id)
        if action in ("run.read", "run.cancel", "run.reproduce"):
            run = self.store.run(p["run_id"])
            if run["project_id"] != project_id:
                raise ValueError("运行不属于当前项目")
            if action == "run.read":
                return run
            if action == "run.cancel":
                if run["detail"].get("kind")=="remote":
                    event=self.remote.jobs.get(run["id"])
                    if event:event.set()
                    return {"requested":bool(event)}
                return self.execution.cancel(run["id"])
            return self._reproduce(run["id"])
        if action == "workflow.run":
            self.session(p["session_id"], project_id)
            safe_path(root, p["path"], True)
            code = build_workflow(p["template_id"], p["path"], p.get("parameters"), p.get("sheet"))
            name = next(t["name"] for t in TEMPLATES if t["id"] == p["template_id"])
            script = "scripts/" + p["template_id"] + "-" + uid() + ".py"
            write_text(root, script, code)
            run = self.execution.submit(project_id, p["session_id"], "python", code, name,
                                         inputs=[p["path"]], kind="workflow", independent=True)
            self.store.update_run(run["id"], script_path=script)
            return self.store.run(run["id"])
        if action == "pipeline.save":
            steps = p.get("steps")
            if not isinstance(steps, list) or not 1 <= len(steps) <= 30:
                raise ValueError("流程需要1–30个步骤")
            for step in steps:
                if step.get("language") not in LANGUAGES or not isinstance(step.get("code"), str) or len(step["code"]) > 200_000:
                    raise ValueError("流程步骤格式无效")
            workflow_id = uid()
            self.store.execute("INSERT INTO workflows VALUES(?,?,?,?,?)",
                               (workflow_id, project_id, str(p.get("name", "分析流程"))[:100], dumps(steps), now()))
            return {"id": workflow_id}
        if action == "pipeline.list":
            return self.store.all("SELECT * FROM workflows WHERE project_id=? ORDER BY created DESC", (project_id,))
        if action == "pipeline.start":
            return self._pipeline_start(project_id, p["session_id"], p["workflow_id"])
        if action == "artifacts.list":
            files = walk_files(root)["files"]
            result = [f for f in files if f["path"].startswith(("outputs/", "reports/"))]
            versions = self.store.all("SELECT id,path,sha256,created FROM artifact_versions WHERE project_id=? ORDER BY created DESC",
                                       (project_id,))
            return {"files": sorted(result, key=lambda x: x["modified"], reverse=True), "versions": versions}
        if action == "artifact.retain":
            return self._retain(project_id, p["path"])
        if action == "artifact.compare":
            return self._compare(project_id, p["version_id"])
        if action == "literature.search":
            records = literature.search(p["query"], p.get("source", "crossref"), p.get("limit", 8))
            search_id = uid()
            self.reference_searches[search_id] = {"project_id": project_id, "records": records}
            while len(self.reference_searches) > 80:
                self.reference_searches.pop(next(iter(self.reference_searches)))
            return {"search_id": search_id, "records": records}
        if action == "literature.save":
            lookup = self.reference_searches.get(p["search_id"])
            if not lookup or lookup["project_id"] != project_id:
                raise ValueError("检索结果过期，请重新检索")
            index = int(p["index"])
            if not 0 <= index < len(lookup["records"]):
                raise ValueError("记录索引无效")
            record = lookup["records"][index]
            reference_id = uid()
            self.store.execute("INSERT OR IGNORE INTO references_library VALUES(?,?,?,?,?)",
                               (reference_id, project_id, record["doi"] or record["url"], dumps(record), now()))
            return {"saved": True}
        if action == "literature.list":
            return [json.loads(r["content"]) for r in self.store.all(
                "SELECT content FROM references_library WHERE project_id=? ORDER BY created DESC", (project_id,))]
        if action == "literature.export":
            refs = self.dispatch("literature.list", {"project_id": project_id})
            relative = "reports/references-" + uid() + ".bib"
            return write_text(root, relative, literature.bibtex(refs))
        if action == "report.generate":
            runs = self.store.runs(project_id, 80)
            refs = self.dispatch("literature.list", {"project_id": project_id})
            text = "# " + project["name"] + " · 分析记录\n\n生成时间：" + now() + "\n\n"
            text += "## 研究目标\n\n" + (project["description"] or "待补充研究目标与实验设计。") + "\n\n"
            text += "## 实际运行\n\n"
            for run in reversed(runs):
                record = self.store.run(run["id"])
                text += "### " + run["title"] + "\n\n"
                text += "- 运行：" + run["id"] + "\n- 状态：" + run["status"] + "\n"
                text += "- 执行方式：" + record["detail"].get("execution_mode", "未记录") + "\n"
                for item in record["detail"]["inputs"]:
                    text += "- 声明输入：" + item["path"] + "；SHA-256：" + item["sha256"] + "\n"
                for item in run["artifacts"]:
                    relative = "../" + item["path"]
                    text += ("\n![" + Path(item["path"]).name + "](" + relative + ")\n" if
                             Path(item["path"]).suffix.lower() in (".png", ".jpg", ".jpeg") else
                             "\n[" + item["path"] + "](" + relative + ")\n")
                text += "\n"
            text += "## 已保存文献\n\n" + "\n".join(
                "- " + r["title"] + "；" + str(r.get("year") or "年份未提供") + "；" + r["url"] for r in refs)
            text += "\n\n## 核查范围\n\n运行状态来自实际执行记录。声明输入不证明完整捕获动态依赖；图表链接指向当前项目文件，"
            text += "原运行快照位于交付包的 runs 目录。此报告未自动核验科学结论。\n"
            relative = "reports/analysis-" + uid() + ".md"
            write_text(root, relative, text)
            return {"path": relative, "text": text}
        if action == "project.export":
            return self._export(project_id, bool(p.get("include_data", False)))
        raise ValueError("未知操作：" + action)
