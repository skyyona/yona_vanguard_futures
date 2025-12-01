"""Run pilots using real data (local CSV or Binance public API).

Usage examples:
    python scripts/run_pilot_realdata.py --symbols PIPPINUSDT --interval 5m --start 2025-11-01 --end 2025-11-30

This script will:
 - look for a local CSV at `data/{symbol}_{interval}.csv` and use it if present
 - otherwise download klines from Binance (public endpoint) and save to `data/`
 - validate OHLCV columns and run the strategy simulator across a small parameter grid
 - write results to `results/{symbol}_pilot_results.csv`
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from typing import Dict, List

import pandas as pd
import requests
import sys

# ensure project root is importable when script runs from scripts/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def ensure_data_dir() -> None:
    os.makedirs("data", exist_ok=True)


def interval_to_ms(interval: str) -> int:
    if interval.endswith("m"):
        return int(interval[:-1]) * 60 * 1000
    if interval.endswith("h"):
        return int(interval[:-1]) * 60 * 60 * 1000
    if interval.endswith("d"):
        return int(interval[:-1]) * 24 * 60 * 60 * 1000
    raise ValueError("Unsupported interval: " + interval)


def download_klines_binance(symbol: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    url = "https://api.binance.com/api/v3/klines"
    limit = 1000
    rows = []
    cur = start_ms
    while cur < end_ms:
        params = {"symbol": symbol, "interval": interval, "startTime": cur, "endTime": end_ms, "limit": limit}
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"Binance API error: {r.status_code} {r.text}")
        data = r.json()
        if not data:
            break
        rows.extend(data)
        last_open = data[-1][0]
        cur = last_open + interval_to_ms(interval)
        time.sleep(0.2)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "num_trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df = df.set_index("open_time")
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df


def download_klines_binance_futures_fallback(symbol: str, interval: str, start_ms: int, end_ms: int) -> pd.DataFrame:
    """Fallback to backend BinanceClient (futures) if Spot API returns nothing or errors."""
    try:
        # Import here to avoid requiring asyncio/httpx when not used
        from backtesting_backend.api_client.binance_client import BinanceClient
        import asyncio

        async def _get():
            client = BinanceClient()
            try:
                data = await client.get_klines(symbol, interval, start_time=start_ms, end_time=end_ms)
                return data
            finally:
                try:
                    await client.close()
                except Exception:
                    pass

        rows = asyncio.run(_get())
        if not rows:
            return pd.DataFrame()

        # rows are list of dicts with open_time (int ms) etc.
        df = pd.DataFrame(rows)
        # convert open_time to datetime index
        if 'open_time' in df.columns:
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df = df.set_index('open_time')

        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df
    except Exception as e:
        # propagate to caller
        raise RuntimeError(f"Futures fallback failed: {e}")


def load_or_download(symbol: str, interval: str, start: str | None, end: str | None) -> pd.DataFrame:
    ensure_data_dir()
    fname = os.path.join("data", f"{symbol}_{interval}.csv")
    # 1) exact match
    if os.path.exists(fname):
        print(f"Using local file: {fname}")
        df = pd.read_csv(fname, parse_dates=[0], index_col=0)
    else:
        # 2) wildcard/case-insensitive search in data dir
        import glob
        pattern = os.path.join("data", f"*{symbol}*.csv")
        candidates = glob.glob(pattern)
        if not candidates:
            pattern2 = os.path.join("data", f"*{symbol.lower()}*.csv")
            candidates = glob.glob(pattern2)
        if candidates:
            candidates = sorted(candidates)
            use = candidates[0]
            print(f"Using local wildcard match: {use}")
            df = pd.read_csv(use, parse_dates=[0], index_col=0)
        else:
            df = None

    # if a local df was found, validate and filter
    if df is not None:
        required = {"open", "high", "low", "close", "volume"}
        if not required <= set(df.columns):
            raise RuntimeError(f"Local CSV found but missing required columns: {fname}")
        if start:
            df = df[df.index >= pd.to_datetime(start)]
        if end:
            df = df[df.index <= pd.to_datetime(end)]
        return df

    start_ms = int(pd.to_datetime(start).timestamp() * 1000) if start else 0
    end_ms = int(pd.to_datetime(end).timestamp() * 1000) if end else int(time.time() * 1000)
    try:
        df = download_klines_binance(symbol, interval, start_ms, end_ms)
        if df.empty:
            # try futures endpoint fallback
            df = download_klines_binance_futures_fallback(symbol, interval, start_ms, end_ms)
    except Exception:
        # if spot failed, attempt futures fallback
        df = download_klines_binance_futures_fallback(symbol, interval, start_ms, end_ms)

    if df is None or df.empty:
        raise RuntimeError("No data returned from Binance for symbol=" + symbol)
    df.to_csv(fname)
    return df


def run_pilot_for_symbol(symbol: str, interval: str, start: str | None, end: str | None) -> None:
    GRID = [
        {"volume_spike_factor": 1.4, "volume_avg_period": 10, "sr_proximity_threshold": 0.001},
        {"volume_spike_factor": 1.6, "volume_avg_period": 20, "sr_proximity_threshold": 0.002},
    ]

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

    print(f"Loading data for {symbol} {interval} {start}->{end}")
    df = load_or_download(symbol, interval, start, end)
    print(f"Loaded {len(df)} rows for {symbol}")

    import sys
    from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
    from backtesting_backend.core.strategy_simulator import StrategySimulator

    analyzer = StrategyAnalyzer()
    sim = StrategySimulator(analyzer=analyzer)

    os.makedirs("results", exist_ok=True)
    out_csv = os.path.join("results", f"{symbol.lower()}_pilot_results.csv")

    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        writer = None
        for params in GRID:
            p = dict(baseline_params)
            p.update(params)
            try:
                res = sim.run_simulation(symbol, interval, df.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=p)
                # Sanitize exported row: do not include initial balance or leverage
                row = {
                    "symbol": symbol,
                    "interval": interval,
                    "params": json.dumps(p, ensure_ascii=False),
                    "profit": res.get("profit", 0.0),
                    "profit_pct": res.get("profit_percentage", 0.0),
                    "total_trades": res.get("total_trades", 0),
                    "win_rate": res.get("win_rate", 0.0),
                    "max_drawdown_pct": res.get("max_drawdown_pct", 0.0),
                }
            except Exception as e:
                row = {"symbol": symbol, "interval": interval, "params": json.dumps(p, ensure_ascii=False), "error": str(e)}

            if writer is None:
                writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
                writer.writeheader()
            writer.writerow(row)
            fh.flush()
            print("Wrote result for", symbol, p)

    print("Pilot finished for", symbol, ". Results ->", out_csv)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", required=True, help="Comma-separated symbols, e.g. PIPPINUSDT")
    p.add_argument("--interval", default="5m", help="Kline interval (1m,5m,1h, etc)")
    p.add_argument("--start", required=False, help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", required=False, help="End date (YYYY-MM-DD)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    for s in syms:
        try:
            run_pilot_for_symbol(s, args.interval, args.start, args.end)
        except Exception as e:
            print(f"Error running pilot for {s}: {e}")


if __name__ == "__main__":
    main()
    
