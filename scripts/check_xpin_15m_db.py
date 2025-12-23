import sys
import os
import asyncio

# Ensure project package path is available
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Also add `yona_vanguard_futures` package directory so `backtesting_backend` is importable
YVF = os.path.join(ROOT, 'yona_vanguard_futures')
if os.path.isdir(YVF) and YVF not in sys.path:
    sys.path.insert(0, YVF)

from backtesting_backend.database.db_manager import BacktestDB
from backtesting_backend.database.repositories.kline_repository import KlineRepository

async def main():
    db = BacktestDB.get_instance()
    await db.init()
    repo = KlineRepository()
    rows = await repo.get_klines_in_range('XPINUSDT','15m', 0, 9999999999999)
    print('XPINUSDT 15m rows in DB:', len(rows))
    await db.close()

if __name__ == '__main__':
    asyncio.run(main())
