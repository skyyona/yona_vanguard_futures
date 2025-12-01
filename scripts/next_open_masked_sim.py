"""Masked next-open simulation: exclude Breakout & Overshoot, shift entries to next-open,
and use ATR-derived adaptive stop loss (global approximation) to better survive intrabar pullbacks.

This script does not change core simulator code; it precomputes signals and computes an
approximate global stop_loss_pct from ATR to pass into StrategySimulator.

Usage example:
  python .\scripts\next_open_masked_sim.py --symbol PIPPINUSDT --date 2025-11-21 --vol-threshold 5.0 --overshoot-threshold 10.0 --atr-mult 1.5
"""
from __future__ import annotations
import argparse, os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import math
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
    p.add_argument('--date', required=True)
    p.add_argument('--interval', default='5m')
    p.add_argument('--vol-threshold', type=float, default=5.0)
    p.add_argument('--overshoot-threshold', type=float, default=10.0)
    p.add_argument('--vol-lookback', type=int, default=20)
    p.add_argument('--confirmation-bars', type=int, default=1)
    p.add_argument('--atr-period', type=int, default=14)
    p.add_argument('--atr-mult', type=float, default=1.5)
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


def compute_atr_pct(df: pd.DataFrame, period: int) -> float:
    # ATR simple: rolling mean of true range
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)
    prev_close = close.shift(1).fillna(close)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=1).mean()
    # return median ATR as fraction of price
    with pd.option_context('mode.use_inf_as_na', True):
        atr_over_price = (atr / close).dropna()
        if len(atr_over_price) == 0:
            return 0.005
        return float(atr_over_price.median())


def mask_breakout_overshoot(df2: pd.DataFrame, params: dict, vol_threshold: float, overshoot_threshold: float, vol_lookback: int) -> pd.DataFrame:
    # reuse logic similar to existing mask_signals
    med_col = f"vol_med_{vol_lookback}"
    mult_col = 'vol_mult'
    if med_col not in df2.columns:
        df2[med_col] = df2['volume'].rolling(window=vol_lookback, min_periods=1).median()
    if mult_col not in df2.columns:
        df2[mult_col] = df2.apply(lambda r: (float(r['volume']) / float(r[med_col])) if pd.notna(r.get(med_col)) and float(r[med_col]) > 0 else 0.0, axis=1)

    fast = int(params.get('fast_ema_period', 3))
    slow = int(params.get('slow_ema_period', 5))

    for i in range(len(df2)):
        try:
            prev_fast = df2.iloc[i-1][f'ema_fast_{fast}'] if i-1 >= 0 else None
            prev_slow = df2.iloc[i-1][f'ema_slow_{slow}'] if i-1 >= 0 else None
            cur_fast = df2.iloc[i][f'ema_fast_{fast}']
            cur_slow = df2.iloc[i][f'ema_slow_{slow}']
        except Exception:
            continue
        ema_gc = False
        try:
            ema_gc = (prev_fast is not None and prev_slow is not None and cur_fast is not None and cur_slow is not None and prev_fast <= prev_slow and cur_fast > cur_slow)
        except Exception:
            ema_gc = False

        vol_spike = bool(df2.iloc[i].get('VolumeSpike', 0)) if 'VolumeSpike' in df2.columns else False
        above_vwap = bool(df2.iloc[i].get('AboveVWAP', 0)) if 'AboveVWAP' in df2.columns else False
        vol_mult = float(df2.iloc[i].get('vol_mult') or 0.0)
        vwap = df2.iloc[i].get('VWAP') if 'VWAP' in df2.columns else None
        close = float(df2.iloc[i].get('close') or 0.0)

        is_breakout = ema_gc and vol_spike and above_vwap
        is_overshoot = (vol_mult >= overshoot_threshold) or (vwap is not None and vwap > 0 and abs(close - vwap) / vwap > 0.12)

        if is_breakout or is_overshoot:
            if 'buy_signal' in df2.columns:
                df2.iat[i, df2.columns.get_loc('buy_signal')] = False
    return df2


def shift_to_next_open_with_confirmation(df2: pd.DataFrame, confirmation: int, vol_threshold: float, vol_lookback: int) -> pd.DataFrame:
    # compute vol_mult if not present
    med_col = f"vol_med_{vol_lookback}"
    mult_col = 'vol_mult'
    if med_col not in df2.columns:
        df2[med_col] = df2['volume'].rolling(window=vol_lookback, min_periods=1).median()
    if mult_col not in df2.columns:
        df2[mult_col] = df2.apply(lambda r: (float(r['volume']) / float(r[med_col])) if pd.notna(r.get(med_col)) and float(r[med_col]) > 0 else 0.0, axis=1)

    df2['buy_signal_next'] = False
    idxs = list(df2.index)
    for i in range(len(idxs)-1):
        if bool(df2.iloc[i].get('buy_signal')):
            # candidate entry at i+1, require confirmation over last `confirmation` bars ending at i+1
            ok = True
            start_i = max(0, i+1 - (confirmation-1))
            for j in range(start_i, i+2):
                v = float(df2.iloc[j].get('vol_mult') or 0.0)
                if v > vol_threshold:
                    ok = False
                    break
            if ok:
                df2.iat[i+1, df2.columns.get_loc('buy_signal_next')] = True

    df2['buy_signal'] = df2['buy_signal_next']
    df2['sell_signal'] = False
    return df2


def run_masked_next_open_day(symbol: str, date_str: str, args):
    df = load_day_df(symbol, args.interval, date_str)
    if df.empty:
        raise SystemExit('No bars for date')

    params = {
        'fast_ema_period': 3,
        'slow_ema_period': 5,
        'enable_volume_momentum': True,
        'enable_sr_detection': True,
        'enable_sr_filter': True,
        'position_size': args.position_size,
        'volume_avg_period': args.vol_lookback,
    }

    analyzer = StrategyAnalyzer()
    df2 = analyzer.calculate_indicators(df.copy(), params)
    df2 = analyzer.generate_signals(df2, params)

    # mask breakout & overshoot
    df2_masked = mask_breakout_overshoot(df2.copy(), params, args.vol_threshold, args.overshoot_threshold, args.vol_lookback)

    # shift signals to next open with confirmation
    df2_shifted = shift_to_next_open_with_confirmation(df2_masked.copy(), args.confirmation_bars, args.vol_threshold, args.vol_lookback)

    # compute ATR% and set global stop_loss_pct = median_atr_pct * atr_mult
    atr_pct = compute_atr_pct(df, args.atr_period)
    stop_loss_pct = max(0.001, atr_pct * args.atr_mult)

    sim = StrategySimulator()
    params_run = dict(params)
    params_run['use_precomputed_signals'] = True
    params_run['stop_loss_pct'] = stop_loss_pct
    params_run['position_size'] = args.position_size
    params_run['fee_pct'] = 0.0005
    params_run['trailing_stop_pct'] = 0.0

    res = sim.run_simulation(symbol.upper(), args.interval, df2_shifted.copy(), initial_balance=args.initial_balance, leverage=args.leverage, strategy_parameters=params_run)
    return res, df2_shifted, stop_loss_pct, atr_pct


def main():
    args = parse_args()
    res, df_with_signals, stop_loss_pct, atr_pct = run_masked_next_open_day(args.symbol, args.date, args)

    out_dir = os.path.join('results', f"{args.symbol.lower()}_masked_next_open")
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"{args.date}_summary.csv")
    # Sanitize summary: do not include user capital or leverage fields
    df_summary = pd.DataFrame([{
        'date': args.date,
        'final_balance': res.get('final_balance'),
        'profit': res.get('profit'),
        'profit_pct': res.get('profit_percentage'),
        'total_trades': res.get('total_trades'),
        'win_rate': res.get('win_rate'),
        'max_drawdown_pct': res.get('max_drawdown_pct'),
        'computed_atr_pct': atr_pct,
        'stop_loss_pct_used': stop_loss_pct,
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

    df_with_signals.to_csv(os.path.join(out_dir, f"{args.date}_df_with_signals.csv"))

    # sanitize CSV if sanitizer available
    if sanitize_csv_file is not None:
        try:
            s = sanitize_csv_file(Path(out_csv), inplace=False, dry_run=False)
            if s:
                print('Sanitized output ->', s)
        except Exception as e:
            print('Sanitization failed:', e)

    print('Wrote summary to', out_csv)
    print('Final profit pct:', res.get('profit_percentage'))


if __name__ == '__main__':
    main()
