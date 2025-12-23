"""Equivalence test: cached indicators vs runtime calculation.

Usage:
  python scripts/equivalence_cached_vs_runtime.py --symbol PIPPINUSDT --interval 5m --start 2025-11-01 --end 2025-11-30
"""
from __future__ import annotations
import os, sys, json, math
from scripts.output_config import legacy_dir
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from backtesting_backend.core.strategy_simulator import StrategySimulator


def load_csv(symbol, interval, start=None, end=None):
    fname = os.path.join('data', f"{symbol}_{interval}.csv")
    if not os.path.exists(fname):
        raise SystemExit('Data file not found: ' + fname)
    df = pd.read_csv(fname, parse_dates=[0], index_col=0)
    if start:
        df = df[df.index >= pd.to_datetime(start)]
    if end:
        df = df[df.index <= pd.to_datetime(end)]
    return df


def approx_equal(a, b, tol=1e-8):
    if a is None and b is None:
        return True
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return a == b


def compare_results(r1, r2):
    keys = ['profit', 'profit_percentage', 'total_trades', 'win_rate', 'max_drawdown_pct']
    diffs = []
    for k in keys:
        v1 = r1.get(k)
        v2 = r2.get(k)
        if v1 is None and v2 is None:
            continue
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            if not approx_equal(v1, v2, tol=1e-6):
                diffs.append((k, v1, v2))
        else:
            if v1 != v2:
                diffs.append((k, v1, v2))
    # compare trades count and a few trade-level fields
    t1 = r1.get('trades', [])
    t2 = r2.get('trades', [])
    if len(t1) != len(t2):
        diffs.append(('trades_len', len(t1), len(t2)))
    else:
        for i, (a, b) in enumerate(zip(t1, t2)):
            # compare entry_price, exit_price, exit_reason
            for fld in ('entry_price', 'exit_price', 'exit_reason'):
                va = a.get(fld)
                vb = b.get(fld)
                if not approx_equal(va, vb, tol=1e-6):
                    diffs.append((f'trade[{i}].{fld}', va, vb))
    return diffs


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--interval', default='5m')
    p.add_argument('--start', required=False)
    p.add_argument('--end', required=False)
    args = p.parse_args()

    symbol = args.symbol.upper()
    interval = args.interval
    df_raw = load_csv(symbol, interval, args.start, args.end)

    # dump both results for inspection into outputs/legacy/equiv_results
    sim = StrategySimulator(analyzer=analyzer)
    results_dir = os.path.join(legacy_dir(), 'equiv_results')
    # representative scalping params
    params = {
        'fast_ema_period': 3,
        'slow_ema_period': 5,
        'enable_volume_momentum': True,
        'enable_sr_detection': True,
        'enable_sr_filter': True,
        'stop_loss_pct': 0.005,
        'take_profit_pct': 0.01,
        'position_size': 0.005,
        'volume_spike_factor': 1.4,
        'volume_avg_period': 20,
    }

    print('Running runtime (on-the-fly) indicators...')
    res_runtime = sim.run_simulation(symbol, interval, df_raw.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=params)

    print('Building cached indicators and running cached path...')
    df_cached = analyzer.calculate_indicators(df_raw.copy(), params)
    # run_simulation should detect indicators present and skip recalculation
    res_cached = sim.run_simulation(symbol, interval, df_cached.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=params)

    diffs = compare_results(res_runtime, res_cached)
    if not diffs:
        print('EQUIVALENT: runtime vs cached outputs match exactly (within tolerance).')
        print('Summary:', {k: res_runtime.get(k) for k in ['profit','profit_percentage','total_trades','win_rate','max_drawdown_pct']})
        return 0
    else:
        print('DIFFERENCES FOUND:')
        for d in diffs:
            print(' -', d)
        # dump both results for inspection into outputs/legacy/results
        # sanitize outputs to avoid including user capital/leverage in shared files
        results_dir = os.path.join(legacy_dir(), 'results')
        os.makedirs(results_dir, exist_ok=True)
        def _sanitize(r):
            if not isinstance(r, dict):
                return r
            s = dict(r)
            for k in ('initial_balance', 'leverage'):
                if k in s:
                    s.pop(k, None)
            return s

        runtime_path = os.path.join(results_dir, 'equiv_runtime.json')
        cached_path = os.path.join(results_dir, 'equiv_cached.json')
        with open(runtime_path, 'w', encoding='utf-8') as fh:
            json.dump(_sanitize(res_runtime), fh, default=str, indent=2)
        with open(cached_path, 'w', encoding='utf-8') as fh:
            json.dump(_sanitize(res_cached), fh, default=str, indent=2)
        print(f'Wrote {runtime_path} and {cached_path}')
        return 2

if __name__ == '__main__':
    sys.exit(main())
