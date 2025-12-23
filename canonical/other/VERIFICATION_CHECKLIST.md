```markdown
Verification checklist (apply after user approval and patches applied)

1) Apply Fix A (simulator changes)
   - Run unit test (create if missing): tests/test_simulator_fix_a.py with simple single-trade scenario.
   - Command:
     python -m pytest tests/test_simulator_fix_a.py::test_simple_pnl -q
   - Expected: PnL numeric matches manual calc (units = notional/price, PnL = price_diff * units * leverage).

2) Re-run baseline scripts and capture outputs (pre/post comparison)
   - Commands (pre-record existing outputs before changes):
     python scripts/run_mtf_backtests.py
     python scripts/run_mtf_backtests_loose.py
   - After applying Fix A and verifying unit tests, re-run same scripts and compare JSONs under backtest_results_mtf/.
   - Check: final_balance, profit_percentage, max_drawdown_pct scales reduced from prior over-leveraged values.

3) Apply leverage sweep patch and minimal UI patch
   - Restart backend server (if running) and call API:
     curl "http://localhost:8000/strategy-analysis?symbol=BTCUSDT&period=1w&interval=1m" -o out.json
   - Inspect:
     jq '.data.leverage_recommendation' out.json
     jq '.data.scenarios.S_LEVER_SWEEP' out.json
   - UI: open dialog and confirm "Simulation 6 (Leverage sweep)" appears with summary & candidate table.

4) Tests for sweep logic
   - Unit test (mock core_run_backtest) covering:
     - Candidate with high max_dd rejected.
     - Candidate with non-positive final_balance rejected.
     - Candidate with highest profit chosen among accepted.

5) Performance and safety checks
   - Enable logging to see number of extra simulations run (should be = len(candidates) or fewer if short-circuited).
   - Confirm config toggles behave (ENABLE_LEVERAGE_SWEEP on/off).

Notes:
- All patches are provided as drafts in patches/*.patch. No files were modified in the codebase; these are patch drafts to review/apply manually.
- After you approve, I will apply patches in order (Fix A -> re-run tests -> leverage sweep -> UI) and report full pre/post metrics and logs.

```

6) Read-only runtime trace & request persistence (added by recent patch)
  - Purpose: aid post-mortem and reproducibility by emitting a compact orchestrator runtime snapshot
    and persisting the full incoming strategy request parameters in backtest artifacts.

  - Runtime trace (non-invasive): `StrategyOrchestrator.step()` now logs a single-line, read-only
    entry `orchestrator_trace` containing: `symbol`, `cfg.order_quantity`, `cfg.leverage`,
    `last_signal.score`, `entry_signal` and `position_size`. This log is purely informational
    and will not change runtime behavior.

  - Artifact persistence: `StrategySimulator.run_simulation()` includes a deep-copied
    `request_parameters` field in the returned results dictionary so saved backtest JSONs
    will contain the full request payload used for that run.

  - How to verify:
    - Run a backtest via the API or scripts and inspect logs for lines containing
      `orchestrator_trace` to see the compact snapshot.
    - Inspect backtest result JSON (`backtest_results/*.json` or returned API payload)
      and confirm presence of `request_parameters` with the expected keys/values.

  - Notes:
    - The trace avoids any sensitive fields and is logged at INFO level.
    - If any non-serializable objects are present in parameters, they are stored as
      a string fallback to avoid breaking result generation.

