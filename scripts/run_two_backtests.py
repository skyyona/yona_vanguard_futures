import sqlite3
import pandas as pd
import datetime as dt
from backtesting_backend.core.strategy_core import run_backtest

DB_PATH = '../yona_backtest.db'
SYMBOLS = ['LIGHTUSDT', 'WETUSDT']
INTERVAL = '1m'
KL_TABLE = None


def load_klines_from_sqlite(db_path, symbol, interval, start_ms, end_ms, table_name=None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if table_name is None:
        table_name = 'klines'
    query = f"SELECT open_time, open, high, low, close, volume, close_time FROM {table_name} WHERE symbol=? AND interval=? AND open_time BETWEEN ? AND ? ORDER BY open_time"
    cur.execute(query, (symbol, interval, start_ms, end_ms))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["open_time","open","high","low","close","volume","close_time"])
    return df


def run_for(symbol):
    now_ms = int(dt.datetime.utcnow().timestamp() * 1000)
    start_ms = now_ms - 7 * 24 * 60 * 60 * 1000
    end_ms = now_ms
    print(f"Loading klines for {symbol} {INTERVAL} {start_ms}->{end_ms} from {DB_PATH}")
    # detect table name if not known
    global KL_TABLE
    if KL_TABLE is None:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
        print('DB tables:', tables)
        if 'klines' in tables:
            KL_TABLE = 'klines'
        else:
            # try find plausible table names
            cand = [t for t in tables if 'kline' in t.lower() or 'ohlc' in t.lower() or 'candle' in t.lower()]
            KL_TABLE = cand[0] if cand else None
        print('Using kline table:', KL_TABLE)

    df = load_klines_from_sqlite(DB_PATH, symbol, INTERVAL, start_ms, end_ms, table_name=KL_TABLE)
    if df is None or df.empty:
        print(f"No klines for {symbol} in requested range; falling back to full range")
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        table = KL_TABLE or 'klines'
        cur.execute(f"SELECT MIN(open_time), MAX(open_time) FROM {table} WHERE symbol=? AND interval=?", (symbol, INTERVAL))
        r = cur.fetchone()
        conn.close()
        if not r or r[0] is None:
            print(f"No klines present for {symbol} in DB")
            return None
        start_ms, end_ms = r[0], r[1]
        df = load_klines_from_sqlite(DB_PATH, symbol, INTERVAL, start_ms, end_ms)
        if df is None or df.empty:
            print(f"Still no klines for {symbol}")
            return None
    print(f"Loaded {len(df)} klines for {symbol}")
    try:
        res = run_backtest(symbol=symbol, interval=INTERVAL, df=df, initial_balance=1000.0, leverage=1, params={})
    except Exception as e:
        print(f"Backtest failed for {symbol}: {e}")
        return None
    return res


def main():
    summary = []
    for s in SYMBOLS:
        res = run_for(s)
        if res is None:
            continue
        print(f"\n=== RESULT: {s} ===")
        keys = [
            'final_balance','profit','profit_percentage','total_trades','win_rate','max_drawdown_pct','aborted_early','insufficient_trades'
        ]
        for k in keys:
            print(f"{k}: {res.get(k)}")
        summary.append((s, res))
    print('\nDone.')

if __name__ == '__main__':
    main()
