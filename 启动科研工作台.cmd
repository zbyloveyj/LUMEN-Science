@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" desktop.py --desktop
) else (
    if exist "C:\app_install\miniconda\python.exe" (
        "C:\app_install\miniconda\python.exe" desktop.py --desktop
    ) else (
        python desktop.py --desktop
    )
)
if errorlevel 1 pause
