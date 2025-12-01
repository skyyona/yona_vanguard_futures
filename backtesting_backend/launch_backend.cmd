@echo off
rem Safe launcher for backtesting uvicorn server.
rem Run this from any location; it will change to the repo root and start uvicorn using the venv_python if available.

setlocal
set "SCRIPT_DIR=%~dp0"
rem repo root is parent of backtesting_backend folder
for %%I in ("%SCRIPT_DIR%\..") do set "REPO_ROOT=%%~fI"
pushd "%REPO_ROOT%"

if exist ".\.venv_backtest\Scripts\python.exe" (
    set "PY_EXE=.\.venv_backtest\Scripts\python.exe"
) else if exist ".\.venv_new\Scripts\python.exe" (
    set "PY_EXE=.\.venv_new\Scripts\python.exe"
) else (
    set "PY_EXE=python"
)

if not exist "backtesting_backend\logs" mkdir "backtesting_backend\logs"

echo Starting uvicorn using %PY_EXE%
"%PY_EXE%" -m uvicorn backtesting_backend.app_main:app --host 0.0.0.0 --port 8001 --log-level info > "backtesting_backend\logs\uvicorn.log" 2>&1

popd
endlocal
