r"""Simple runner for the backtesting FastAPI app.

Run this from the project root with the backtest virtualenv activated to
start the app in a single process (no auto-reload). This helps diagnose
issues related to the reloader or parent/child process lifecycle on Windows.

Usage:
  cd /d C:\Users\User\new\yona_vanguard_futures
  call .\.venv_backtest\Scripts\activate.bat
  python backtesting_backend\run_uvicorn.py
"""
import os
import sys

# Ensure project root is on sys.path so `backtesting_backend` can be imported
# when this file is executed as a script (e.g. `python backtesting_backend\run_uvicorn.py`).
project_root = os.path.dirname(os.path.dirname(__file__))
if project_root not in sys.path:
  sys.path.insert(0, project_root)

from backtesting_backend.app_main import create_app
import uvicorn


def main():
    app = create_app()
    # Run without reload/watchdog so we have one process to inspect
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")


if __name__ == "__main__":
    main()
