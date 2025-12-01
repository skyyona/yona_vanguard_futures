# Experiment Matrix & Walk-Forward Plan

This document captures the parameter grid, timeframe choices, walk-forward validation plan, metrics, and resource estimates for evaluating the new Advanced Volume Momentum and Support/Resistance scalping features.

## 1) Goals
- Measure whether enabling volume-momentum and S/R filters improves strategy performance vs. baseline EMA crossover.
- Evaluate robustness across multiple assets and market regimes.

## 2) Parameters to Sweep

- Volume spike factor (`volume_spike_factor` / `spike_factor`): [1.2, 1.4, 1.6, 1.8, 2.0]
- Volume avg lookback (`volume_avg_period` / `avg_period`): [5, 10, 20, 50]
- S/R lookback (`sr_lookback_period`): [50, 100, 200]
- S/R proximity threshold (`sr_proximity_threshold`): [0.001, 0.002, 0.005]
- Timeframes (for core backtest bars): [`1min`, `5min`, `15min`]
- EMA fast/slow (kept consistent with baseline or optionally swept): fast in [3,5,9], slow in [21,34]
- Feature flags: `enable_volume_momentum` in {False, True}, `enable_sr_filter` in {False, True}

Note: For combinatorial explosion, practical runs should iterate over a subset (see Execution Plan).

## 3) Experiment Design / Cross-Validation

- Approach: Rolling walk-forward (rolling-origin) cross-validation per-symbol.
  - Train window: 90 days (or N bars depending on TF)
  - Test (out-of-sample) window: 30 days
  - Step size: 30 days (non-overlapping test windows with overlap in training), repeat until end of dataset.
- For shorter datasets, use: train 60 days / test 30 days.
- For each fold and parameter combination:
  1. Compute indicators using only training data; optionally tune simple thresholds on training fold (not required for fixed-parameter sweep).
  2. Run simulation on test fold using parameters fixed.
  3. Record fold-level metrics (see Metrics section).
- Aggregate across folds to compute mean/median metrics and robustness (fraction of folds with positive returns).

## 4) Asset / Data Selection

- Start with a small pilot cohort (5–10 high-liquidity coins), for example: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `ADAUSDT`.
- Time range: ideally 12+ months; minimum 6 months for stable seasonal evaluation.
- Data quality filters: drop bars with missing close or zero volume; mark and skip symbols with >10% missing bars in requested span.
- VWAP session handling: use exchange-local day boundaries (UTC by default) and reset VWAP per-session when computing.

## 5) Metrics & Acceptance Criteria

- Trade-level:
  - Win rate, average win/loss, expectancy (avg profit per trade)
  - Avg trade duration, trades per period
- Portfolio-level (per-fold):
  - Total return, annualized return
  - Sharpe ratio (excess return / std dev) — use daily/TF-normalized returns
  - Max drawdown, Calmar ratio
  - Profit factor (gross wins / gross losses)
- Robustness metrics:
  - Fraction of folds with positive return
  - Fraction of symbols with median positive return across folds
  - Parameter stability: sensitivity table (small changes in spike_factor should not flip sign of returns)
- Signal-quality metrics:
  - Precision/recall of buy signals that become positive after N bars (labeling requires follow-up window)

Acceptance recommendation (pilot thresholds):
- Require mean test-fold Sharpe > baseline Sharpe by at least 0.2, AND
- Fraction of positive folds >= 60% OR median test-fold return > baseline median by 5%.

## 6) Execution Plan

- Pilot run (fast):
  - TF: `5min` (balance between noise and computation)
  - Parameters: sample points spike_factor ∈ {1.4, 1.6}, avg_period ∈ {10,20}, sr_prox ∈ {0.001,0.002}
  - Symbols: `BTCUSDT`, `ETHUSDT`, `BNBUSDT`
  - Purpose: sanity check and runtime estimate

- Full sweep (example):
  - Parameter combs: 5 x 4 x 3 x 3 x 3 TFs = 540 combos (with feature flags doubling factor if both enabled/disabled included)
  - If evaluating 10 symbols and 6 folds, total runs = 540 x 10 x 6 = 32,400 simulation runs

## 7) Resource Estimate & Parallelism

- Single simulation runtime: depends on TF and history length; estimate 1–10s per combo for 1 symbol on typical dev machine for `5min` bars.
- Full-sweep rough estimate (540 combos x 10 symbols x 6 folds x 3s avg) ≈ 27 hours single-threaded. Parallelizing across 8 workers reduces to ~3.5 hours.
- Recommendation: use a job queue or `concurrent.futures` with process-based workers; save intermediate CSV results per-run to avoid re-computation.

## 8) Outputs
- Per-run CSV row with: symbol, TF, parameters, fold, total_return, sharpe, max_dd, trades, profit_factor, mean_trade, win_rate
- Aggregated CSVs: `aggregate_by_params.csv`, `top_param_combos.csv`, `param_robustness.csv`
- Visuals (post-run): heatmaps of mean returns / sharpe across (spike_factor x avg_period) per TF.

## 9) Next Steps (implementation)
1. Implement an orchestrator script that: enumerates parameter combos, shards jobs for parallel workers, and writes per-run CSV lines. (I can implement this.)
2. Run the Pilot (small combos, 3 symbols) and confirm outputs. (I can run this and provide results.)
3. If pilot looks promising, schedule full sweep on a larger machine or cloud instance.

---
File created by the auto-design step. Ask me to (A) implement the orchestrator script, (B) run the pilot now, or (C) change any grid/fold sizes.
