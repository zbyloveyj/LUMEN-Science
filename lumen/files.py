from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import mimetypes
import os
import re
from pathlib import Path

MAX_FILE = 32 * 1024 * 1024
IGNORED = {".git", ".venv", "node_modules", "__pycache__", ".lumen", ".ipynb_checkpoints"}
TEXT_EXTENSIONS = {".txt", ".md", ".py", ".r", ".json", ".csv", ".tsv", ".yaml", ".yml", ".log", ".toml", ".bib", ".ris"}


def safe_path(root, relative, must_exist=False):
    root = Path(root).resolve()
    if not isinstance(relative, str) or "\x00" in relative or not relative.strip():
        raise ValueError("请提供项目内的相对路径")
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts or ":" in relative:
        raise ValueError("只能访问当前项目内的相对路径")
    path = (root / relative_path).resolve()
    if path != root and root not in path.parents:
        raise ValueError("路径超出当前项目")
    if must_exist and not path.exists():
        raise ValueError("文件不存在")
    return path


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(root, relative):
    path = safe_path(root, relative, True)
    if not path.is_file() or path.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("输入需要为不超过 256 MiB 的普通文件")
    return {"path": path.relative_to(Path(root).resolve()).as_posix(),
            "sha256": sha256(path), "bytes": path.stat().st_size}


def walk_files(root, max_count=1500):
    root = Path(root).resolve()
    result = []
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED and not d.startswith(".")
                         and not (Path(base) / d).is_symlink())
        for name in sorted(names):
            if name.startswith("."):
                continue
            p = Path(base) / name
            if p.is_symlink() or not p.is_file():
                continue
            try:
                p = safe_path(root, p.relative_to(root).as_posix(), True)
                stat = p.stat()
                result.append({"path": p.relative_to(root).as_posix(), "name": name,
                               "bytes": stat.st_size, "modified": stat.st_mtime,
                               "extension": p.suffix.lower()})
            except (OSError, ValueError):
                continue
            if len(result) >= max_count:
                return {"files": result, "truncated": True}
    return {"files": result, "truncated": False}


def output_snapshot(root):
    out = {}
    for file in walk_files(root, 2500)["files"]:
        if file["path"].startswith(("outputs/", "reports/")) and file["bytes"] <= MAX_FILE:
            path = safe_path(root, file["path"], True)
            out[file["path"]] = sha256(path)
    return out


def changed_outputs(root, before):
    after = output_snapshot(root)
    return [{"path": p, "sha256": h, "bytes": safe_path(root, p).stat().st_size}
            for p, h in after.items() if before.get(p) != h]


def load_table(path, sheet=None, nrows=None):
    import pandas as pd
    suffix = Path(path).suffix.lower()
    if suffix in (".csv", ".tsv"):
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                return pd.read_csv(path, sep="\t" if suffix == ".tsv" else ",",
                                   encoding=encoding, nrows=nrows)
            except UnicodeDecodeError:
                continue
        raise ValueError("无法识别表格编码")
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path, sheet_name=sheet or 0, nrows=nrows)
    if suffix == ".parquet":
        try:
            df = pd.read_parquet(path)
        except ImportError:
            raise ValueError("读取 Parquet 需要 pyarrow 或 fastparquet；请安装 requirements-data.txt 中的可选依赖。") from None
        return df.head(nrows) if nrows else df
    raise ValueError("支持 CSV、TSV、Excel 和 Parquet 表格")


def table_preview(root, relative, sheet=None):
    import pandas as pd
    path = safe_path(root, relative, True)
    if path.stat().st_size > MAX_FILE:
        raise ValueError("交互预览上限为 32 MiB；大文件请在 Notebook 中按块处理")
    df = load_table(path, sheet)
    if len(df.columns) > 300:
        raise ValueError("表格超过 300 列，请在 Notebook 中选择列后处理")
    columns = []
    for index, name in enumerate(df.columns):
        series = df.iloc[:, index]
        info = {"name": str(name), "dtype": str(series.dtype),
                "missing": int(series.isna().sum()), "unique": int(series.nunique()),
                "missing_percent": round(float(series.isna().mean() * 100), 2)}
        if pd.api.types.is_numeric_dtype(series):
            finite = series.replace([float("inf"), -float("inf")], float("nan")).dropna()
            for key in ("min", "max", "mean", "median", "std"):
                value = getattr(finite, key)() if len(finite) else None
                info[key] = float(value) if value is not None and pd.notna(value) else None
        columns.append(info)
    # JSON conversion normalizes timestamps, null and numpy scalars.
    rows = json.loads(df.head(60).to_json(orient="records", date_format="iso", force_ascii=False))
    sheets = pd.ExcelFile(path).sheet_names if path.suffix.lower() in (".xlsx", ".xls") else []
    return {"path": relative, "rows": len(df), "columns": columns, "preview": rows,
            "duplicate_rows": int(df.duplicated().sum()), "sheets": sheets,
            "identity": identity(root, relative), "preview_limit": 60}


def read_text(root, relative, limit=80_000):
    path = safe_path(root, relative, True)
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("文本超过 2 MiB，请分段处理")
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            content = path.read_text(encoding=encoding)
            return {"path": relative, "text": content[:limit], "truncated": len(content) > limit}
        except UnicodeDecodeError:
            pass
    raise ValueError("此文件不适合文本预览")


def write_text(root, relative, text, overwrite=False):
    if len(text.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("文本大小超过 2 MiB")
    path = safe_path(root, relative)
    if path.parts[len(Path(root).resolve().parts):][0].lower() in ("data", "raw"):
        raise ValueError("数据目录只读；请将衍生数据保存在 outputs 中")
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        raise ValueError("只允许保存文本、脚本和报告")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if overwrite else "x", encoding="utf-8") as stream:
        stream.write(text)
    return {"path": relative, "sha256": sha256(path)}


def import_file(root, name, content):
    name = Path(name.replace("\\", "/")).name
    if not name or name.startswith(".") or name.lower().endswith((".exe", ".dll", ".bat", ".cmd", ".ps1")):
        raise ValueError("请选择数据、脚本或文献文件")
    try:
        data = base64.b64decode(content, validate=True)
    except Exception as exc:
        raise ValueError("文件编码无效") from exc
    if len(data) > MAX_FILE:
        raise ValueError("上传上限为 32 MiB")
    path = safe_path(root, "data/" + name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    return identity(root, "data/" + name)
