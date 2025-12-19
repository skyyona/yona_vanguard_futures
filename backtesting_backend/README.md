# backtesting_backend

Lightweight, adapter-driven backtesting package for the YONA repo.

This package provides:
- Strategy adapter interfaces and adapters that wrap live strategy orchestrators (read-only).
- A lightweight `AdapterRunner` for fast replay/backtests.
- A feature-rich simulator module (kept separate) for deeper experiments.
- A minimal FastAPI router (`app/api/backtest_router.py`) and `BacktestService` for integration tests.
- ML stubs and tiny dummy model artifacts to exercise inference paths in tests.

WARNING: Do not commit any `.env` files containing secrets. Local `.env` files are ignored by `.gitignore`.

Getting started (Windows PowerShell)
-----------------------------------

1. Create and activate a venv:

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

2. Install runtime requirements:

```powershell
python -m pip install -r ..\requirements-runtime.txt
```

3. (Optional) Install test/dev requirements:

```powershell
python -m pip install -r ..\requirements-test.txt
python -m pip install -r ..\dev-requirements.txt  # optional dev tools
```

Running tests
-------------

- Unit tests:

```powershell
python -m pytest backtesting_backend/tests/unit -q
```

- Integration tests:

```powershell
python -m pytest backtesting_backend/tests/integration -q
```

Quick smoke run (adapter runner):

```powershell
python -c "from backtesting_backend.core.adapter_runner import AdapterRunner; print(AdapterRunner().run_once('alpha','BTCUSDT','2025-01-01','2025-01-02'))"
```

Run API locally (uvicorn)
-------------------------

```powershell
python -m uvicorn backtesting_backend.app.api.backtest_router:router --port 8203
```

Notes for reviewers
-------------------
- This package intentionally lazy-imports heavy dependencies where possible to avoid forcing consumers to install everything.
- `requirements.txt` and `dev-requirements.txt` were generated from the active venv used for development and tests; CI may pin slightly different versions.
- Do not commit `.env` files. The repo `.gitignore` has been updated to ignore `*.env` and the `engine_backend/.env` file.

If you want me to create a PR branch and push these changes, I can run the git commands for you.
Backtesting Backend (prototype)
===============================

This folder contains a minimal backtesting adapter layer and simulator used for local testing.

Quick start (recommended with conda/miniforge):

1. Create environment:

```powershell
conda env create -f environment.yml -n yonaback
conda activate yonaback
pip install -r requirements.txt  # optional
```

2. Run a small simulator example:

```powershell
python -m backtesting_backend.core.strategy_simulator
```

Notes:
- This is a conservative, read-only adapter implementation. It does not modify `backend/` live strategy files.
- The orchestrator adapter will attempt to wrap the live `StrategyOrchestrator` if available; otherwise it is a no-op.
