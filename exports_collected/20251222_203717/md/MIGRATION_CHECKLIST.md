# Backtesting Backend — Migration & PR Checklist

Use this checklist when opening a PR to add or migrate a strategy into `backtesting_backend`.

1) Pre-PR
- Verify local environment per `PREREQUISITES.md`.
- Ensure no changes are made to live `backend/` code. Adapter approach must be used.
- Add adapter implementation under `backtesting_backend/app/services/strategies/` and tests under `backtesting_backend/tests/`.

2) Files to add (example)
- `app/services/strategies/<strategy>_adapter.py`
- `app/services/adapters/<broker_simulator>.py` (if needed)
- `core/adapter_runner.py` or extend runner to support new adapter
- `tests/unit/test_<strategy>_adapter.py`

3) Tests
- Unit tests for adapter interface and broker simulator.
- Integration test that imports `app/api/backtest_router` (use lazy imports) — skip if optional dependencies missing.

4) Documentation
- Update `backtesting_backend/README.md` if new runtime dependencies are required.
- Add migration notes describing how the adapter maps to live orchestrator events.

5) Security
- Ensure `.env` files with credentials are not added.

6) PR template (suggested)
- Title: `backtesting: add <strategy> adapter to backtesting_backend`
- Body: short description, files changed, testing steps, security note, reviewer checklist.

7) Post-merge
- Coordinate with ops to run longer-running backtests in an isolated environment.
