import json
import asyncio
import datetime as dt
from backtesting_backend.database.db_manager import BacktestDB
from backtesting_backend.database.repositories.kline_repository import KlineRepository
from backtesting_backend.core.strategy_core import run_backtest as core_run_backtest

async def main():
    # load API response
    with open('api_jelly.json', 'r', encoding='utf8') as f:
        api = json.load(f)
    data = api.get('data', {})
    symbol = data.get('symbol')
    interval = data.get('interval')
    period = data.get('period')
    params = data.get('best_parameters', {})

    now_ms = int(dt.datetime.utcnow().timestamp() * 1000)
    if period == '1w':
        start_ms = now_ms - 7 * 24 * 60 * 60 * 1000
    elif period == '1d':
        start_ms = now_ms - 24 * 60 * 60 * 1000
    else:
        start_ms = now_ms - 7 * 24 * 60 * 60 * 1000
    end_ms = now_ms

    # init DB and repo
    db = BacktestDB.get_instance()
    await db.init()
    repo = KlineRepository(session_factory=db.get_session)

    print(f"Loading klines for {symbol} {interval} {start_ms}->{end_ms}")
    df = await repo.get_klines_for_backtest(symbol, interval, start_ms, end_ms)
    if df is None or df.empty:
        print('No klines found for slice')
        return
    print(f'Loaded {len(df)} klines')

    # Run backtest with verbose tracing by wrapping core_run_backtest result printing
    print('Running core_run_backtest with parameters:', params)
    res = core_run_backtest(symbol=symbol, interval=interval, df=df, initial_balance=1000.0, leverage=1, params=params)
    print('\n=== SIMULATION RESULT SUMMARY ===')
    for k,v in res.items():
        print(f'{k}: {v}')

if __name__ == '__main__':
    asyncio.run(main())
