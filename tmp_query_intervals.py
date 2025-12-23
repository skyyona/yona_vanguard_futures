import sqlite3

db=r'C:\Users\User\new\yona_backtest.db'
conn=sqlite3.connect(db)
cur=conn.cursor()
for row in cur.execute("select interval, count(*) from klines where symbol='XPINUSDT' group by interval order by interval"):
    print(row[0], row[1])
conn.close()
