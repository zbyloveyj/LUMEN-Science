"""Desktop/worker entry point. Worker dispatch must precede window imports."""
from __future__ import annotations

import multiprocessing
import os
import runpy
import sys
from pathlib import Path

WORKER_MODE = len(sys.argv) > 1 and sys.argv[1] in ("--python-worker", "--kernel-worker")


def main():
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] == "--python-worker":
        sys.argv = sys.argv[2:]
        if not sys.argv:
            raise SystemExit("A script is required")
        script = str(Path(sys.argv[0]).resolve())
        sys.path[:0] = [str(Path(script).parent), os.getcwd()]
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        runpy.run_path(script, run_name="__main__")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--kernel-worker":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        sys.path.insert(0, os.getcwd())
        from ipykernel.kernelapp import IPKernelApp
        IPKernelApp.launch_instance()
        return
    from run import main as launch
    launch()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        from lumen.runtime import default_data_dir
        root = Path.cwd() / ".lumen" if WORKER_MODE else default_data_dir()
        root.mkdir(parents=True, exist_ok=True)
        (root / "startup-error.log").write_text(traceback.format_exc(), encoding="utf-8")
        if sys.__stderr__:
            traceback.print_exc(file=sys.__stderr__)
        if os.name == "nt" and not WORKER_MODE:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, "LUMEN 未能启动。错误记录：" + str(root / "startup-error.log"),
                                             "LUMEN Science", 0x10)
        raise SystemExit(1)
