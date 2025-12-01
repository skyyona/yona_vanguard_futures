"""Ingest local data/{symbol}_{interval}.csv into the backtesting DB Kline table.

Usage:
  python scripts/ingest_csv_to_db.py --symbol PIPPINUSDT --interval 5m
"""
from __future__ import annotations

import argparse
import os
import sys
import pandas as pd

# ensure project root importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.database.repositories.kline_repository import KlineRepository


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--interval", required=True)
    return p.parse_args()


def df_to_klines(df: pd.DataFrame, symbol: str, interval: str):
    # Ensure index is datetime
    if not pd.api.types.is_datetime64_any_dtype(df.index):
        df.index = pd.to_datetime(df.index)

    # interval to ms
    if interval.endswith('m'):
        interval_ms = int(interval[:-1]) * 60 * 1000
    elif interval.endswith('h'):
        interval_ms = int(interval[:-1]) * 60 * 60 * 1000
    elif interval.endswith('d'):
        interval_ms = int(interval[:-1]) * 24 * 60 * 60 * 1000
    else:
        interval_ms = 0

    out = []
    for idx, row in df.iterrows():
        open_time_ms = int(pd.to_datetime(idx).timestamp() * 1000)
        close_time_ms = open_time_ms + interval_ms
        d = {
            'symbol': symbol,
            'interval': interval,
            'open_time': open_time_ms,
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume']),
            'close_time': int(close_time_ms),
            'quote_asset_volume': None,
            'number_of_trades': None,
            'taker_buy_base_asset_volume': None,
            'taker_buy_quote_asset_volume': None,
            'ignore': None,
        }
        out.append(d)
    return out


def main():
    args = parse_args()
    fname = os.path.join('data', f"{args.symbol}_{args.interval}.csv")
    if not os.path.exists(fname):
        print('File not found:', fname)
        raise SystemExit(1)

    df = pd.read_csv(fname, parse_dates=[0], index_col=0)
    required = {'open','high','low','close','volume'}
    if not required <= set(df.columns):
        print('CSV missing required columns')
        raise SystemExit(1)

    klines = df_to_klines(df, args.symbol, args.interval)

    repo = KlineRepository()

    import asyncio
    from backtesting_backend.database.db_manager import BacktestDB

    async def _runner():
        # ensure DB/tables initialized
        db = BacktestDB.get_instance()
        await db.init()
        await repo.bulk_insert_klines(klines)

    asyncio.run(_runner())
    print('Ingested', len(klines), 'klines into DB for', args.symbol)


if __name__ == '__main__':
    main()
