"""Walk-forward verification for candidate strategy parameters.

Usage:
  python scripts/walk_forward_verify.py --symbol PIPPINUSDT --interval 5m --start 2025-11-01 --end 2025-11-30 --candidates results/pippinusdt_measure_grid.csv --top-n 10 --windows 3
"""
from __future__ import annotations
import argparse, os, sys, csv
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
from statistics import mean, pstdev

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from backtesting_backend.core.strategy_simulator import StrategySimulator


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--interval', default='5m')
    p.add_argument('--start', required=False)
    p.add_argument('--end', required=False)
    p.add_argument('--candidates', required=False, help='CSV of candidate params (from measure script)')
    p.add_argument('--top-n', type=int, default=10)
    p.add_argument('--windows', type=int, default=3)
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


def read_candidates(path, top_n=10):
    rows = []
    with open(path, newline='', encoding='utf-8') as fh:
        dr = csv.DictReader(fh)
        for r in dr:
            rows.append(r)
    # sort by profit_pct desc
    rows_sorted = sorted(rows, key=lambda r: float(r.get('profit_pct') or 0), reverse=True)
    return rows_sorted[:top_n]


def parse_params_from_row(row):
    # rows contain stop_loss_pct, position_size, take_profit_pct, volume_spike_factor
    return {
        'fast_ema_period': 3,
        'slow_ema_period': 5,
        'enable_volume_momentum': True,
        'enable_sr_detection': True,
        'enable_sr_filter': True,
        'stop_loss_pct': float(row.get('stop_loss_pct') or 0.005),
        'take_profit_pct': float(row.get('take_profit_pct') or 0.0),
        'position_size': float(row.get('position_size') or 0.005),
        'volume_spike_factor': float(row.get('volume_spike_factor') or 1.4),
        'volume_avg_period': 20,
    }


def windows_from_df(df, windows):
    n = len(df)
    if n < windows * 4:
        # require reasonable data per window; fallback to simple contiguous splits
        size = max(1, n // (windows + 1))
    else:
        size = n // (windows + 1)
    parts = []
    for i in range(windows):
        train_end = size * (i + 1)
        test_start = train_end
        test_end = min(n, test_start + size)
        if test_end - test_start < 2:
            continue
        parts.append((0, train_end, test_start, test_end))
    return parts


def run_wf_for_candidate(sim, df, windows, params):
    parts = windows_from_df(df, windows)
    results = []
    for train_s, train_e, test_s, test_e in parts:
        df_test = df.iloc[test_s:test_e].copy()
        res = sim.run_simulation('symbol', 'int', df_test, initial_balance=1000.0, leverage=1, strategy_parameters=params)
        results.append(res.get('profit_percentage', 0.0))
    return results


def main():
    args = parse_args()
    symbol = args.symbol.upper()
    df = load_df(symbol, args.interval, args.start, args.end)
    # load candidates
    cand_path = args.candidates or os.path.join('results', f"{symbol.lower()}_measure_grid.csv")
    if not os.path.exists(cand_path):
        raise SystemExit('Candidates CSV not found: ' + cand_path)
    cand_rows = read_candidates(cand_path, top_n=args.top_n)

    analyzer = StrategyAnalyzer()
    sim = StrategySimulator(analyzer=analyzer)

    out_rows = []
    for i, row in enumerate(cand_rows, start=1):
        params = parse_params_from_row(row)
        wf_profits = run_wf_for_candidate(sim, df, args.windows, params)
        mean_pf = mean(wf_profits) if wf_profits else 0.0
        std_pf = pstdev(wf_profits) if len(wf_profits) > 1 else 0.0
        positive_count = sum(1 for p in wf_profits if p > 0)
        out_rows.append({
            'rank': i,
            'stop_loss_pct': params['stop_loss_pct'],
            'position_size': params['position_size'],
            'take_profit_pct': params['take_profit_pct'],
            'volume_spike_factor': params['volume_spike_factor'],
            'wf_mean_profit_pct': mean_pf,
            'wf_std_profit_pct': std_pf,
            'wf_positive_windows': positive_count,
            'wf_profits_list': ';'.join(f"{p:.6f}" for p in wf_profits),
        })

    out_dir = 'results'
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"{symbol.lower()}_wf_verify.csv")
    fieldnames = ['rank','stop_loss_pct','position_size','take_profit_pct','volume_spike_factor','wf_mean_profit_pct','wf_std_profit_pct','wf_positive_windows','wf_profits_list']
    with open(out_csv, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in out_rows:
            writer.writerow(r)

    print('Wrote', out_csv)


if __name__ == '__main__':
    main()
