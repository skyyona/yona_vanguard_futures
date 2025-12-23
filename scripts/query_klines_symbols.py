import sqlite3
import os

db = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'yona_backtest.db'))
print('DB path used:', db)
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT DISTINCT symbol FROM klines LIMIT 200")
rows = cur.fetchall()
print('Distinct symbols (up to 200):')
for r in rows:
    print(r[0])
conn.close()
