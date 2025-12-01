"""Expanded grid search for a symbol using StrategySimulator.
Outputs CSV to results/{symbol.lower()}_grid_search.csv
"""
from __future__ import annotations
import argparse, csv, os, json, sys
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from backtesting_backend.core.strategy_simulator import StrategySimulator


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--interval', default='5m')
    p.add_argument('--start', required=False)
    p.add_argument('--end', required=False)
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


def main():
    args = parse_args()
    symbol = args.symbol.upper()
    interval = args.interval
    df = load_df(symbol, interval, args.start, args.end)

    analyzer = StrategyAnalyzer()
    sim = StrategySimulator(analyzer=analyzer)

    # grid
    stop_losses = [0.005, 0.01, 0.02, 0.03]
    position_sizes = [0.005, 0.01, 0.02, 0.04]
    take_profits = [0.00, 0.02, 0.05]
    volume_spike_factors = [1.4, 1.6, 2.0]

    out_dir = 'results'
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"{symbol.lower()}_grid_search.csv")

    with open(out_csv, 'w', newline='', encoding='utf-8') as fh:
        fieldnames = ['stop_loss_pct','position_size','take_profit_pct','volume_spike_factor','profit','profit_pct','total_trades','win_rate','max_drawdown_pct']
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        total = 0
        for sl in stop_losses:
            for ps in position_sizes:
                for tp in take_profits:
                    for vsf in volume_spike_factors:
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
                        try:
                            res = sim.run_simulation(symbol, interval, df.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=params)
                            row = {
                                'stop_loss_pct': sl,
                                'position_size': ps,
                                'take_profit_pct': tp,
                                'volume_spike_factor': vsf,
                                'profit': res.get('profit', 0.0),
                                'profit_pct': res.get('profit_percentage', 0.0),
                                'total_trades': res.get('total_trades', 0),
                                'win_rate': res.get('win_rate', 0.0),
                                'max_drawdown_pct': res.get('max_drawdown_pct', 0.0),
                            }
                        except Exception as e:
                            row = {'stop_loss_pct': sl,'position_size': ps,'take_profit_pct': tp,'volume_spike_factor': vsf,'profit': None,'profit_pct': None,'total_trades': None,'win_rate': None,'max_drawdown_pct': None}
                        writer.writerow(row)
                        fh.flush()
                        total += 1
        print('Grid search finished, wrote', out_csv)

if __name__ == '__main__':
    main()
