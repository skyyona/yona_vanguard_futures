# Changelog

## 2025-12-03 — Simulator position-sizing fallback fix

- Problem: When a strategy's `parameters` were empty the simulator fell back to a legacy fixed-unit sizing behaviour which produced non-proportional PnL across different `initial_balance` values. This caused identical strategies run with different capital to show inconsistent profit percentages.

- Fix: Apply an app-level default `capital_fraction` (1%) when a strategy does not supply an explicit `position_size_policy`. Position sizing now computes exposure = notional * leverage and derives units = exposure / price. Also corrected gross PnL math to avoid double-counting leverage.

- Verification: Added unit test `tests/test_simulator_scaling.py` that asserts profit percentage is invariant to `initial_balance` for a fixed leverage and scales linearly with `leverage` when using the default fallback. End-to-end API backtests were re-run and DB rows verified.
