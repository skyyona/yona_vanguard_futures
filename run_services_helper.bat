@echo off
REM Helper to start services in separate windows
SET "BASE_DIR=%~dp0"

REM Start Live Backend (port 8200)
start "Live Backend" cmd /k "cd /d "%BASE_DIR%backend" && call "%BASE_DIR%.venv_new\Scripts\activate.bat" && python -m uvicorn app_main:app --host 0.0.0.0 --port 8200 --reload --log-level info"

REM Start Backtesting Backend (port 8001) - use the single-process runner to avoid reload issues
start "Backtesting Backend" cmd /k "cd /d "%BASE_DIR%backtesting_backend" && call "%BASE_DIR%.venv_backtest\Scripts\activate.bat" && python "%BASE_DIR%backtesting_backend\run_uvicorn.py""

REM Start GUI
start "GUI" cmd /k "cd /d "%BASE_DIR%gui" && call "%BASE_DIR%.venv_new\Scripts\activate.bat" && python main.py"
