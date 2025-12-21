import sys, os, asyncio, time, json
sys.path.insert(0, os.path.join(os.getcwd(), 'yona_vanguard_futures'))
from backtesting_backend.core.data_loader import DataLoader
from backtesting_backend.database.db_manager import BacktestDB
from backtesting_backend.api_client.binance_client import BinanceClient
from backtesting_backend.database.repositories.kline_repository import KlineRepository
from backtesting_backend.core.strategy_core import run_backtest

OUT_DIR = os.path.join(os.getcwd(), 'backtest_results_mtf')
os.makedirs(OUT_DIR, exist_ok=True)

SYMBOLS = ['BTCUSDT','JELLYJELLYUSDT']
INTERVAL = '1m'
DAYS = 7

async def run_for(symbol, interval=INTERVAL, days=DAYS, params=None, suffix=''):
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
        res = run_backtest(symbol=symbol, interval=interval, df=df, initial_balance=1000.0, leverage=1, params=params or {})
        return res
    except Exception as e:
        print(f"Backtest failed for {symbol}: {e}")
        return None

async def main():
    await BacktestDB.get_instance().init()
    summary = []
    for s in SYMBOLS:
        mtf_loose_params = {"enable_mtf_stoch": True, "mtf_loose_mode": True, "mtf_oversold_threshold": 20.0}
        print(f"Running MTF-loose enabled for {s}")
        res_mtf_loose = await run_for(s, INTERVAL, DAYS, params=mtf_loose_params)
        if res_mtf_loose:
            out_path = os.path.join(OUT_DIR, f"mtf_loose_{s}_{INTERVAL}_{DAYS}d.json")
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(res_mtf_loose, f, default=str, ensure_ascii=False, indent=2)
            print(f"Saved {out_path}")

        summary.append({
            'symbol': s,
            'mtf_loose': res_mtf_loose
        })

    summary_path = os.path.join(OUT_DIR, 'comparison_summary_loose.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, default=str, ensure_ascii=False, indent=2)
    print('Done. Summary written to', summary_path)

if __name__ == '__main__':
    asyncio.run(main())
