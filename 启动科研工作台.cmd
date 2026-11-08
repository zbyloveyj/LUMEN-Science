@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    if exist "C:\app_install\miniconda\python.exe" (
        "C:\app_install\miniconda\python.exe" run.py
    ) else (
        python run.py
    )
)
if errorlevel 1 pause
