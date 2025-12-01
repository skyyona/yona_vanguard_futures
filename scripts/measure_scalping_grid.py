"""Measure scalping grid runtime and produce results CSV.

Usage:
  python scripts/measure_scalping_grid.py --symbol PIPPINUSDT --interval 5m --start 2025-11-01 --end 2025-11-30 --grid-size 48 --workers 4
"""
from __future__ import annotations
import argparse, os, sys, time, csv, random
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from backtesting_backend.core.strategy_simulator import StrategySimulator
from pathlib import Path

# central sanitizer (importable)
try:
    from scripts.sanitize_results import sanitize_csv_file
except Exception:
    # fallback import path when running as module
    try:
        from sanitize_results import sanitize_csv_file
    except Exception:
        sanitize_csv_file = None


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--interval', default='5m')
    p.add_argument('--start', required=False)
    p.add_argument('--end', required=False)
    p.add_argument('--grid-size', type=int, default=48)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--early-stop-balance-frac', type=float, default=0.0,
                   help='Abort a combo early if equity <= initial_balance * frac (0 disables)')
    p.add_argument('--min-trades', type=int, default=0,
                   help='Minimum trades required to consider a combo valid (0 disables)')
    p.add_argument('--out-suffix', type=str, default='', help='Optional suffix for output CSV filename')
    return p.parse_args()


def load_df(symbol, interval, start=None, end=None):
    fname = os.path.join('data', f"{symbol}_{interval}.csv")
    if not os.path.exists(fname):
        raise SystemExit('Data file not found: ' + fname)
    df = pd.read_csv(fname, parse_dates=[0], index_col=0)
    if start:
        df = df[df.index >= pd.to_datetime(start)]
    if end:
        df = df[df.index <= pd.to_datetime(end)]
    return df


def worker_task(task):
    # Each worker loads its own small simulator instance to avoid pickling heavy objects
    symbol, interval, start, end, params = task
    start_t = time.time()
    try:
        df = load_df(symbol, interval, start, end)
        analyzer = StrategyAnalyzer()
        sim = StrategySimulator(analyzer=analyzer)
        res = sim.run_simulation(symbol, interval, df.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=params)
        elapsed = time.time() - start_t
        return {'params': params, 'result': res, 'time': elapsed, 'error': None}
    except Exception as e:
        elapsed = time.time() - start_t
        return {'params': params, 'result': None, 'time': elapsed, 'error': str(e)}


def main():
    args = parse_args()
    symbol = args.symbol.upper()
    interval = args.interval

    # define scalping-focused parameter space (smaller ranges, fast EMAs)
    stop_losses = [0.002, 0.005, 0.01, 0.02]
    position_sizes = [0.0025, 0.005, 0.01, 0.02]
    take_profits = [0.0, 0.01, 0.02]
    volume_spike_factors = [1.2, 1.4, 1.6]

    all_combos = list(product(stop_losses, position_sizes, take_profits, volume_spike_factors))
    random.shuffle(all_combos)
    grid_size = min(len(all_combos), args.grid_size)
    sampled = all_combos[:grid_size]

    tasks = []
    for sl, ps, tp, vsf in sampled:
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
            'early_stop_balance_frac': args.early_stop_balance_frac,
            'min_trades': args.min_trades,
        }
        tasks.append((symbol, interval, args.start, args.end, params))

    out_dir = 'results'
    os.makedirs(out_dir, exist_ok=True)
    if args.out_suffix:
        out_csv = os.path.join(out_dir, f"{symbol.lower()}_measure_grid_{args.out_suffix}.csv")
    else:
        suf = ''
        if args.early_stop_balance_frac:
            suf = f"_earlystop_{str(args.early_stop_balance_frac).replace('.','p')}"
        if args.min_trades:
            suf = suf + f"_mintrades_{args.min_trades}"
        out_csv = os.path.join(out_dir, f"{symbol.lower()}_measure_grid{suf}.csv")

    start_all = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(worker_task, t): t for t in tasks}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            # write incremental to CSV
            with open(out_csv, 'a', newline='', encoding='utf-8') as fh:
                fieldnames = ['stop_loss_pct','position_size','take_profit_pct','volume_spike_factor','profit','profit_pct','total_trades','win_rate','max_drawdown_pct','aborted_early','insufficient_trades','runtime_sec','error']
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                if fh.tell() == 0:
                    writer.writeheader()
                params = r.get('params', {})
                res = r.get('result') or {}
                row = {
                    'stop_loss_pct': params.get('stop_loss_pct'),
                    'position_size': params.get('position_size'),
                    'take_profit_pct': params.get('take_profit_pct'),
                    'volume_spike_factor': params.get('volume_spike_factor'),
                    'profit': res.get('profit'),
                    'profit_pct': res.get('profit_percentage'),
                    'total_trades': res.get('total_trades'),
                    'win_rate': res.get('win_rate'),
                    'max_drawdown_pct': res.get('max_drawdown_pct'),
                    'aborted_early': res.get('aborted_early'),
                    'insufficient_trades': res.get('insufficient_trades'),
                    'runtime_sec': r.get('time'),
                    'error': r.get('error')
                }
                writer.writerow(row)

    total_elapsed = time.time() - start_all
    # summary
    runtimes = [r['time'] for r in results if r['error'] is None]
    errors = [r for r in results if r['error']]
    avg = sum(runtimes)/len(runtimes) if runtimes else None
    print(f"Finished {len(results)} tasks in {total_elapsed:.2f}s, avg per-successful-task={avg:.3f}s, errors={len(errors)}")
    print('Wrote', out_csv)

    # sanitize the produced CSV to remove any sensitive columns if present
    if sanitize_csv_file is not None:
        try:
            out = sanitize_csv_file(Path(out_csv), inplace=False, dry_run=False)
            if out:
                print(f"Sanitized output -> {out}")
            else:
                print("No sensitive columns found in output.")
        except Exception as e:
            print(f"Sanitization failed: {e}")

if __name__ == '__main__':
    main()
