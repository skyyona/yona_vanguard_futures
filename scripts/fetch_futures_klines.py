"""Fetch futures klines via the backend BinanceClient and save to data/ as CSV.

Usage:
  python scripts/fetch_futures_klines.py --symbol PIPPINUSDT --interval 5m --start 2025-11-23 --end 2025-11-30
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import pandas as pd

# ensure project root importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.api_client.binance_client import BinanceClient


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--interval", default="5m")
    p.add_argument("--start", required=False, help="YYYY-MM-DD")
    p.add_argument("--end", required=False, help="YYYY-MM-DD")
    return p.parse_args()


async def fetch_and_save(symbol: str, interval: str, start: str | None, end: str | None):
    client = BinanceClient()
    try:
        start_ms = int(pd.to_datetime(start).timestamp() * 1000) if start else None
        end_ms = int(pd.to_datetime(end).timestamp() * 1000) if end else None
        klines = await client.get_klines(symbol, interval, start_time=start_ms, end_time=end_ms)
        if not klines:
            print("No klines returned for", symbol)
            return 1

        df = pd.DataFrame(klines)
        # convert open_time to datetime index if present
        if 'open_time' in df.columns:
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df = df.set_index('open_time')

        # keep standard OHLCV
        keep = [c for c in ['open','high','low','close','volume'] if c in df.columns]
        df = df[keep].astype(float)

        os.makedirs('data', exist_ok=True)
        out = os.path.join('data', f"{symbol}_{interval}.csv")
        df.to_csv(out, index_label='open_time')
        print("Wrote:", out)
        return 0
    finally:
        try:
            await client.close()
        except Exception:
            pass


def main():
    args = parse_args()
    rc = asyncio.run(fetch_and_save(args.symbol.upper(), args.interval, args.start, args.end))
    raise SystemExit(rc)


if __name__ == '__main__':
    main()
