Title: Add cleanup: remove backtesting artifacts (logs, pycache, db, dockerfiles, scripts, openapi)

This PR removes non-source artifacts from `backtesting_backend` to keep the repository clean and reproducible.

What I removed
- Runtime artifacts and caches:
  - `__pycache__` files, `backtesting_backend/logs/*`, `backtesting_backend/openapi.json`, `backtesting_backend/last_run_response.json`
- Local/test artifacts:
  - `backtesting_backend/yona_backtest.db` (moved to backup)
- Docker / environment / helper files:
  - `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `ENGINE_HOST_DOCKER.md`, `environment.yml`, `requirements.lock`, `run_uvicorn.py`, `run_uvicorn_monitor.ps1`, `run_backtest_service.ps1`, `run_backtest_test.py`, `launch_backend.cmd`

Notes
- Preserved source code: `app/`, `core/`, `database/`, `tests/`, `ml/` (source code), `config/`, `schemas/`, and documentation files.
- Backups were created before removal and moved outside the repository to: `C:\Users\User\backups\backtesting_cleanup_20251211_005656`
- If you want backups stored elsewhere (network share, external drive), I can move them.

Testing performed
- Unit tests: `backtesting_backend/tests/unit` — passed locally
- Integration tests: `backtesting_backend/tests/integration` — passed locally

Reviewer checklist
- [ ] Confirm backups retrieved at `C:\Users\User\backups\backtesting_cleanup_20251211_005656`
- [ ] Confirm no required runtime scripts are needed by CI or deployments
- [ ] Confirm Docker artifacts are not used in CI; if used, restore relevant files
- [ ] Merge after approval
