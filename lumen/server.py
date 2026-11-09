from __future__ import annotations

import json
import mimetypes
import secrets
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .files import safe_path


UI_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, app, static):
        self.app = app
        self.static = Path(static).resolve()
        self.token = secrets.token_urlsafe(32)
        self.instance_id = secrets.token_hex(12)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "LUMEN-Science"

    def log_message(self, *args):
        pass

    def _headers(self, code, content_type, length, attachment=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                         "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
                         "object-src 'none'; base-uri 'none'; form-action 'self'")
        if attachment:
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(attachment))
        self.end_headers()

    def _host_ok(self):
        host = self.headers.get("Host", "")
        return host in ("127.0.0.1:" + str(self.server.server_port),
                        "localhost:" + str(self.server.server_port))

    def _json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False, default=str, allow_nan=False).encode("utf-8")
        self._headers(code, "application/json; charset=utf-8", len(raw))
        self.wfile.write(raw)

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "Host not allowed"})
        url = urllib.parse.urlparse(self.path)
        try:
            if url.path == "/health":
                return self._json(200, {"service": "lumen-science", "instance_id": self.server.instance_id})
            if url.path == "/file":
                q = urllib.parse.parse_qs(url.query)
                project = self.server.app.project(q["project"][0])
                path = safe_path(project["path"], q["path"][0], True)
                if not path.is_file():
                    raise ValueError("请选择普通文件")
                if path.stat().st_size > 200 * 1024 * 1024:
                    raise ValueError("文件超过本地预览或下载上限")
                mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
                # Never execute project HTML, SVG, scripts or user-provided active content.
                inline = path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf")
                self._headers(200, mime if inline else "application/octet-stream",
                              path.stat().st_size, path.name if not inline or q.get("download") else None)
                with path.open("rb") as source:
                    while chunk := source.read(256 * 1024):
                        self.wfile.write(chunk)
                return
            relative = "index.html" if url.path in ("/", "/index.html") else urllib.parse.unquote(url.path).lstrip("/")
            path = safe_path(self.server.static, relative, True)
            if not path.is_file():
                raise ValueError("页面不存在")
            raw = path.read_bytes()
            if relative == "index.html":
                raw = raw.replace(b"__LUMEN_TOKEN__", self.server.token.encode())
            mime = UI_CONTENT_TYPES.get(path.suffix.lower())
            self._headers(200, mime or mimetypes.guess_type(str(path))[0] or "application/octet-stream", len(raw))
            self.wfile.write(raw)
        except (ValueError, KeyError, OSError):
            self._json(404, {"error": "文件或页面不可用"})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if not self._host_ok() or not secrets.compare_digest(
                self.headers.get("X-Lumen-Token", ""), self.server.token):
            return self._json(403, {"ok": False, "error": "请从本机启动页面打开工作台"})
        origin = self.headers.get("Origin")
        if origin and origin not in ("http://127.0.0.1:" + str(self.server.server_port),
                                      "http://localhost:" + str(self.server.server_port)):
            return self._json(403, {"ok": False, "error": "来源不匹配"})
        if self.path != "/api":
            return self._json(404, {"ok": False, "error": "未知接口"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 46 * 1024 * 1024:
                raise ValueError("请求大小超过上限")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or not isinstance(body.get("params", {}), dict):
                raise ValueError("请求结构无效")
            if body.get("action") == "system.shutdown":
                self._json(200, {"ok": True, "data": {"stopping": True}})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            result = self.server.app.dispatch(body.get("action", ""), body.get("params", {}))
            self._json(200, {"ok": True, "data": result})
        except (ValueError, KeyError, FileExistsError, ImportError) as exc:
            message = "同名文件已存在；请使用新文件名" if isinstance(exc, FileExistsError) else str(exc)
            self._json(400, {"ok": False, "error": message})
        except Exception as exc:
            # Error type only; never log request bodies or credentials.
            self._json(500, {"ok": False, "error": "操作未完成：" + type(exc).__name__ + "。请检查配置或输入文件。"})
