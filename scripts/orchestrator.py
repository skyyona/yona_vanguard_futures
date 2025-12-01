"""Orchestrator for parameter sweeps using StrategySimulator.

Usage:
    python scripts/orchestrator.py            # runs pilot by default

This script enumerates parameter combinations, runs the simulator for each symbol/combo/fold,
and writes per-run results to a CSV file under `results/`.

By default this uses a synthetic data loader. To plug a real data loader, modify `load_ohlcv`.
"""
from __future__ import annotations

import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any, Dict, List

import pandas as pd
from pathlib import Path

# sanitizer (importable)
try:
    from scripts.sanitize_results import sanitize_csv_file
except Exception:
    try:
        from sanitize_results import sanitize_csv_file
    except Exception:
        sanitize_csv_file = None


def load_ohlcv_synthetic(symbol: str, interval: str, periods: int = 1440) -> pd.DataFrame:
    """Return a synthetic OHLCV DataFrame for quick pilots.

    Index will be a DatetimeIndex at 1-minute resolution by default.
    """
    idx = pd.date_range("2025-01-01", periods=periods, freq="1min")
    import random

    random.seed(abs(hash(symbol)) % 2 ** 32)
    base = 100.0 + (abs(hash(symbol)) % 50)
    prices = [base + (i * 0.0005) + (random.random() - 0.5) * 0.5 for i in range(len(idx))]
    vols = [100 + (random.random() * 200) for _ in range(len(idx))]
    opens = [p - 0.05 for p in prices]
    highs = [p + 0.05 for p in prices]
    lows = [p - 0.1 for p in prices]
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": prices, "volume": vols}, index=idx)


def _worker_run(job: Dict[str, Any]) -> Dict[str, Any]:
    """Worker function executed in subprocesses. Builds simulator and runs one job.

    job keys: symbol, interval, params, initial_balance, leverage
    """
    # ensure project root is on sys.path for subprocess imports
    import sys
    import os
    proj_root = job.get("project_root") or os.getcwd()
    if proj_root not in sys.path:
        sys.path.insert(0, proj_root)

    # import inside worker to avoid heavy pickling
    from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
    from backtesting_backend.core.strategy_simulator import StrategySimulator

    symbol = job["symbol"]
    interval = job.get("interval", "1m")
    params = job.get("params", {})
    initial_balance = float(job.get("initial_balance", 1000.0))
    leverage = int(job.get("leverage", 1))

    # load data (for now synthetic)
    df = load_ohlcv_synthetic(symbol, interval, periods=job.get("periods", 1440))

    analyzer = StrategyAnalyzer()
    sim = StrategySimulator(analyzer=analyzer)

    try:
        res = sim.run_simulation(symbol, interval, df.copy(), initial_balance=initial_balance, leverage=leverage, strategy_parameters=params)
        # Do not include user capital or leverage in exported results
        out = {
            "symbol": symbol,
            "interval": interval,
            "params": json.dumps(params, ensure_ascii=False),
            "profit": res.get("profit", 0.0),
            "profit_pct": res.get("profit_percentage", 0.0),
            "total_trades": res.get("total_trades", 0),
            "win_rate": res.get("win_rate", 0.0),
            "max_drawdown_pct": res.get("max_drawdown_pct", 0.0),
        }
    except Exception as e:
        out = {"symbol": symbol, "interval": interval, "params": json.dumps(params, ensure_ascii=False), "error": str(e)}

    return out


def enumerate_grid(grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    keys = sorted(grid.keys())
    combos = list(itertools.product(*(grid[k] for k in keys)))
    out = []
    for c in combos:
        d = {k: v for k, v in zip(keys, c)}
        out.append(d)
    return out


def main():
    # results dir
    os.makedirs("results", exist_ok=True)
    out_csv = os.path.join("results", "orchestrator_results.csv")

    SYMBOLS = ["PILOT_BTC", "PILOT_ETH", "PILOT_BNB"]
    INTERVAL = "5min"

    GRID = {
        "volume_spike_factor": [1.4, 1.6],
        "volume_avg_period": [10, 20],
        "sr_proximity_threshold": [0.001, 0.002],
    }

    baseline_params = {
        "fast_ema_period": 3,
        "slow_ema_period": 5,
        "enable_volume_momentum": True,
        "enable_sr_detection": True,
        "enable_sr_filter": True,
        "stop_loss_pct": 0.01,
        "take_profit_pct": 0.02,
        "position_size": 0.02,
    }

    grid_list = enumerate_grid(GRID)
    jobs = []
    for symbol in SYMBOLS:
        for combo in grid_list:
            params = dict(baseline_params)
            # map combo keys to expected param names
            params["volume_spike_factor"] = combo["volume_spike_factor"]
            params["volume_avg_period"] = combo["volume_avg_period"]
            params["sr_proximity_threshold"] = combo["sr_proximity_threshold"]

            job = {
                "symbol": symbol,
                "interval": INTERVAL,
                "params": params,
                "initial_balance": 1000.0,
                "leverage": 1,
                "project_root": os.getcwd(),
                "periods": 6 * 24 * 12,  # e.g., 6 days at 5min ~ 6*24*12
            }
            jobs.append(job)

    # start parallel run
    max_workers = min(4, os.cpu_count() or 1)
    print(f"Running {len(jobs)} jobs with {max_workers} workers. Output -> {out_csv}")

    # write header
    import csv

    header_written = False
    with ProcessPoolExecutor(max_workers=max_workers) as exe, open(out_csv, "w", newline='', encoding="utf-8") as fh:
        writer = None
        futures = {exe.submit(_worker_run, job): job for job in jobs}
        for fut in as_completed(futures):
            job = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"symbol": job.get("symbol"), "interval": job.get("interval"), "params": json.dumps(job.get("params")), "error": str(e)}

            # flatten row
            row = dict(res)
            if not header_written:
                writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
                writer.writeheader()
                header_written = True
            writer.writerow(row)
            fh.flush()
            print("completed:", row.get("symbol"), row.get("params")[:80])

    print("Orchestrator finished. Results saved to:", out_csv)

    # sanitize the orchestrator CSV
    if sanitize_csv_file is not None:
        try:
            s = sanitize_csv_file(Path(out_csv), inplace=False, dry_run=False)
            if s:
                print('Sanitized output ->', s)
        except Exception as e:
            print('Sanitization failed:', e)


if __name__ == "__main__":
    main()
