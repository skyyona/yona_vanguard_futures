"""Simulate next-open entries while excluding Breakout and Overshoot signals,
and apply an ATR-based adaptive stop-loss to improve survival through intra-candle pullbacks.

This script combines logic from `sim_no_breakout_overshoot.py` and `next_open_sim.py`.
"""
from __future__ import annotations
import os, sys
import argparse
import json
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
    p.add_argument('--date', required=False, help='Optional single date YYYY-MM-DD to restrict')
    p.add_argument('--vol-threshold', type=float, default=5.0)
    p.add_argument('--overshoot-threshold', type=float, default=10.0)
    p.add_argument('--confirmation-bars', type=int, default=1)
    p.add_argument('--atr-lookback', type=int, default=14)
    p.add_argument('--atr-mult', type=float, default=1.5)
    p.add_argument('--position-size', type=float, default=0.005)
    p.add_argument('--initial-balance', type=float, default=1000.0)
    p.add_argument('--leverage', type=int, default=1)
    return p.parse_args()


def load_df(symbol: str, interval: str, date_filter: str | None = None) -> pd.DataFrame:
    path = os.path.join('data', f"{symbol.upper()}_{interval}.csv")
    if not os.path.exists(path):
        raise SystemExit(f"Data file not found: {path}")
    df = pd.read_csv(path, parse_dates=[0], index_col=0)
    if date_filter:
        start = pd.to_datetime(date_filter)
        end = start + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        df = df[(df.index >= start) & (df.index <= end)].copy()
    return df


def mask_breakout_overshoot(df2: pd.DataFrame, params: dict, vol_threshold: float, overshoot_threshold: float) -> pd.DataFrame:
    # reuse logic: compute vol_med and vol_mult
    lookback = int(params.get('vol_spike_lookback', 10))
    med_col = f"vol_med_{lookback}"
    mult_col = 'vol_mult'
    if med_col not in df2.columns:
        df2[med_col] = df2['volume'].rolling(window=lookback, min_periods=1).median()
    if mult_col not in df2.columns:
        df2[mult_col] = df2.apply(lambda r: (float(r['volume']) / float(r[med_col])) if pd.notna(r.get(med_col)) and float(r[med_col]) > 0 else 0.0, axis=1)

    fast = params.get('fast_ema_period', 3)
    slow = params.get('slow_ema_period', 5)
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
        is_overshoot = (vol_mult >= overshoot_threshold) or (vwap is not None and vwap>0 and abs(close - vwap)/vwap > 0.12)

        if (is_breakout or is_overshoot) and 'buy_signal' in df2.columns:
            df2.iat[i, df2.columns.get_loc('buy_signal')] = False
    return df2


def shift_to_next_open_with_confirmation(df2: pd.DataFrame, confirmation: int, vol_threshold: float, vol_lookback: int) -> pd.DataFrame:
    # compute vol_mult if missing
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
            # require confirmation window ending at i+1
            ok = True
            start_i = max(0, i+1 - (confirmation-1))
            for j in range(start_i, i+2):
                v = float(df2.iloc[j].get('vol_mult') or 0.0)
                if v > vol_threshold:
                    ok = False
                    break
            if ok:
                df2.at[idxs[i+1], 'buy_signal_next'] = True
    df2['buy_signal'] = df2['buy_signal_next']
    df2['sell_signal'] = False
    return df2


def compute_atr_pct(df: pd.DataFrame, lookback: int) -> float:
    # True range: max(high-low, abs(high-prev_close), abs(low-prev_close))
    h = df['high']
    l = df['low']
    c = df['close']
    prev_c = c.shift(1)
    tr1 = h - l
    tr2 = (h - prev_c).abs()
    tr3 = (l - prev_c).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=lookback, min_periods=1).mean()
    # use mean ATR percent over the dataset
    atr_pct = (atr / c).replace([pd.NA, pd.NaT], 0.0).mean()
    return float(atr_pct or 0.0)


def main():
    args = parse_args()
    symbol = args.symbol.upper()
    df = load_df(symbol, args.interval, args.date)
    if df.empty:
        raise SystemExit('No data for symbol/date')

    analyzer = StrategyAnalyzer()
    sim = StrategySimulator()

    params = {
        'fast_ema_period': 3,
        'slow_ema_period': 5,
        'enable_volume_momentum': True,
        'enable_sr_detection': True,
        'enable_sr_filter': True,
        'stop_loss_pct': 0.005,
        'take_profit_pct': 0.0,
        'position_size': args.position_size,
        'volume_avg_period': 20,
        'vol_spike_lookback': 20,
    }

    df2 = analyzer.calculate_indicators(df.copy(), params)
    df2 = analyzer.generate_signals(df2, params)

    # mask breakout/overshoot
    df_masked = mask_breakout_overshoot(df2.copy(), params, args.vol_threshold, args.overshoot_threshold)

    # shift to next-open with confirmation
    df_shifted = shift_to_next_open_with_confirmation(df_masked.copy(), args.confirmation_bars, args.vol_threshold, params.get('vol_spike_lookback', 20))

    # compute ATR percent for adaptive SL
    atr_pct = compute_atr_pct(df_shifted, args.atr_lookback)
    adaptive_sl = max(float(params.get('stop_loss_pct', 0.005)), atr_pct * args.atr_mult)
    params['stop_loss_pct'] = adaptive_sl
    params['use_precomputed_signals'] = True

    res = sim.run_simulation(symbol, args.interval, df_shifted.copy(), initial_balance=args.initial_balance, leverage=args.leverage, strategy_parameters=params)

    # Do not include capital/leverage in exported summaries
    out = {
        'symbol': symbol,
        'date': args.date,
        'vol_threshold': args.vol_threshold,
        'overshoot_threshold': args.overshoot_threshold,
        'confirmation_bars': args.confirmation_bars,
        'atr_lookback': args.atr_lookback,
        'atr_mult': args.atr_mult,
        'atr_pct': atr_pct,
        'adaptive_stop_loss_pct': adaptive_sl,
        'result_summary': {
            'final_balance': res.get('final_balance'),
            'profit': res.get('profit'),
            'profit_pct': res.get('profit_percentage'),
            'total_trades': res.get('total_trades'),
            'win_rate': res.get('win_rate'),
            'max_drawdown_pct': res.get('max_drawdown_pct')
        }
    }

    out_dir = os.path.join('results', f"{symbol.lower()}_next_open_no_breakout")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{args.date or 'all'}_summary.json")
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2)

    print('Wrote', out_path)
    print('Summary:', out['result_summary'])


if __name__ == '__main__':
    main()
