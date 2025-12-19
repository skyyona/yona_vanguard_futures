# PR Draft: Orchestrator — Backtest compatibility

## Summary
Add backward-compatible keys to `orchestrator.step()` so the legacy backtest adapter and other consumers can detect executed entries/exits:

- `entry_triggered`: bool
- `exit_triggered`: bool
- `entry_signal`: optional dict with execution details
- `exit_reason`: optional string

## Files changed
- `backend/core/new_strategy/orchestrator.py` — add flags and metadata to return payload

## Testing
- Local test runner `tmp_run_backtests.py` executed for `JELLYJELLYUSDT` and `BTCUSDT`.
- Created `scripts/collect_backtests.py` to run multiple symbols and save JSON outputs to `backtest_results/`.

## Checklist
- [ ] Unit tests (n/a)
- [x] Integration test: local backtest runs
- [ ] Docs update: GUI text vs engine (recommend separate PR)

## Notes
The orchestrator change is additive and backward-compatible; consumers reading `signal_action` remain unaffected. Recommend reviewing the GUI copy in `gui/widgets/strategy_analysis_dialog.py` to align EMA numbers.
