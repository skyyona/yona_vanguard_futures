import sqlite3
import sys

db=r"C:\Users\User\new\yona_backtest.db"
con=sqlite3.connect(db)
cur=con.cursor()
for interval in ('1m','3m','15m'):
    try:
        cur.execute('select count(*) from klines where symbol=? and interval=?',( 'XPINUSDT', interval))
        print(interval, cur.fetchone()[0])
    except Exception as e:
        print('error',interval,e)
con.close()
