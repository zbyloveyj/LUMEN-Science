# Windows desktop build

Use a clean Python 3.11 x64 environment on Windows. The bundle contains a native pywebview window and a separate console-subsystem worker for Jupyter and independent Python processes. This prevents a frozen executable from being mistaken for a standard Python interpreter.

~~~powershell
python -m venv .build-venv
.build-venv/Scripts/python -m pip install -r requirements-desktop.txt
./scripts/setup_build_tools.ps1
.build-venv/Scripts/python scripts/build_desktop.py --makensis .tools/nsis-3.11/makensis.exe
.build-venv/Scripts/python scripts/smoke_desktop.py dist/LUMENScience/LUMENScience.exe
~~~

The tools script downloads NSIS 3.11 from its official SourceForge mirror, checks the pinned archive hash, and checks the Microsoft bootstrapper Authenticode signature. Building does not include .state, .vendor, credentials, local projects or the source environment. Third-party license files and package versions are included under `_internal/THIRD_PARTY_NOTICES`.

`desktop-release.yml` runs on packaging/version changes or manual dispatch. It publishes a GitHub prerelease only after source tests, portable/installed runtime smoke checks and manifest-based uninstall checks pass. Existing version releases are not overwritten; increment the version to publish another release. No signing keys are configured.

The Windows profile is implemented and tested separately from macOS/Linux source support. It does not generate untested macOS or Linux installers.

References: [PyInstaller runtime paths](https://pyinstaller.org/en/stable/runtime-information.html), [pywebview freezing](https://pywebview.flowrl.com/guide/freezing), [Microsoft WebView2 distribution](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution).
