import sqlite3, os
p='yona_backtest.db'
print('DB exists?', os.path.exists(p))
conn=sqlite3.connect(p)
cur=conn.cursor()
cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view')")
print(cur.fetchall())
conn.close()
