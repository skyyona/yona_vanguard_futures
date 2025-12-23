import sqlite3

db=r'C:\Users\User\new\yona_backtest.db'
conn=sqlite3.connect(db)
cur=conn.cursor()
for interval in ('1m','3m','15m'):
    try:
        cur.execute('select count(*) from klines where symbol=? and interval=?', ('XPINUSDT', interval))
        print(interval, cur.fetchone()[0])
    except Exception as e:
        print('error', interval, e)
conn.close()
