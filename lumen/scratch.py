"""Per-run compiler staging for tools with Windows ANSI/space restrictions."""
from __future__ import annotations

import ctypes
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


def compatible_base(path):
    base = Path(path).expanduser().resolve()
    if not base.is_dir():
        raise ValueError("工具临时目录不存在，请在设置中选择已有目录")
    value = str(base)
    if value.isascii() and not any(c.isspace() for c in value):
        return value
    if os.name == "nt":
        # A short name is optional on NTFS; never assume that it exists.
        function = ctypes.windll.kernel32.GetShortPathNameW
        function.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        function.restype = ctypes.c_uint32
        size = function(value, None, 0)
        if size:
            buffer = ctypes.create_unicode_buffer(size + 1)
            if function(value, buffer, len(buffer)):
                short = buffer.value
                if short.isascii() and not any(c.isspace() for c in short):
                    return short
    raise ValueError("此语言工具需要无空格的 ASCII 临时目录；请在设置中填写“编译工具临时目录”，项目名称和数据目录无需更改。")


@contextmanager
def compiler_workspace(config, script):
    base = compatible_base(config.get("tool_temp_dir") or tempfile.gettempdir())
    created = Path(tempfile.mkdtemp(prefix="lumen-", dir=base))
    expected_parent = Path(base).resolve()
    try:
        shutil.copyfile(script, created / Path(script).name)
        yield created
    finally:
        # Only remove our newly created, resolved child of the selected temp root.
        resolved = created.resolve()
        if resolved.parent != expected_parent or created.is_symlink():
            raise ValueError("临时目录身份变化，已拒绝自动清理")
        try:
            shutil.rmtree(created)
        except OSError:
            # An externally spawned process may still own a file handle.
            # Do not misreport the computation as failed or remove unrelated files.
            pass
