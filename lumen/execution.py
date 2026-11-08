from __future__ import annotations

import ast
import base64
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from contextlib import nullcontext
from pathlib import Path

from .files import changed_outputs, identity, output_snapshot, safe_path, sha256
from .store import now
from .runners import LANGUAGES, plan, resolve_tool
from .scratch import compiler_workspace
from .runtime import python_executable, kernel_command


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


class Execution:
    def __init__(self, store, project_getter):
        self.store = store
        self.project_getter = project_getter
        self.kernels = {}
        self.guard = threading.RLock()
        self.cancel_flags = {}
        self.active = {}
        self.processes = {}
        self.project_locks = {}
        self.threads = []
        self.closed = False

    def submit(self, project_id, session_id, language, code, title="代码运行", cell_id=None,
               inputs=None, kind="cell", independent=False, timeout=300):
        if language not in LANGUAGES:
            raise ValueError("请选择支持的执行语言")
        if not isinstance(code, str) or not code.strip() or len(code) > 200_000:
            raise ValueError("代码为空或超过 200,000 字符")
        project = self.project_getter(project_id)
        root = Path(project["path"])
        declared = [identity(root, p) for p in (inputs or [])[:30]]
        run_id = self.store.new_run(project_id, session_id, language, code, title, cell_id,
                                    inputs=declared, kind=kind, independent=independent,
                                    environment={}, provenance_scope="声明的输入文件；动态读取及已有内核变量未完整捕获")
        run_dir = root / ".lumen" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / LANGUAGES[language]["file"]).write_text(code, encoding="utf-8")
        event = threading.Event()
        self.cancel_flags[run_id] = event
        thread = threading.Thread(target=self._work,
                                  args=(run_id, project, session_id, language, code, event, independent, timeout),
                                  daemon=True, name="lumen-run-" + run_id)
        self.threads.append(thread)
        thread.start()
        return self.store.run(run_id)

    def _create_kernel(self, key, root, language):
        from jupyter_client import KernelManager
        from jupyter_client.kernelspec import KernelSpecManager
        settings = self.store.setting("config", {})
        specs = KernelSpecManager().find_kernel_specs()
        if language == "R":
            name = settings.get("r_kernel") or next((n for n in specs if n.lower() in ("ir", "r")), "")
            if not name:
                raise ValueError("尚未找到 R 内核。请安装 R 和 IRkernel，或在设置中配置 Rscript 使用独立运行。")
        else:
            name = "python3"
        km = KernelManager(kernel_name=name)
        if language == "python":
            interpreter = python_executable(settings)
            if not Path(interpreter).is_file():
                raise ValueError("Python 解释器路径不存在")
            km.kernel_spec.argv = kernel_command(settings)
        runtime = root / ".lumen" / "kernels"
        runtime.mkdir(parents=True, exist_ok=True)
        km.connection_file = str(runtime / ("kernel-" + key.replace(":", "-") + ".json"))
        launch_options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        with (runtime / ("kernel-" + key.replace(":", "-") + ".log")).open("ab") as log:
            km.start_kernel(cwd=str(root), env={**os.environ, "MPLBACKEND": "module://matplotlib_inline.backend_inline"},
                            stdout=log, stderr=log, **launch_options)
        client = km.blocking_client()
        client.start_channels()
        try:
            client.wait_for_ready(timeout=35)
        except Exception:
            client.stop_channels()
            km.shutdown_kernel(now=True)
            raise ValueError("计算内核启动失败；请确认该 Python 环境已安装 ipykernel，R 环境已安装 IRkernel。")
        entry = {"manager": km, "client": client, "lock": threading.Lock(),
                 "language": language, "started": now(), "key": key}
        self.kernels[key] = entry
        return entry

    def _kernel(self, key, root, language):
        with self.guard:
            entry = self.kernels.get(key)
            if entry and entry["manager"].is_alive():
                return entry
            if entry:
                entry["client"].stop_channels()
            return self._create_kernel(key, root, language)

    def _expression(self, entry, expression, timeout=8):
        client = entry["client"]
        msg_id = client.execute("", silent=True, store_history=False,
                                user_expressions={"lumen": expression})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                msg = client.get_shell_msg(timeout=0.4)
            except queue.Empty:
                continue
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            result = msg["content"].get("user_expressions", {}).get("lumen", {})
            if result.get("status") != "ok":
                return {}
            text = result.get("data", {}).get("text/plain", "'{}'")
            return json.loads(ast.literal_eval(text))
        return {}

    def _environment(self, entry):
        return self._expression(entry,
            "__import__('json').dumps({'executable':__import__('sys').executable,"
            "'python':__import__('sys').version,'platform':__import__('platform').platform(),"
            "'packages':{n:__import__('importlib.metadata',fromlist=['version']).version(n) "
            "for n in ['ipykernel','numpy','pandas','scipy','matplotlib'] "
            "if __import__('importlib.util',fromlist=['find_spec']).find_spec(n)}})") if entry["language"] == "python" else {
                "language": "R", "kernel": entry["manager"].kernel_name}

    def _work(self, run_id, project, session_id, language, code, event, independent, timeout):
        start = time.monotonic()
        root = Path(project["path"])
        entry = None
        locked = False
        before = None
        project_lock = None
        project_locked = False
        status = "failed"
        error = None
        try:
            if self.closed:
                raise ValueError("应用正在关闭")
            if event.is_set():
                status = "cancelled"
                self.store.update_run(run_id, "cancelled")
                return
            with self.guard:
                project_lock = self.project_locks.setdefault(project["id"], threading.Lock())
            while not project_lock.acquire(timeout=.1):
                if event.is_set():
                    status = "cancelled"
                    return
            project_locked = True
            config = self.store.setting("config", {})
            if independent or language not in ("python", "R") or (language == "R" and not config.get("r_kernel") and resolve_tool("Rscript",config)):
                self.store.update_run(run_id, "running")
                before = output_snapshot(root)
                result = self._independent(run_id, root, language, code, event, timeout)
                status, error = result["status"], result.get("error")
                self.store.update_run(run_id, environment=result["environment"],
                                      execution_mode="独立进程（编译型语言先编译，变量不跨运行保留）")
            else:
                key = project["id"] + ":" + (session_id or "notebook") + ":" + language
                entry = self._kernel(key, root, language)
                while not entry["lock"].acquire(timeout=0.1):
                    if event.is_set():
                        status = "cancelled"
                        self.store.update_run(run_id, "cancelled")
                        return
                locked = True
                if event.is_set():
                    status = "cancelled"
                    self.store.update_run(run_id, "cancelled")
                    return
                self.active[run_id] = entry
                self.store.update_run(run_id, "running", environment=self._environment(entry),
                                      execution_mode="持续内核", kernel_id=entry["key"])
                before = output_snapshot(root)
                client = entry["client"]
                msg_id = client.execute(code, stop_on_error=True, allow_stdin=False)
                deadline = time.monotonic() + min(max(int(timeout), 5), 3600)
                interrupted_at = None
                failed = False
                while True:
                    if event.is_set() and interrupted_at is None:
                        entry["manager"].interrupt_kernel()
                        interrupted_at = time.monotonic()
                    if time.monotonic() > deadline and interrupted_at is None:
                        error = "运行超时，已发送中断"
                        event.set()
                    if interrupted_at and time.monotonic() - interrupted_at > 8:
                        entry["manager"].shutdown_kernel(now=True)
                        with self.guard:
                            self.kernels.pop(key, None)
                        error = "计算未响应中断，本次内核已停止；该内核变量已清空"
                        break
                    if not entry["manager"].is_alive():
                        error = error or "计算内核意外退出"
                        break
                    try:
                        msg = client.get_iopub_msg(timeout=0.2)
                    except queue.Empty:
                        continue
                    if msg.get("parent_header", {}).get("msg_id") != msg_id:
                        continue
                    kind, content = msg["header"]["msg_type"], msg["content"]
                    if kind == "stream":
                        self.store.append_output(run_id, {"type": "stream", "name": content.get("name"),
                                                          "text": content.get("text", "")[:150_000]})
                    elif kind == "error":
                        failed = True
                        error = content.get("ename", "") + ": " + content.get("evalue", "")
                        self.store.append_output(run_id, {"type": "error", "text": "\n".join(content.get("traceback", []))})
                    elif kind in ("execute_result", "display_data", "update_display_data"):
                        data = content.get("data", {})
                        if "image/png" in data:
                            self._save_image(root, run_id, data["image/png"])
                        elif "image/jpeg" in data:
                            self._save_image(root, run_id, data["image/jpeg"], ".jpg")
                        if "text/plain" in data:
                            self.store.append_output(run_id, {"type": "result", "text": str(data["text/plain"])[:80_000]})
                    elif kind == "status" and content.get("execution_state") == "idle":
                        status = "cancelled" if event.is_set() else "failed" if failed else "success"
                        break
                if event.is_set():
                    status = "cancelled"
                elif error:
                    status = "failed"
        except Exception as exc:
            error = str(exc)
            status = "cancelled" if event.is_set() else "failed"
            self.store.append_output(run_id, {"type": "error", "text": error})
        finally:
            self.active.pop(run_id, None)
            try:
                artifacts = changed_outputs(root, before) if before is not None else []
                run_dir = root / ".lumen" / "runs" / run_id
                # Preserve exact result bytes; current files may later change.
                for item in artifacts:
                    src = safe_path(root, item["path"], True)
                    dest = run_dir / "artifacts" / item["path"]
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dest)
                    if sha256(dest) != item["sha256"]:
                        raise ValueError("结果在保存期间发生变化，无法绑定来源")
                detail = {"duration": round(time.monotonic() - start, 3),
                          "artifacts": artifacts, "error": error}
                self.store.update_run(run_id, status, **detail)
                (run_dir / "manifest.json").write_text(
                    json.dumps(self.store.run(run_id), ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as exc:
                self.store.update_run(run_id, "failed", error="保存运行记录失败：" + str(exc))
            if locked:
                entry["lock"].release()
            if project_locked:
                project_lock.release()
            self.cancel_flags.pop(run_id, None)

    def _save_image(self, root, run_id, encoded, suffix=".png"):
        raw = base64.b64decode(encoded)
        if len(raw) > 20 * 1024 * 1024:
            self.store.append_output(run_id, {"type": "notice", "text": "图片超过 20 MiB，未保存。"})
            return
        folder = root / "outputs" / run_id
        folder.mkdir(parents=True, exist_ok=True)
        index = len(list(folder.glob("figure-*"))) + 1
        target = folder / ("figure-" + str(index) + suffix)
        target.write_bytes(raw)
        self.store.append_output(run_id, {"type": "image", "path": target.relative_to(root).as_posix()})

    def _independent(self, run_id, root, language, code, event, timeout):
        config = self.store.setting("config", {})
        run_dir = root / ".lumen" / "runs" / run_id
        staged = os.name == "nt" and language in ("R", "c", "cpp", "java", "go", "rust")
        context = compiler_workspace(config, run_dir / LANGUAGES[language]["file"]) if staged else nullcontext(run_dir)
        with context as work_dir:
            commands = plan(language, work_dir, config)
            temp = work_dir / "temp"
            temp.mkdir(exist_ok=True)
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg",
                   "TMP": str(temp), "TEMP": str(temp), "TMPDIR": str(temp),
                   "GOCACHE": str(temp / "go-cache"), "CARGO_TARGET_DIR": str(temp / "cargo"),
                   "ZIG_GLOBAL_CACHE_DIR":str(self.store.root/"compiler-cache"/"zig"),
                   "ZIG_LOCAL_CACHE_DIR":str(temp/"zig-cache")}
            if language=="R" and os.name=="nt":
                env.pop("LC_ALL",None)
            result = None
            for index, args in enumerate(commands):
                if event.is_set():
                    return {"status": "cancelled", "environment": {"language": language}}
                self.store.append_output(run_id, {"type": "notice", "text":
                    ("编译阶段" if len(commands)>1 and index==0 else "执行阶段") + " · " + Path(args[0]).name})
                # Keep project cwd unchanged even when compiler source/temporary files are staged.
                result = self._process(run_id, root, args, env, event, timeout)
                if result["status"] != "success":
                    break
            result["environment"] = {"language": language, "commands": commands,
                                     "platform": sys.platform, "working_directory": str(root),
                                     "compiler_staging": staged, **result.get("environment", {})}
            return result

    def _process(self, run_id, root, args, env, event, timeout):
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(args, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=flags, start_new_session=os.name != "nt")
        self.processes[run_id] = process
        events = queue.Queue()
        def reader(stream, name):
            try:
                for chunk in iter(lambda: stream.read1(2048), b""):
                    events.put((name, chunk.decode("utf-8", "replace")))
            finally:
                stream.close()
        for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            threading.Thread(target=reader, args=(stream, name), daemon=True).start()
        deadline = time.monotonic() + min(max(int(timeout), 5), 3600)
        timed_out = False
        try:
            while process.poll() is None:
                if event.is_set() or time.monotonic() > deadline:
                    timed_out = not event.is_set()
                    stop_process(process)
                    break
                try:
                    name, text = events.get(timeout=0.1)
                    self.store.append_output(run_id, {"type": "stream", "name": name, "text": text})
                except queue.Empty:
                    pass
            process.wait(timeout=10)
            time.sleep(0.1)
            while not events.empty():
                name, text = events.get_nowait()
                self.store.append_output(run_id, {"type": "stream", "name": name, "text": text})
            return {"status": "cancelled" if event.is_set() else "failed" if timed_out or process.returncode else "success",
                    "error": "独立进程运行超时" if timed_out else
                    ("退出码 " + str(process.returncode)) if process.returncode and not event.is_set() else None,
                    "environment": {"executable": args[0], "exit_code": process.returncode}}
        finally:
            self.processes.pop(run_id, None)
            if process.poll() is None:
                stop_process(process)

    def cancel(self, run_id):
        self.store.run(run_id)
        flag = self.cancel_flags.get(run_id)
        if flag:
            flag.set()
        return {"requested": bool(flag), "message": "已请求停止；以运行记录的最终状态为准"}

    def variables(self, project_id, session_id, language="python"):
        key = project_id + ":" + (session_id or "notebook") + ":" + language
        entry = self.kernels.get(key)
        if not entry:
            return {"variables": [], "state": "not_started"}
        if not entry["lock"].acquire(blocking=False):
            return {"variables": [], "state": "busy"}
        try:
            if language != "python":
                return {"variables": [], "state": "unsupported", "message": "R 变量可使用 ls() / str() 查看"}
            result = self._expression(entry,
                "__import__('json').dumps([{'name':n,'type':type(v).__name__,"
                "'shape':str(getattr(v,'shape','')),'preview':str(v)[:160] "
                "if isinstance(v,(str,int,float,bool,list,tuple,dict)) else ''} "
                "for n,v in list(globals().items()) if not n.startswith('_') "
                "and n not in ['In','Out','get_ipython','exit','quit','open']][:100],default=str)")
            return {"variables": result if isinstance(result, list) else [], "state": "idle"}
        finally:
            entry["lock"].release()

    def shutdown(self):
        self.closed = True
        for flag in list(self.cancel_flags.values()):
            flag.set()
        for process in list(self.processes.values()):
            try:
                stop_process(process)
            except Exception:
                pass
        for thread in list(self.threads):
            if thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=12)
        with self.guard:
            for entry in list(self.kernels.values()):
                try:
                    entry["client"].stop_channels()
                    entry["manager"].shutdown_kernel(now=True)
                except Exception:
                    pass
            self.kernels.clear()
