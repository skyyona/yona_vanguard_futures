"""Simulate 'next-open' entry behavior by shifting generated buy signals forward one bar
and applying volume-energy confirmation checks before entry.

This script does not modify core code; it precomputes signals and calls StrategySimulator
with `use_precomputed_signals=True` to simulate entering at the next bar open.

Usage (example):
  python .\scripts\next_open_sim.py --symbol PIPPINUSDT --date 2025-11-21 --interval 5m --vol-threshold 5.0
"""
from __future__ import annotations
import argparse, os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from backtesting_backend.core.strategy_simulator import StrategySimulator
from pathlib import Path

# sanitizer (importable)
try:
    from scripts.sanitize_results import sanitize_csv_file
except Exception:
    try:
        from sanitize_results import sanitize_csv_file
    except Exception:
        sanitize_csv_file = None


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--date', required=True, help='Day to simulate in YYYY-MM-DD')
    p.add_argument('--interval', default='5m')
    p.add_argument('--vol-threshold', type=float, default=5.0)
    p.add_argument('--vol-lookback', type=int, default=20)
    p.add_argument('--confirmation-bars', type=int, default=1)
    p.add_argument('--stop-loss-pct', type=float, default=0.005)
    p.add_argument('--position-size', type=float, default=0.005)
    p.add_argument('--initial-balance', type=float, default=1000.0)
    p.add_argument('--leverage', type=int, default=1)
    return p.parse_args()


def load_day_df(symbol: str, interval: str, date_str: str) -> pd.DataFrame:
    path = os.path.join('data', f"{symbol.upper()}_{interval}.csv")
    if not os.path.exists(path):
        raise SystemExit(f"Data file not found: {path}")
    df = pd.read_csv(path, parse_dates=[0], index_col=0)
    start = pd.to_datetime(date_str)
    end = start + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return df[(df.index >= start) & (df.index <= end)].copy()


def prepare_precomputed_signals(df: pd.DataFrame, params: dict, vol_threshold: float, vol_lookback: int, confirmation: int) -> pd.DataFrame:
    analyzer = StrategyAnalyzer()
    df2 = analyzer.calculate_indicators(df.copy(), params)
    df2 = analyzer.generate_signals(df2, params)

    # compute rolling median and vol_mult if not present
    med_col = f"vol_med_{vol_lookback}"
    mult_col = "vol_mult"
    if med_col not in df2.columns:
        df2[med_col] = df2['volume'].rolling(window=vol_lookback, min_periods=1).median()
    if mult_col not in df2.columns:
        df2[mult_col] = df2.apply(lambda r: (float(r['volume']) / float(r[med_col])) if r.get(med_col) and float(r[med_col]) > 0 else 0.0, axis=1)

    # Build next-open entry signals: if buy_signal at t, candidate entry at t+1
    df2['buy_signal_next'] = False
    idxs = list(df2.index)
    for i in range(len(idxs)-1):
        t = idxs[i]
        t_next = idxs[i+1]
        row = df2.loc[t]
        # original buy at time t
        if bool(row.get('buy_signal')):
            # check confirmation on t_next: vol_mult <= threshold for confirmation bars ending at t_next
            ok = True
            # ensure we have enough bars for confirmation window
            start_i = max(0, i+1 - (confirmation-1))
            for j in range(start_i, i+2):
                v = float(df2.iloc[j].get('vol_mult') or 0.0)
                if v > vol_threshold:
                    ok = False
                    break
            if ok:
                df2.at[t_next, 'buy_signal_next'] = True

    # set buy_signal to the shifted/confirmed version and mark as precomputed
    df2['buy_signal'] = df2['buy_signal_next']
    df2['sell_signal'] = False  # keep original sell logic disabled for safety (could be extended)
    return df2


def run_day_simulation(symbol: str, date_str: str, interval: str, vol_threshold: float, vol_lookback: int, confirmation: int, sl_pct: float, pos_size: float, initial_balance: float, leverage: int):
    df = load_day_df(symbol, interval, date_str)
    if df.empty:
        raise SystemExit('No bars for specified date')

    params = {
        'fast_ema_period': 3,
        'slow_ema_period': 5,
        'enable_volume_momentum': True,
        'enable_sr_detection': True,
        'enable_sr_filter': True,
        'stop_loss_pct': sl_pct,
        'take_profit_pct': 0.0,
        'position_size': pos_size,
        'volume_avg_period': vol_lookback,
    }

    df_pre = prepare_precomputed_signals(df, params, vol_threshold, vol_lookback, confirmation)

    sim = StrategySimulator()
    # mark that df contains precomputed signals
    params['use_precomputed_signals'] = True
    params['enable_volume_spike_filter'] = True
    params['vol_spike_threshold'] = vol_threshold
    params['vol_spike_lookback'] = vol_lookback

    res = sim.run_simulation(symbol.upper(), interval, df_pre, initial_balance=initial_balance, leverage=leverage, strategy_parameters=params)
    return res, df_pre


def main():
    args = parse_args()
    res, df_pre = run_day_simulation(args.symbol, args.date, args.interval, args.vol_threshold, args.vol_lookback, args.confirmation_bars, args.stop_loss_pct, args.position_size, args.initial_balance, args.leverage)
    out_dir = os.path.join('results', f"{args.symbol.lower()}_next_open_sim")
    os.makedirs(out_dir, exist_ok=True)
    # write summary
    out_csv = os.path.join(out_dir, f"{args.date}_summary.csv")
    # Sanitize summary: do not include user capital or leverage fields
    df_summary = pd.DataFrame([{
        'date': args.date,
        'final_balance': res.get('final_balance'),
        'profit': res.get('profit'),
        'profit_pct': res.get('profit_percentage'),
        'total_trades': res.get('total_trades'),
        'win_rate': res.get('win_rate'),
        'max_drawdown_pct': res.get('max_drawdown_pct')
    }])
    df_summary.to_csv(out_csv, index=False)
    # save trades
    trades_csv = os.path.join(out_dir, f"{args.date}_trades.csv")
    try:
        import csv
        with open(trades_csv, 'w', newline='', encoding='utf-8') as fh:
            if res.get('trades'):
                keys = sorted({k for t in res.get('trades') for k in t.keys()})
                writer = csv.DictWriter(fh, fieldnames=keys)
                writer.writeheader()
                for t in res.get('trades'):
                    writer.writerow(t)
    except Exception:
        pass

    # save precomputed df sample (with signals)
    df_pre.to_csv(os.path.join(out_dir, f"{args.date}_df_with_signals.csv"))

    # attempt to sanitize generated CSV
    if sanitize_csv_file is not None:
        try:
            s = sanitize_csv_file(Path(out_csv), inplace=False, dry_run=False)
            if s:
                print('Sanitized output ->', s)
        except Exception as e:
            print('Sanitization failed:', e)

    print('Simulation complete. Summary written to', out_csv)
    print('Final profit pct:', res.get('profit_percentage'))


if __name__ == '__main__':
    main()
