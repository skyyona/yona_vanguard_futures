"""Measure scalping grid runtime with per-worker caching (load df and simulator once per worker).

Usage:
  python scripts/measure_scalping_grid_cached.py --symbol PIPPINUSDT --interval 5m --start 2025-11-01 --end 2025-11-30 --grid-size 48 --workers 4
"""
from __future__ import annotations
import argparse, os, sys, time, csv, random
from itertools import product
from multiprocessing import Pool, current_process

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd

# Globals for worker
GLOBAL_DF = None
GLOBAL_SIM = None
GLOBAL_SYMBOL = None
GLOBAL_INTERVAL = None
GLOBAL_START = None
GLOBAL_END = None

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from backtesting_backend.core.strategy_simulator import StrategySimulator


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--interval', default='5m')
    p.add_argument('--start', required=False)
    p.add_argument('--end', required=False)
    p.add_argument('--grid-size', type=int, default=48)
    p.add_argument('--workers', type=int, default=4)
    return p.parse_args()


def load_df(symbol, interval, start=None, end=None):
    # prefer precomputed indicator parquet if present
    parquet_fname = os.path.join('data', f"{symbol}_{interval}_indicators.parquet")
    csv_fname = os.path.join('data', f"{symbol}_{interval}.csv")
    if os.path.exists(parquet_fname):
        df = pd.read_parquet(parquet_fname)
    else:
        if not os.path.exists(csv_fname):
            raise SystemExit('Data file not found: ' + csv_fname)
        df = pd.read_csv(csv_fname, parse_dates=[0], index_col=0)
    if start:
        df = df[df.index >= pd.to_datetime(start)]
    if end:
        df = df[df.index <= pd.to_datetime(end)]
    return df


def worker_init(symbol, interval, start, end):
    global GLOBAL_DF, GLOBAL_SIM, GLOBAL_SYMBOL, GLOBAL_INTERVAL, GLOBAL_START, GLOBAL_END
    GLOBAL_SYMBOL = symbol
    GLOBAL_INTERVAL = interval
    GLOBAL_START = start
    GLOBAL_END = end
    # load df once per worker
    GLOBAL_DF = load_df(symbol, interval, start, end)
    analyzer = StrategyAnalyzer()
    GLOBAL_SIM = StrategySimulator(analyzer=analyzer)
    print(f"Worker {current_process().name} initialized: df rows={len(GLOBAL_DF)}")


def worker_process(params_tuple):
    global GLOBAL_DF, GLOBAL_SIM
    sl, ps, tp, vsf = params_tuple
    params = {
        'fast_ema_period': 3,
        'slow_ema_period': 5,
        'enable_volume_momentum': True,
        'enable_sr_detection': True,
        'enable_sr_filter': True,
        'stop_loss_pct': sl,
        'take_profit_pct': tp,
        'position_size': ps,
        'volume_spike_factor': vsf,
        'volume_avg_period': 20,
    }
    start_t = time.time()
    try:
        res = GLOBAL_SIM.run_simulation(GLOBAL_SYMBOL, GLOBAL_INTERVAL, GLOBAL_DF.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=params)
        elapsed = time.time() - start_t
        return (params, res, elapsed, None)
    except Exception as e:
        elapsed = time.time() - start_t
        return (params, None, elapsed, str(e))


def main():
    args = parse_args()
    symbol = args.symbol.upper()
    interval = args.interval

    stop_losses = [0.002, 0.005, 0.01, 0.02]
    position_sizes = [0.0025, 0.005, 0.01, 0.02]
    take_profits = [0.0, 0.01, 0.02]
    volume_spike_factors = [1.2, 1.4, 1.6]

    all_combos = list(product(stop_losses, position_sizes, take_profits, volume_spike_factors))
    random.shuffle(all_combos)
    grid_size = min(len(all_combos), args.grid_size)
    sampled = all_combos[:grid_size]

    out_dir = 'results'
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"{symbol.lower()}_measure_grid_cached.csv")
    # Build indicator cache once (scalping-focused params) to speed up worker tasks
    cache_parquet = os.path.join('data', f"{symbol}_{interval}_indicators.parquet")
    if not os.path.exists(cache_parquet):
        print('Building indicator cache:', cache_parquet)
        # load raw CSV explicitly
        csv_fname = os.path.join('data', f"{symbol}_{interval}.csv")
        if not os.path.exists(csv_fname):
            raise SystemExit('Data file not found: ' + csv_fname)
        df_raw = pd.read_csv(csv_fname, parse_dates=[0], index_col=0)
        analyzer = StrategyAnalyzer()
        cache_params = {
            'fast_ema_period': 3,
            'slow_ema_period': 5,
            'enable_volume_momentum': True,
            'enable_sr_detection': True,
            'enable_sr_filter': True,
            'volume_avg_period': 20,
            'volume_spike_factor': 1.4,
        }
        df_cached = analyzer.calculate_indicators(df_raw, cache_params)
        # write parquet for workers to use
        try:
            df_cached.to_parquet(cache_parquet)
        except Exception:
            # fallback: write csv if parquet unavailable
            df_cached.to_csv(cache_parquet.replace('.parquet', '.csv'))

    start_all = time.time()
    # use Pool with initializer to load df + sim once per worker
    with Pool(processes=args.workers, initializer=worker_init, initargs=(symbol, interval, args.start, args.end)) as pool:
        results = pool.map(worker_process, sampled)

    total_elapsed = time.time() - start_all
    # write CSV
    with open(out_csv, 'w', newline='', encoding='utf-8') as fh:
        fieldnames = ['stop_loss_pct','position_size','take_profit_pct','volume_spike_factor','profit','profit_pct','total_trades','win_rate','max_drawdown_pct','runtime_sec','error']
        import csv
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        runtimes = []
        errors = []
        for params, res, elapsed, err in results:
            row = {
                'stop_loss_pct': params.get('stop_loss_pct'),
                'position_size': params.get('position_size'),
                'take_profit_pct': params.get('take_profit_pct'),
                'volume_spike_factor': params.get('volume_spike_factor'),
                'profit': res.get('profit') if res else None,
                'profit_pct': res.get('profit_percentage') if res else None,
                'total_trades': res.get('total_trades') if res else None,
                'win_rate': res.get('win_rate') if res else None,
                'max_drawdown_pct': res.get('max_drawdown_pct') if res else None,
                'runtime_sec': elapsed,
                'error': err
            }
            writer.writerow(row)
            if err:
                errors.append(err)
            else:
                runtimes.append(elapsed)

    avg = sum(runtimes)/len(runtimes) if runtimes else None
    print(f"Finished {len(results)} tasks in {total_elapsed:.2f}s, avg per-successful-task={avg:.3f}s, errors={len(errors)}")
    print('Wrote', out_csv)

if __name__ == '__main__':
    main()
