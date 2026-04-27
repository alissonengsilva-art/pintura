@echo off
setlocal

cd /d "%~dp0"

echo ======================
echo INICIANDO CONTROL PLAN
echo ======================
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
    goto :eof
)

py -m uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload
