Release Notes - Backtest/Parity Cleanup (2025-12-21)

Summary:
- Removed temporary debug instrumentation that wrote `tmp_*` diagnostic files from the order normalization path in `yona_vanguard_futures/backend/core/new_strategy/execution_adapter.py`.
- Preserved the safe fallback in the inlined backtest client (`_BacktestClient.get_mark_price`) in `yona_vanguard_futures/backend/core/new_strategy/orchestrator.py` to ensure deterministic backtests.
- Deleted all existing `tmp_*` diagnostic files from the workspace.
- Verified parity: `scripts/parity_test.py` produced `parity_report.json` confirming legacy `entry_index=1` and new-engine entry at `signal_score=95.0`.

Details:
- `ExecutionAdapter.normalize_quantity` no longer writes temporary JSON dumps on client/method failures or exceptions. Instead it falls back to a safe numeric `price_hint=0.0` and proceeds, returning a normalized qty or a structured error result. This avoids noisy workspace artifacts while keeping deterministic behavior for backtests.
- `_BacktestClient.get_mark_price` behavior retained: returns a safe `{"markPrice": "0.0"}` on cache misses/exceptions so backtests continue to behave deterministically.

Recommended next steps:
1. Run unit/integration tests and any CI checks.
2. Optionally gate verbose debug instrumentation behind a `DEBUG_BACKTEST` flag if future captures are required.
3. Commit and push these changes to the mainline branch.

Commit suggestion:
- Title: "chore(backtest): remove tmp_* debug dumps and clean normalize_quantity"
- Body: "Remove temporary diagnostic file writes from ExecutionAdapter.normalize_quantity; keep safe backtest mark-price fallback; remove tmp_* files; verify parity with scripts/parity_test.py."
