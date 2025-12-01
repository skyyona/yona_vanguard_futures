import sqlite3
import os
import sys

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'yona_backtest.db')
if not os.path.exists(DB):
    print('DB_NOT_FOUND', DB)
    sys.exit(2)

conn = sqlite3.connect(DB)
c = conn.cursor()
# Parameters for query will be supplied via env or defaults
symbol = os.environ.get('CHECK_SYMBOL', 'BTCUSDT')
interval = os.environ.get('CHECK_INTERVAL', '1m')
start = int(os.environ.get('CHECK_START', '1672531200000'))
end = int(os.environ.get('CHECK_END', '1672617600000'))

q = "SELECT COUNT(*) FROM klines WHERE symbol=? AND interval=? AND open_time BETWEEN ? AND ?"
res = c.execute(q, (symbol, interval, start, end)).fetchone()
print('DB:', DB)
print('QUERY:', q)
print('PARAMS:', symbol, interval, start, end)
print('COUNT:', res[0] if res else 0)
# print sample rows
rows = c.execute("SELECT open_time, open, high, low, close, volume FROM klines WHERE symbol=? AND interval=? ORDER BY open_time LIMIT 5", (symbol, interval)).fetchall()
print('SAMPLE_ROWS:', rows)
conn.close()