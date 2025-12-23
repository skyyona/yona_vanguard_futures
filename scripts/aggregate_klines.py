#!/usr/bin/env python3
"""Aggregate existing 1m klines into 3m and 15m intervals for a symbol.

Usage: python scripts/aggregate_klines.py --db <path> --symbol BEATUSDT
"""
import argparse
import sqlite3
import math
from collections import defaultdict


def fetch_min_max(conn, symbol, interval='1m'):
    cur = conn.cursor()
    cur.execute("SELECT MIN(open_time), MAX(open_time) FROM klines WHERE symbol=? AND interval=?", (symbol, interval))
    row = cur.fetchone()
    return row[0], row[1]


def fetch_1m_rows(conn, symbol, start_ms, end_ms):
    cur = conn.cursor()
    cur.execute(
        "SELECT open_time, open, high, low, close, volume, close_time, quote_asset_volume, number_of_trades, taker_buy_base_asset_volume, taker_buy_quote_asset_volume, \"ignore\" FROM klines WHERE symbol=? AND interval='1m' AND open_time>=? AND open_time<=? ORDER BY open_time",
        (symbol, start_ms, end_ms),
    )
    return cur.fetchall()


def insert_candle(conn, symbol, interval, open_time, open_p, high, low, close_p, volume, close_time, quote_vol, trades, taker_base, taker_quote, ignore_val):
    cur = conn.cursor()
    # check existing
    cur.execute("SELECT 1 FROM klines WHERE symbol=? AND interval=? AND open_time=?", (symbol, interval, open_time))
    if cur.fetchone():
        return False
    cur.execute(
        "INSERT INTO klines (symbol, interval, open_time, open, high, low, close, volume, close_time, quote_asset_volume, number_of_trades, taker_buy_base_asset_volume, taker_buy_quote_asset_volume, \"ignore\") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (symbol, interval, open_time, str(open_p), str(high), str(low), str(close_p), str(volume), close_time, str(quote_vol), trades, str(taker_base), str(taker_quote), str(ignore_val)),
    )
    return True


def aggregate_and_insert(conn, symbol, target_min):
    interval_ms = target_min * 60 * 1000
    min_open, max_open = fetch_min_max(conn, symbol, '1m')
    if min_open is None:
        print(f'No 1m rows for {symbol} — nothing to do')
        return 0
    # align start to interval boundary
    start = (min_open // interval_ms) * interval_ms
    end = (max_open // interval_ms) * interval_ms
    rows = fetch_1m_rows(conn, symbol, start, end + interval_ms - 1)
    if not rows:
        print('No 1m rows in range')
        return 0

    # group by bucket
    buckets = defaultdict(list)
    for r in rows:
        open_time = int(r[0])
        bucket = (open_time // interval_ms) * interval_ms
        buckets[bucket].append(r)

    inserted = 0
    for bucket_start in sorted(buckets.keys()):
        group = buckets[bucket_start]
        opens = [float(g[1]) for g in group]
        highs = [float(g[2]) for g in group]
        lows = [float(g[3]) for g in group]
        closes = [float(g[4]) for g in group]
        vols = [float(g[5]) for g in group]
        quote_vols = [float(g[7] or 0) for g in group]
        trades = sum(int(g[8] or 0) for g in group)
        taker_base = sum(float(g[9] or 0) for g in group)
        taker_quote = sum(float(g[10] or 0) for g in group)
        open_price = opens[0]
        close_price = closes[-1]
        high = max(highs)
        low = min(lows)
        volume = sum(vols)
        quote_vol = sum(quote_vols)
        close_time = bucket_start + interval_ms - 1
        ok = insert_candle(conn, symbol, f'{target_min}m', bucket_start, open_price, high, low, close_price, volume, close_time, quote_vol, trades, taker_base, taker_quote, 0)
        if ok:
            inserted += 1
    conn.commit()
    print(f'Inserted {inserted} {target_min}m candles for {symbol}')
    return inserted


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', required=True)
    p.add_argument('--symbol', required=True)
    args = p.parse_args()
    conn = sqlite3.connect(args.db)
    try:
        inserted3 = aggregate_and_insert(conn, args.symbol, 3)
        inserted15 = aggregate_and_insert(conn, args.symbol, 15)
        print('Done')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
