import asyncio
import time
import os
import json
import datetime as dt

from backtesting_backend.database.db_manager import BacktestDB
from backtesting_backend.database.repositories.kline_repository import KlineRepository
from backtesting_backend.core.strategy_core import run_backtest
from scripts.output_config import backtest_dir

SYMBOL = 'XPINUSDT'
INTERVAL = '1m'
DAYS = 7
OUT_DIR = backtest_dir()

async def main():
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - DAYS * 24 * 60 * 60 * 1000

    db = BacktestDB.get_instance()
    await db.init()
    repo = KlineRepository(session_factory=db.get_session)

    print(f"Loading klines for {SYMBOL} {INTERVAL} from {dt.datetime.utcfromtimestamp(start_ms/1000)} to {dt.datetime.utcfromtimestamp(now_ms/1000)}")
    df = await repo.get_klines_for_backtest(SYMBOL, INTERVAL, start_ms, now_ms)
    if df is None or df.empty:
        print('No klines found in backtest DB for symbol; attempting to use DataLoader to fetch from exchange')
        try:
            from backtesting_backend.core.data_loader import DataLoader
            from backtesting_backend.api_client.binance_client import BinanceClient
            client = BinanceClient()
            loader = DataLoader(binance_client=client, kline_repo=repo)
            await loader.load_historical_klines(SYMBOL, INTERVAL, start_ms, now_ms)
            df = await loader.get_klines_for_backtest(SYMBOL, INTERVAL, start_ms, now_ms)
        except Exception as e:
            print('Failed to fetch klines from exchange:', e)
            return

    print(f'Klines loaded: rows={len(df)}')

    params = {}
    print('Running backtest...')
    try:
        res = run_backtest(symbol=SYMBOL, interval=INTERVAL, df=df, initial_balance=1000.0, leverage=1, params=params)
    except Exception as e:
        print('Backtest execution failed:', e)
        return

    out_path = os.path.join(OUT_DIR, f"backtest_{SYMBOL}_{INTERVAL}_{DAYS}d.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(res, f, default=str, ensure_ascii=False, indent=2)
    print('Saved result to', out_path)
    print('\nSummary:')
    for k in ['net_pnl','total_trades','win_rate','max_drawdown']:
        print(k, ':', res.get(k))

if __name__ == '__main__':
    asyncio.run(main())
