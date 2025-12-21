import sqlite3
conn=sqlite3.connect('yona_backtest.db')
cur=conn.cursor()
cur.execute("SELECT MIN(open_time), MAX(open_time), COUNT(*) FROM klines WHERE symbol=? AND interval=?",('JELLYJELLYUSDT','1m'))
print(cur.fetchone())
conn.close()
