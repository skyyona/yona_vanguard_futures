import sys, os, asyncio, time, json
sys.path.insert(0, os.path.join(os.getcwd(), 'yona_vanguard_futures'))
from backtesting_backend.core.data_loader import DataLoader
from backtesting_backend.database.db_manager import BacktestDB
from backtesting_backend.api_client.binance_client import BinanceClient
from backtesting_backend.database.repositories.kline_repository import KlineRepository
from backtesting_backend.core.strategy_core import run_backtest

from scripts.output_config import legacy_dir

OUT_DIR = os.path.join(legacy_dir(), 'backtest_results_extended')
os.makedirs(OUT_DIR, exist_ok=True)

SYMBOLS = ['BTCUSDT','ETHUSDT','SOLUSDT','ADAUSDT','XRPUSDT','LTCUSDT']
INTERVAL = '5m'
DAYS = 7

async def run_for(symbol, interval=INTERVAL, days=DAYS):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - days * 24 * 60 * 60 * 1000
    client = BinanceClient()
    repo = KlineRepository()
    loader = DataLoader(binance_client=client, kline_repo=repo)
    print(f"Loading klines for {symbol} {interval} {days} day(s) -> {start_ms} to {now_ms}")
    try:
        await loader.load_historical_klines(symbol, interval, start_ms, now_ms)
        df = await loader.get_klines_for_backtest(symbol, interval, start_ms, now_ms)
    except Exception as e:
        print(f"Failed to load klines for {symbol}: {e}")
        return None
    print(f"Klines loaded: rows={len(df)} index_start={df.index[0] if len(df)>0 else 'N/A'}")
    try:
        res = run_backtest(symbol=symbol, interval=interval, df=df, initial_balance=1000.0, leverage=1, params={})
        return res
    except Exception as e:
        print(f"Backtest failed for {symbol}: {e}")
        return None

async def main():
    await BacktestDB.get_instance().init()
    summary = []
    for s in SYMBOLS:
        res = await run_for(s, INTERVAL, DAYS)
        if res is None:
            continue
        out_path = os.path.join(OUT_DIR, f"{s}_{INTERVAL}_{DAYS}d.json")
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(res, f, default=str, ensure_ascii=False, indent=2)
        print(f"Saved {out_path}")
        summary.append({
            'symbol': s,
            'total_trades': res.get('total_trades'),
            'profit_percentage': res.get('profit_percentage'),
            'max_drawdown_pct': res.get('max_drawdown_pct'),
            'win_rate': res.get('win_rate')
        })
    summary_md = os.path.join(OUT_DIR, 'summary.md')
    with open(summary_md, 'w', encoding='utf-8') as f:
        f.write('# Extended Backtest Summary\n\n')
        for s in summary:
            f.write(f"- {s['symbol']}: trades={s['total_trades']}, profit_pct={s['profit_percentage']}, max_dd={s['max_drawdown_pct']}, win_rate={s['win_rate']}\n")
    print('Done. Summary written to', summary_md)

if __name__ == '__main__':
    asyncio.run(main())
