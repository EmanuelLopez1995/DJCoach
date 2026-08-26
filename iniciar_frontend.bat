@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv.
    echo Ejecuta: py -3.12 -m venv .venv --system-site-packages
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "dj_coach_web.py"

