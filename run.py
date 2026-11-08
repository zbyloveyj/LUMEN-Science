"""Launch the local workbench. No package manager or cloud account is required."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path

from lumen.app import Workbench
from lumen.server import LocalServer


def open_window(url):
    if os.name == "nt":
        candidates = [Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) /
                      "Microsoft/Edge/Application/msedge.exe",
                      Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) /
                      "Google/Chrome/Application/chrome.exe"]
        for browser in candidates:
            if browser.is_file():
                subprocess.Popen([str(browser), "--app=" + url, "--window-size=1440,960"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=str(Path(__file__).parent / ".state"))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    root = Path(args.data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    info_file = root / "server.json"
    if info_file.exists():
        try:
            info = json.loads(info_file.read_text(encoding="utf-8"))
            with urllib.request.urlopen(info["url"] + "/health", timeout=2) as response:
                health = json.load(response)
            if health.get("instance_id") == info.get("instance_id") and health.get("service") == "lumen-science":
                if not args.no_browser:
                    open_window(info["url"])
                print(info["url"], flush=True)
                return
        except Exception:
            pass
    app = Workbench(root)
    try:
        server = LocalServer(("127.0.0.1", args.port), app, Path(__file__).parent / "web")
    except OSError:
        server = LocalServer(("127.0.0.1", 0), app, Path(__file__).parent / "web")
    url = "http://127.0.0.1:" + str(server.server_port)
    info_file.write_text(json.dumps({"url": url, "instance_id": server.instance_id, "pid": os.getpid()}),
                         encoding="utf-8")
    print("LUMEN Science  " + url, flush=True)
    if not args.no_browser:
        open_window(url)
    try:
        server.serve_forever(poll_interval=.3)
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
