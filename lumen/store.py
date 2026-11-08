from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def uid():
    return uuid.uuid4().hex[:16]


def dumps(value):
    return json.dumps(value, ensure_ascii=False, default=str, allow_nan=False)


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "workbench.sqlite3"
        self.lock = threading.RLock()
        with self.connection() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS projects(
                id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL DEFAULT '', created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL,
                created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                role TEXT NOT NULL, content TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cells(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, session_id TEXT NOT NULL,
                language TEXT NOT NULL, code TEXT NOT NULL, position INTEGER NOT NULL,
                created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, session_id TEXT,
                cell_id TEXT, language TEXT NOT NULL, code TEXT NOT NULL,
                status TEXT NOT NULL, title TEXT NOT NULL, created TEXT NOT NULL,
                finished TEXT, detail TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS runs_project ON runs(project_id,created);
            CREATE TABLE IF NOT EXISTS references_library(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, doi TEXT NOT NULL,
                content TEXT NOT NULL, created TEXT NOT NULL,
                UNIQUE(project_id,doi));
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS workflows(
                id TEXT PRIMARY KEY,project_id TEXT NOT NULL,name TEXT NOT NULL,
                content TEXT NOT NULL,created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifact_versions(
                id TEXT PRIMARY KEY,project_id TEXT NOT NULL,path TEXT NOT NULL,
                sha256 TEXT NOT NULL,stored_path TEXT NOT NULL,created TEXT NOT NULL);
            """)
            # A process restart cannot imply an old computation is still running.
            for row in db.execute("SELECT id,detail FROM runs WHERE status IN ('queued','running')"):
                detail = json.loads(row["detail"])
                detail["error"] = "应用上次退出时任务未完成；计算状态未知，请核查输出后重新运行。"
                db.execute("UPDATE runs SET status='interrupted',finished=?,detail=? WHERE id=?",
                           (now(), dumps(detail), row["id"]))

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def all(self, sql, args=()):
        with self.connection() as db:
            return [dict(r) for r in db.execute(sql, args)]

    def one(self, sql, args=()):
        rows = self.all(sql, args)
        return rows[0] if rows else None

    def execute(self, sql, args=()):
        with self.lock, self.connection() as db:
            db.execute(sql, args)

    def setting(self, key, default=None):
        row = self.one("SELECT value FROM settings WHERE key=?", (key,))
        return json.loads(row["value"]) if row else default

    def set_setting(self, key, value):
        self.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, dumps(value)))

    def message(self, session_id, role, content):
        self.execute("INSERT INTO messages(session_id,role,content,created) VALUES(?,?,?,?)",
                     (session_id, role, dumps(content), now()))

    def messages(self, session_id):
        rows = self.all("SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,))
        for row in rows:
            row["content"] = json.loads(row["content"])
        return rows

    def new_run(self, project_id, session_id, language, code, title, cell_id=None, **detail):
        run_id = uid()
        value = {"outputs": [], "artifacts": [], "inputs": [], **detail}
        self.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                     (run_id, project_id, session_id, cell_id, language, code,
                      "queued", title, now(), None, dumps(value)))
        return run_id

    def run(self, run_id):
        row = self.one("SELECT * FROM runs WHERE id=?", (run_id,))
        if not row:
            raise ValueError("找不到这次运行")
        row["detail"] = json.loads(row["detail"])
        return row

    def update_run(self, run_id, status=None, **patch):
        with self.lock:
            row = self.run(run_id)
            row["detail"].update(patch)
            final = status in ("success", "failed", "cancelled", "interrupted")
            self.execute("UPDATE runs SET status=?,finished=?,detail=? WHERE id=?",
                         (status or row["status"], now() if final else row["finished"],
                          dumps(row["detail"]), run_id))

    def append_output(self, run_id, output):
        with self.lock:
            run = self.run(run_id)
            outputs = run["detail"]["outputs"]
            size = sum(len(str(x)) for x in outputs)
            if size < 600_000 and len(outputs) < 300:
                outputs.append(output)
            elif not run["detail"].get("output_truncated"):
                outputs.append({"type": "notice", "text": "输出已达到界面上限；请缩小打印范围。"})
                run["detail"]["output_truncated"] = True
            self.update_run(run_id, **run["detail"])

    def runs(self, project_id, limit=80):
        rows = self.all("SELECT * FROM runs WHERE project_id=? ORDER BY created DESC LIMIT ?",
                        (project_id, max(1, min(int(limit), 200))))
        for row in rows:
            detail = json.loads(row.pop("detail"))
            row["artifacts"] = detail.get("artifacts", [])
            row["error"] = detail.get("error")
            row["duration"] = detail.get("duration")
            row["kind"] = detail.get("kind", "cell")
        return rows
