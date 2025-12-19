import sqlite3
p=r'C:\Users\User\new\yona_vanguard_futures\yona_backtest.db'
try:
    conn=sqlite3.connect(p)
    cur=conn.cursor()
    cur.execute('SELECT name FROM sqlite_master WHERE type="table"')
    print('TABLES:', cur.fetchall())
    cur.execute('SELECT COUNT(*) FROM klines WHERE symbol=? AND interval=?',('ZRCUSDT','1m'))
    cnt=cur.fetchone()[0]
    print('KL_COUNT',cnt)
    if cnt>0:
        cur.execute('SELECT open_time,open,high,low,close,volume FROM klines WHERE symbol=? AND interval=? ORDER BY open_time ASC LIMIT 3',('ZRCUSDT','1m'))
        print('HEAD:', cur.fetchall())
        cur.execute('SELECT open_time,open,high,low,close,volume FROM klines WHERE symbol=? AND interval=? ORDER BY open_time DESC LIMIT 3',('ZRCUSDT','1m'))
        print('TAIL:', cur.fetchall())
except Exception as e:
    print('DB_ERR',e)
finally:
    try:
        conn.close()
    except:
        pass
