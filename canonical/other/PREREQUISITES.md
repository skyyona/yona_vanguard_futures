# Backtesting Backend — Prerequisites

This document lists exact environment and dependency prerequisites used to run and test `backtesting_backend` locally.

1) Python
- Supported/tested: Python 3.10 (local venv used). We recommend supporting Python 3.10–3.12. If you require a single minimum, choose Python 3.10 for widest compatibility.

2) Package manager
- On Windows prefer Miniforge/Conda for heavy numeric/binary packages, or use a standard `venv` if you can install wheels.

3) Creating an environment (recommended)

PowerShell (venv):

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Or using Conda (Miniforge)

```powershell
conda env create -f backtesting_backend/environment.yml -n yonaback
conda activate yonaback
python -m pip install -r dev-requirements.txt
```

4) Files and secrets
- Do NOT commit any `.env` files containing API keys or secrets.
- The repo `.gitignore` has been updated to include `*.env`, `engine_backend/.env`, and `backtesting_backend/.env`.
- If any `.env` has been committed previously, remove it from the repo history or run `git rm --cached path/to/.env` and commit the removal.

5) Recommended runtime packages (non-exhaustive)
- `pydantic`, `pandas`, `numpy`, `httpx`, `fastapi`, `SQLAlchemy` — installed via `requirements.txt`.
- Dev/test packages available in `dev-requirements.txt` (pytest, pytest-asyncio, black, etc.).

6) Windows-specific notes
- Avoid Docker Desktop/WSL for local dev if you do not want them; use Miniforge or a native `venv` as shown above.
- When using `venv` on Windows, use PowerShell `Activate.ps1` to activate and ensure `pip` installs the pre-built wheels where available.

7) CI recommendations
- Use matrix runs for `ubuntu-latest` and `windows-latest` and a Python matrix containing 3.10 and 3.12. Install `pip` dependencies and run unit and integration tests.

If you want, I can create a one-click developer setup (PowerShell script) to create the venv and install dev deps.
