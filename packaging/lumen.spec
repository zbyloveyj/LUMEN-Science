# Build on Windows with the clean desktop environment; no local state is collected.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

root = Path(SPECPATH).parent
datas = [(str(root / "web"), "web"),
         (str(root / "lumen/sqlite_runner.py"), "lumen"),
         (str(root / "LICENSE"), "."),
         (str(root / "build/THIRD_PARTY_NOTICES"), "THIRD_PARTY_NOTICES")]
binaries = []
hiddenimports = ["run", "lumen.app", "lumen.runtime", "openpyxl", "scipy.stats", "scipy.linalg",
                 "matplotlib.backends.backend_agg", "matplotlib_inline.backend_inline",
                 "ipykernel_launcher", "ipykernel.kernelapp", "pandas", "numpy", "paramiko"]
for package in ("webview", "ipykernel", "jupyter_client", "matplotlib_inline", "debugpy"):
    data, binary, hidden = collect_all(package)
    datas += data
    binaries += binary
    hiddenimports += hidden
# debugpy enumerates its vendored source tree at runtime before loading pydevd.
datas += collect_data_files("debugpy", include_py_files=True)
for package in ("pandas", "numpy", "scipy", "matplotlib", "ipykernel", "jupyter_client", "openpyxl"):
    datas += copy_metadata(package)
a = Analysis([str(root / "desktop.py")], pathex=[str(root)], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports,
             excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "gi", "cefpython3", "pytest", "tkinter"],
             noarchive=False)
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LUMENScience", console=False,
          debug=False, upx=False, icon=str(root / "packaging/lumen.ico"))
worker = EXE(pyz, a.scripts, [], exclude_binaries=True, name="lumen-runtime", console=True,
             debug=False, upx=False, icon=str(root / "packaging/lumen.ico"))
coll = COLLECT(gui, worker, a.binaries, a.datas, strip=False, upx=False, name="LUMENScience")
