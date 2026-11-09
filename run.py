"""Launch the local workbench. No package manager or cloud account is required."""
from __future__ import annotations

import argparse
import http.client
import json
import logging
import os
import re
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from lumen.app import Workbench
from lumen.server import LocalServer
from lumen.runtime import default_data_dir, frozen, resources


def open_window(url, browser=False):
    if os.name == "nt" and not browser:
        candidates = [Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) /
                      "Microsoft/Edge/Application/msedge.exe",
                      Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) /
                      "Google/Chrome/Application/chrome.exe"]
        for browser in candidates:
            if browser.is_file():
                subprocess.Popen([str(browser), "--app=" + url, "--window-size=1440,960"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    if not webbrowser.open(url):
        raise RuntimeError("无法打开浏览器。请检查 Windows 的默认浏览器设置。")


def service_is_ready(url, instance_id):
    match = re.fullmatch(r"http://127\.0\.0\.1:([0-9]{1,5})", url)
    if not match or not 1 <= int(match[1]) <= 65535:
        return False
    connection = http.client.HTTPConnection("127.0.0.1", int(match[1]), timeout=3)
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        if response.status != 200:
            return False
        health = json.loads(response.read(4096))
        return health["service"] == "lumen-science" and health["instance_id"] == instance_id
    except (OSError, http.client.HTTPException, ValueError, KeyError, TypeError):
        return False
    finally:
        connection.close()


def existing_url(info_file):
    try:
        info = json.loads(info_file.read_text(encoding="utf-8"))
        url = info["url"]
        if service_is_ready(url, info["instance_id"]):
            return url
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def desktop_window(url, root):
    log = logging.getLogger("pywebview")
    handler = logging.FileHandler(root / "desktop-startup.log", mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    arguments_key = "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"
    previous_arguments = os.environ.get(arguments_key)
    try:
        import webview
        webview.settings["ALLOW_DOWNLOADS"] = True
        window = webview.create_window("LUMEN Science", url, width=1440, height=960,
                                      min_size=(1000, 700))
        finished = threading.Event()
        failed = threading.Event()

        def lumen_ready():
            finished.set()

        def check_startup():
            if os.name == "nt" and webview.renderer != "edgechromium":
                reason = "WebView2 unavailable (renderer: %s)" % webview.renderer
            elif finished.wait(25):
                return
            else:
                reason = "The workbench page did not finish loading within 25 seconds."
            if window.events.closed.is_set():
                return
            log.error(reason)
            failed.set()
            window.destroy()

        window.expose(lumen_ready)
        window.events.closed += finished.set
        if os.name == "nt":
            # Only this process's embedded browser serves the local workbench UI.
            os.environ[arguments_key] = ((previous_arguments or "") + " --no-proxy-server").strip()
        webview.start(check_startup, gui="edgechromium" if os.name == "nt" else None,
                      private_mode=False, storage_path=str(root / "webview"))
        if failed.is_set():
            return False
        if not finished.is_set() and not window.events.closed.is_set():
            log.error("The desktop window closed before initialization.")
            return False
        return True
    except Exception:
        log.exception("Could not start the desktop window.")
        return False
    finally:
        if os.name == "nt":
            if previous_arguments is None:
                os.environ.pop(arguments_key, None)
            else:
                os.environ[arguments_key] = previous_arguments
        log.removeHandler(handler)
        handler.close()


def offer_browser(root):
    if os.name != "nt":
        return True
    import ctypes

    message = ("LUMEN 已启动本机服务，但桌面窗口未能加载。\n\n"
               "是否改用默认浏览器打开工作台？\n\n"
               f"诊断记录：{root / 'desktop-startup.log'}")
    return ctypes.windll.user32.MessageBoxW(None, message, "LUMEN Science", 0x34) == 6


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=str(default_data_dir()))
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--browser", action="store_true", help="Use an external browser instead of the desktop window")
    args = parser.parse_args()
    root = Path(args.data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    info_file = root / "server.json"
    wants_desktop = not args.no_browser and frozen() and not args.browser
    url = existing_url(info_file)
    if url:
        if wants_desktop:
            if not desktop_window(url, root) and offer_browser(root):
                open_window(url, browser=True)
        elif not args.no_browser:
            open_window(url, browser=args.browser)
        if sys.stdout:
            print(url, flush=True)
        return
    app = Workbench(root)
    try:
        server = LocalServer(("127.0.0.1", args.port), app, resources() / "web")
    except OSError:
        server = LocalServer(("127.0.0.1", 0), app, resources() / "web")
    url = "http://127.0.0.1:" + str(server.server_port)
    info_file.write_text(json.dumps({"url": url, "instance_id": server.instance_id, "pid": os.getpid()}),
                         encoding="utf-8")
    if sys.stdout:
        print("LUMEN Science  " + url, flush=True)
    try:
        if args.no_browser:
            server.serve_forever(poll_interval=.3)
        else:
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .3}, daemon=True)
            thread.start()
            try:
                if not service_is_ready(url, server.instance_id):
                    raise ConnectionError(f"工作台无法连接本机服务 {url}。请检查代理或安全软件的连接记录。")
                if wants_desktop and (desktop_window(url, root) or not offer_browser(root)):
                    return
                open_window(url, browser=args.browser or wants_desktop)
                thread.join()
            finally:
                server.shutdown()
                thread.join(timeout=5)
    except KeyboardInterrupt:
        pass
    finally:
        for job in app.agent.jobs.values():
            job["cancel"].set()
            job["decision"].set()
        app.execution.shutdown()
        server.server_close()
        try:
            if json.loads(info_file.read_text(encoding="utf-8")).get("instance_id") == server.instance_id:
                info_file.unlink()
        except (OSError, ValueError):
            pass


if __name__ == "__main__":
    main()
