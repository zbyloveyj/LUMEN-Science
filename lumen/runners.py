"""Small, explicit language adapters. Compilation and execution are separate phases."""
from __future__ import annotations

import importlib.util
import shutil
import sys
import os
from pathlib import Path

LANGUAGES = {
    "python": {"label": "Python", "file": "code.py", "tool": "python", "mode": "持续内核 / 独立进程"},
    "R": {"label": "R", "file": "code.R", "tool": "Rscript", "mode": "IRkernel / Rscript"},
    "c": {"label": "C", "file": "main.c", "tool": "cc", "mode": "编译后运行"},
    "cpp": {"label": "C++", "file": "main.cpp", "tool": "cxx", "mode": "编译后运行"},
    "java": {"label": "Java", "file": "Main.java", "tool": "java", "mode": "编译后运行"},
    "javascript": {"label": "JavaScript", "file": "code.js", "tool": "node", "mode": "Node.js"},
    "typescript": {"label": "TypeScript", "file": "code.ts", "tool": "node", "mode": "Node.js 类型擦除"},
    "go": {"label": "Go", "file": "main.go", "tool": "go", "mode": "编译后运行"},
    "rust": {"label": "Rust", "file": "main.rs", "tool": "rustc", "mode": "编译后运行"},
    "powershell": {"label": "PowerShell", "file": "code.ps1", "tool": "pwsh", "mode": "独立进程"},
    "bash": {"label": "Bash", "file": "code.sh", "tool": "bash", "mode": "独立进程"},
    "sql": {"label": "SQL / SQLite", "file": "code.sql", "tool": "sqlite", "mode": "独立项目数据库"},
}


def resolve_tool(name, config):
    configured = config.get("runner_paths", {}).get(name)
    if configured:
        return configured if Path(configured).is_file() else None
    if name in ("python", "sqlite"):
        return config.get("python_path") or sys.executable
    if name == "Rscript":
        detected=config.get("rscript_path") or shutil.which("Rscript")
        if detected:return detected
        if os.name=="nt":
            roots=[Path("C:/app_install"),Path(os.environ.get("PROGRAMFILES","C:/Program Files"))/"R"]
            for root in roots:
                if root.is_dir():
                    for folder in sorted(root.glob("R-*"),reverse=True):
                        for candidate in (folder/"bin"/"Rscript.exe",folder/"bin"/"x64"/"Rscript.exe"):
                            if candidate.is_file():return str(candidate)
        return None
    if name == "bash":
        git=shutil.which("git")
        if git:
            candidate=Path(git).parent.parent/"bin"/"bash.exe"
            if candidate.is_file():return str(candidate)
    aliases = {"cc": ["gcc", "clang"], "cxx": ["g++", "clang++"],
               "node": ["node"], "java": ["java"], "javac": ["javac"],
               "go": ["go"], "rustc": ["rustc"], "pwsh": ["pwsh", "powershell"],
               "bash": ["bash"]}
    for candidate in aliases.get(name, [name]):
        value = shutil.which(candidate)
        if value:
            return value
    if name in ("cc", "cxx"):
        spec = importlib.util.find_spec("ziglang")
        if spec and spec.submodule_search_locations:
            base = Path(next(iter(spec.submodule_search_locations)))
            for file in ("zig.exe", "zig"):
                if (base / file).is_file():
                    return str(base / file)
    return None


def environments(config):
    return [{"id": name, **spec, "path": resolve_tool(spec["tool"], config),
             "ready": bool(resolve_tool(spec["tool"], config)) and
                      (name != "java" or bool(resolve_tool("javac", config)))}
            for name, spec in LANGUAGES.items()]


def plan(language, run_dir, config):
    if language not in LANGUAGES:
        raise ValueError("不支持的执行语言")
    spec = LANGUAGES[language]
    executable = resolve_tool(spec["tool"], config)
    if not executable:
        raise ValueError("尚未检测到 " + spec["label"] + " 所需工具；请在设置中配置 " + spec["tool"])
    script = Path(run_dir) / spec["file"]
    binary = Path(run_dir) / ("program.exe" if sys.platform == "win32" else "program")
    if language == "python":
        return [[executable, "-u", str(script)]]
    if language == "R":
        return [[executable, "--vanilla", str(script)]]
    if language in ("c", "cpp"):
        zig = Path(executable).stem.lower() == "zig"
        command = [executable] + (["c++" if language == "cpp" else "cc"] if zig else [])
        return [command + [str(script), "-O2", "-o", str(binary)], [str(binary)]]
    if language == "java":
        javac = resolve_tool("javac", config)
        if not javac:
            raise ValueError("Java 执行需要 JDK 和 javac 编译器")
        return [[javac, "-encoding", "UTF-8", "-d", str(run_dir), str(script)],
                [executable, "-Dfile.encoding=UTF-8", "-cp", str(run_dir), "Main"]]
    if language in ("javascript", "typescript"):
        return [[executable, str(script)]]
    if language == "go":
        return [[executable, "build", "-o", str(binary), str(script)], [str(binary)]]
    if language == "rust":
        return [[executable, str(script), "-O", "-o", str(binary)], [str(binary)]]
    if language == "powershell":
        return [[executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)]]
    if language == "bash":
        return [[executable, str(script)]]
    if language == "sql":
        return [[executable, "-u", str(Path(__file__).with_name("sqlite_runner.py")), str(script)]]
    raise ValueError("没有配置此语言的执行方式")
