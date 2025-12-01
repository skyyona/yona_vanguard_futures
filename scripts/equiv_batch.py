"""Run equivalence tests (cached vs runtime indicators) across multiple symbols and parameter sets.

Writes per-case JSONs (sanitized) into results/ and a summary CSV `results/equiv_summary.csv`.
"""
from __future__ import annotations
import os, sys, json, csv
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
    # compare trades count
    t1 = r1.get('trades', [])
    t2 = r2.get('trades', [])
    if len(t1) != len(t2):
        diffs.append(('trades_len', len(t1), len(t2)))
    return diffs


def sanitize(r):
    if not isinstance(r, dict):
        return r
    s = dict(r)
    for k in ('initial_balance', 'leverage'):
        if k in s:
            s.pop(k, None)
    return s


def main():
    # configuration
    symbols = ['PIPPINUSDT', 'INUSDT', 'BTCUSDT']
    interval = '5m'
    start = '2025-11-01'
    end = '2025-11-30'

    # 5 representative scalping param sets
    param_sets = [
        {'fast_ema_period':3,'slow_ema_period':5,'stop_loss_pct':0.002,'take_profit_pct':0.01,'position_size':0.0025,'volume_spike_factor':1.2,'volume_avg_period':20},
        {'fast_ema_period':3,'slow_ema_period':5,'stop_loss_pct':0.005,'take_profit_pct':0.02,'position_size':0.005,'volume_spike_factor':1.4,'volume_avg_period':20},
        {'fast_ema_period':3,'slow_ema_period':5,'stop_loss_pct':0.01,'take_profit_pct':0.02,'position_size':0.01,'volume_spike_factor':1.6,'volume_avg_period':20},
        {'fast_ema_period':5,'slow_ema_period':8,'stop_loss_pct':0.005,'take_profit_pct':0.01,'position_size':0.005,'volume_spike_factor':1.4,'volume_avg_period':20},
        {'fast_ema_period':3,'slow_ema_period':5,'stop_loss_pct':0.02,'take_profit_pct':0.0,'position_size':0.02,'volume_spike_factor':2.0,'volume_avg_period':20},
    ]

    os.makedirs('results', exist_ok=True)
    summary_path = os.path.join('results','equiv_summary.csv')
    with open(summary_path, 'w', newline='', encoding='utf-8') as sf:
        writer = csv.DictWriter(sf, fieldnames=['symbol','case_id','equivalent','notes'])
        writer.writeheader()

        for sym in symbols:
            df_raw = load_csv(sym, interval, start, end)
            analyzer = StrategyAnalyzer()
            sim = StrategySimulator(analyzer=analyzer)
            for i, params in enumerate(param_sets):
                case_id = f"{sym}_case{i+1}"
                print('Running', case_id)
                res_runtime = sim.run_simulation(sym, interval, df_raw.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=params)
                df_cached = analyzer.calculate_indicators(df_raw.copy(), params)
                res_cached = sim.run_simulation(sym, interval, df_cached.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=params)
                diffs = compare_results(res_runtime, res_cached)
                eq = (len(diffs) == 0)
                notes = '' if eq else str(diffs)
                writer.writerow({'symbol':sym,'case_id':case_id,'equivalent':eq,'notes':notes})

                # write sanitized per-case JSONs
                with open(os.path.join('results', f"equiv_{case_id}_runtime.json"), 'w', encoding='utf-8') as fh:
                    json.dump(sanitize(res_runtime), fh, default=str, indent=2)
                with open(os.path.join('results', f"equiv_{case_id}_cached.json"), 'w', encoding='utf-8') as fh:
                    json.dump(sanitize(res_cached), fh, default=str, indent=2)

    print('Wrote summary to', summary_path)


if __name__ == '__main__':
    main()
