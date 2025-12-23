import os
import asyncio

# Ensure DB_PATH points to the collector DB we populated
os.environ.setdefault('DB_PATH', r"C:\Users\User\new\yona_vanguard_futures\backtesting_backend\yona_backtest.db")

from backtesting_backend.database.db_manager import BacktestDB
from backtesting_backend.database.repositories.kline_repository import KlineRepository

async def main():
    db = BacktestDB.get_instance()
    await db.init()
    repo = KlineRepository(session_factory=db.get_session)

    start_ms = 0
    end_ms = 9223372036854775807

    print('Querying repository for XPINUSDT 3m klines...')
    rows = await repo.get_klines_in_range('XPINUSDT', '3m', start_ms, end_ms)
    print('Fetched rows:', len(rows))
    if rows:
        print('First open_time:', rows[0].open_time)
        print('Last  open_time:', rows[-1].open_time)

    latest = await repo.get_latest_kline_time('XPINUSDT', '3m')
    earliest = await repo.get_earliest_kline_time('XPINUSDT', '3m')
    print('Repository earliest open_time:', earliest)
    print('Repository latest   open_time:', latest)

    await db.close()

if __name__ == '__main__':
    asyncio.run(main())
