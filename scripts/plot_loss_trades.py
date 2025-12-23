"""Plot top loss trades per candidate using extracted traces.

Usage:
  python scripts/plot_loss_trades.py --symbol PIPPINUSDT --samples 5
"""
from __future__ import annotations
import os, csv, argparse, json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
import sys
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from scripts.output_config import legacy_dir


def read_all_trades(traces_dir: str):
    # collect all trades CSVs under traces_dir/rank_*/run_*.csv
    rows = []
    for rank_dir in sorted(os.listdir(traces_dir)):
        rd = os.path.join(traces_dir, rank_dir)
        if not os.path.isdir(rd):
            continue
        try:
            rank = int(rank_dir.split('_')[-1])
        except Exception:
            rank = None
        for fn in sorted(os.listdir(rd)):
            if fn.endswith('_trades.csv'):
                path = os.path.join(rd, fn)
                try:
                    df = pd.read_csv(path, parse_dates=['entry_index','exit_index'])
                except Exception:
                    df = pd.read_csv(path)
                    # try to coerce indices
                    for c in ['entry_index','exit_index']:
                        if c in df.columns:
                            df[c] = pd.to_datetime(df[c], errors='coerce')
                for _, r in df.iterrows():
                    rdict = r.to_dict()
                    rdict['rank'] = rank
                    rdict['source_file'] = path
                    rows.append(rdict)
    return pd.DataFrame(rows)


def plot_trade_context(symbol, interval, df_market, analyzer: StrategyAnalyzer, trade_row, out_path):
    # ensure datetime index
    if not pd.api.types.is_datetime64_any_dtype(df_market.index):
        df_market.index = pd.to_datetime(df_market.index)

    entry = pd.to_datetime(trade_row.get('entry_index'))
    exit = pd.to_datetime(trade_row.get('exit_index'))
    if pd.isna(entry) or pd.isna(exit):
        return False
    # window padding: include 10 candles before entry and 10 after exit
    start = entry - (df_market.index.freq or pd.Timedelta('5min')) * 10
    end = exit + (df_market.index.freq or pd.Timedelta('5min')) * 10
    window = df_market[(df_market.index >= start) & (df_market.index <= end)].copy()
    if window.empty:
        # fallback: use entire market df
        window = df_market.copy()

    params = {
        'fast_ema_period': 3,
        'slow_ema_period': 5,
        'enable_volume_momentum': True,
        'volume_avg_period': 20,
        'volume_spike_factor': float(trade_row.get('volume_spike_factor') or 1.4),
    }
    window_ind = analyzer.calculate_indicators(window, params)

    plt.figure(figsize=(10,6))
    ax_price = plt.gca()
    ax_price.plot(window_ind.index, window_ind['close'], label='close', color='black')
    if f"ema_fast_{params['fast_ema_period']}" in window_ind.columns:
        ax_price.plot(window_ind.index, window_ind[f"ema_fast_{params['fast_ema_period']}"] , label='ema_fast', color='tab:orange')
    if f"ema_slow_{params['slow_ema_period']}" in window_ind.columns:
        ax_price.plot(window_ind.index, window_ind[f"ema_slow_{params['slow_ema_period']}"] , label='ema_slow', color='tab:green')
    if 'VWAP' in window_ind.columns:
        ax_price.plot(window_ind.index, window_ind['VWAP'], label='VWAP', color='tab:blue', alpha=0.7)

    # mark entry and exit
    ax_price.axvline(entry, color='red', linestyle='--', linewidth=1)
    ax_price.axvline(exit, color='green', linestyle='--', linewidth=1)
    ax_price.fill_between(window_ind.index, window_ind['close'].min(), window_ind['close'].max(),
                         where=(window_ind.index >= entry) & (window_ind.index <= exit), color='red', alpha=0.04)
    ax_price.set_title(f"Rank {trade_row.get('rank')} loss trade net_pnl={trade_row.get('net_pnl')}")
    ax_price.legend(loc='upper left')

    # volume subplot
    ax_vol = ax_price.twinx()
    if 'volume' in window_ind.columns:
        ax_vol.bar(window_ind.index, window_ind['volume'], alpha=0.2, color='gray', width=0.0005)
    ax_vol.set_ylabel('volume')

    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--interval', default='5m')
    p.add_argument('--top', type=int, default=5)
    args = p.parse_args()

    symbol = args.symbol.upper()
    traces_dir = os.path.join(legacy_dir(), 'traces', symbol.lower())
    if not os.path.exists(traces_dir):
        print('Traces directory not found:', traces_dir)
        return

    df_trades = read_all_trades(traces_dir)
    if df_trades.empty:
        print('No trades found in traces dir')
        return

    # ensure numeric net_pnl
    df_trades['net_pnl'] = pd.to_numeric(df_trades.get('net_pnl', pd.Series()), errors='coerce')
    # group by rank and pick worst top N
    analyzer = StrategyAnalyzer()
    market_csv = os.path.join('data', f"{symbol}_{args.interval}.csv")
    if not os.path.exists(market_csv):
        print('Market data missing:', market_csv)
        return
    df_market = pd.read_csv(market_csv, parse_dates=[0], index_col=0)

    out_plots_dir = os.path.join(traces_dir, 'plots')
    os.makedirs(out_plots_dir, exist_ok=True)

    report_rows = []
    for rank, g in df_trades.groupby('rank'):
        g_sorted = g.sort_values(by='net_pnl', ascending=True).head(args.top)
        rank_dir = os.path.join(out_plots_dir, f'rank_{rank}')
        os.makedirs(rank_dir, exist_ok=True)
        for i, (_, tr) in enumerate(g_sorted.iterrows(), start=1):
            out_path = os.path.join(rank_dir, f'loss_trade_{i}.png')
            ok = plot_trade_context(symbol, args.interval, df_market, analyzer, tr, out_path)
            report_rows.append({'rank': rank, 'file': out_path, 'net_pnl': tr.get('net_pnl'), 'entry': tr.get('entry_index'), 'exit': tr.get('exit_index')})

    consolidated = os.path.join(out_plots_dir, f'{symbol.lower()}_loss_trade_report.json')
    with open(consolidated, 'w', encoding='utf-8') as fh:
        json.dump(report_rows, fh, default=str, indent=2)

    print('Wrote plots and report to', out_plots_dir)


if __name__ == '__main__':
    main()
