import json
import sqlite3
import pandas as pd
import datetime as dt
from backtesting_backend.core.strategy_core import run_backtest as core_run_backtest

def load_klines_from_sqlite(db_path, symbol, interval, start_ms, end_ms):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT open_time, open, high, low, close, volume, close_time
        FROM klines
        WHERE symbol=? AND interval=? AND open_time BETWEEN ? AND ?
        ORDER BY open_time
        """,
        (symbol, interval, start_ms, end_ms),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["open_time","open","high","low","close","volume","close_time"])
    return df


def main():
    with open('../api_jelly.json', 'r', encoding='utf8') as f:
        api = json.load(f)
    data = api.get('data', {})
    symbol = data.get('symbol')
    interval = data.get('interval')
    period = data.get('period')
    params = data.get('best_parameters', {})

    now_ms = int(dt.datetime.utcnow().timestamp() * 1000)
    if period == '1w':
        start_ms = now_ms - 7 * 24 * 60 * 60 * 1000
    elif period == '1d':
        start_ms = now_ms - 24 * 60 * 60 * 1000
    else:
        start_ms = now_ms - 7 * 24 * 60 * 60 * 1000
    end_ms = now_ms

    db_path = '../yona_backtest.db'
    print(f"Loading klines for {symbol} {interval} {start_ms}->{end_ms} from {db_path}")
    df = load_klines_from_sqlite(db_path, symbol, interval, start_ms, end_ms)
    if df is None or df.empty:
        print('No klines found for slice; falling back to full available range for symbol')
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT MIN(open_time), MAX(open_time) FROM klines WHERE symbol=? AND interval=?", (symbol, interval))
        r = cur.fetchone()
        conn.close()
        if not r or r[0] is None:
            print('No klines present for symbol in DB')
            return
        start_ms, end_ms = r[0], r[1]
        print(f'Falling back to start_ms={start_ms}, end_ms={end_ms}')
        df = load_klines_from_sqlite(db_path, symbol, interval, start_ms, end_ms)
        if df is None or df.empty:
            print('Still no klines found after fallback')
            return
    print(f'Loaded {len(df)} klines')

    print('Running core_run_backtest with parameters:', params)
    res = core_run_backtest(symbol=symbol, interval=interval, df=df, initial_balance=1000.0, leverage=1, params=params)
    print('\n=== SIMULATION RESULT SUMMARY ===')
    for k,v in res.items():
        print(f'{k}: {v}')

if __name__ == '__main__':
    main()
