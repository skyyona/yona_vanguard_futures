import os
import sqlite3

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Search for possible backtest DB files named 'yona_backtest.db'
candidates = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    for fn in filenames:
        if fn == 'yona_backtest.db':
            candidates.append(os.path.join(dirpath, fn))

if not candidates:
    print('No yona_backtest.db found under', ROOT)
    # Also try common path
    alt = os.path.join(ROOT, 'yona_vanguard_futures', 'backtesting_backend', 'yona_backtest.db')
    if os.path.isfile(alt):
        candidates.append(alt)

if not candidates:
    print('No DB candidates found. Exiting.')
    raise SystemExit(1)

for dbpath in candidates:
    print('Checking DB:', dbpath)
    try:
        conn = sqlite3.connect(dbpath)
        cur = conn.cursor()
        # Check if klines table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='klines'")
        if not cur.fetchone():
            print('  table `klines` not found in', dbpath)
            conn.close()
            continue
        # Count rows for symbol/interval
        cur.execute("SELECT COUNT(*) FROM klines WHERE symbol=? AND interval=?", ('XPINUSDT', '15m'))
        count = cur.fetchone()[0]
        print('  XPINUSDT 15m rows in DB:', count)
        conn.close()
    except Exception as e:
        print('  Error querying DB', dbpath, e)
