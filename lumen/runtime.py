"""Paths and Python commands for both source and self-contained desktop builds."""
from __future__ import annotations

import errno
import os
import sys
from pathlib import Path


def try_lock_instance(lock):
    """Hold the workspace's single service lock until this file handle closes."""
    try:
        if os.name == "nt":
            import msvcrt

            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        if error.errno in (errno.EACCES, errno.EAGAIN):
            return False
        raise
    return True


def frozen():
    return bool(getattr(sys, "frozen", False))


def resources():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def default_data_dir():
    if not frozen():
        return resources() / ".state"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "LUMENScience"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/LUMENScience"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "lumen-science"


def uses_bundled_python(config):
    if not frozen():
        return False
    value = config.get("python_path")
    if not value:
        return True
    selected = Path(value).resolve()
    home = Path(sys.executable).resolve().parent
    return selected.parent == home and selected.name.lower() in ("lumenscience.exe", "lumen-runtime.exe", "lumenscience", "lumen-runtime")


def python_executable(config=None):
    configured = (config or {}).get("python_path")
    if configured and not uses_bundled_python(config or {}):
        return configured
    if frozen():
        name = "lumen-runtime.exe" if os.name == "nt" else "lumen-runtime"
        return str(Path(sys.executable).parent / name)
    return sys.executable


def python_command(config, script, *args):
    executable = python_executable(config)
    if uses_bundled_python(config):
        return [executable, "--python-worker", str(script), *map(str, args)]
    return [executable, "-u", str(script), *map(str, args)]


def kernel_command(config):
    executable = python_executable(config)
    if uses_bundled_python(config):
        return [executable, "--kernel-worker", "-f", "{connection_file}"]
    return [executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
