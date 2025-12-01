import argparse
import os
import sys
import pandas as pd

# ensure project root is on sys.path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer

def parse_params_from_wf_row(row: dict) -> dict:
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

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--time', required=True, help='ISO time to inspect, e.g. 2025-11-21T12:30:00')
    # optional WF file argument if needed in future
    # p.add_argument('--wf', default=os.path.join('results', f"{symbol.lower()}_wf_verify.csv"))
    args = p.parse_args()

    symbol = args.symbol.upper()
    inspect_time = pd.to_datetime(args.time)

    wf_path = os.path.join('results', f"{symbol.lower()}_wf_verify.csv")
    if not os.path.exists(wf_path):
        raise SystemExit('WF verify file not found: ' + wf_path)

    wf = pd.read_csv(wf_path)
    if wf.empty:
        raise SystemExit('WF file empty')

    # pick top candidate (rank 1)
    top = wf.iloc[0].to_dict()
    params = parse_params_from_wf_row(top)

    # load data
    df_path = os.path.join('data', f"{symbol}_5m.csv")
    if not os.path.exists(df_path):
        raise SystemExit('Data file not found: ' + df_path)
    df = pd.read_csv(df_path, parse_dates=[0], index_col=0)

    analyzer = StrategyAnalyzer()
    df2 = analyzer.calculate_indicators(df, params)
    df2 = analyzer.generate_signals(df2, params)

    # compute rolling median vol and vol_mult consistent with simulator defaults
    lookback = 10
    med_col = f"vol_med_{lookback}"
    mult_col = 'vol_mult'
    if med_col not in df2.columns:
        df2[med_col] = df2['volume'].rolling(window=lookback, min_periods=1).median()
    if mult_col not in df2.columns:
        df2[mult_col] = df2.apply(lambda r: (float(r['volume']) / float(r[med_col])) if pd.notna(r.get(med_col)) and float(r[med_col]) > 0 else 0.0, axis=1)

    if inspect_time not in df2.index:
        # try to find nearest
        if inspect_time in df2.index:
            row = df2.loc[inspect_time]
        else:
            raise SystemExit('Requested time not found in data index: ' + str(inspect_time))

    i = df2.index.get_loc(inspect_time)
    prev_i = i-1 if i-1 >= 0 else None

    def val_at(idx, col):
        try:
            return df2.iloc[idx][col]
        except Exception:
            return None

    prev_fast = val_at(prev_i, f"ema_fast_{params.get('fast_ema_period', 3)}") if prev_i is not None else None
    prev_slow = val_at(prev_i, f"ema_slow_{params.get('slow_ema_period', 5)}") if prev_i is not None else None
    cur_fast = val_at(i, f"ema_fast_{params.get('fast_ema_period', 3)}")
    cur_slow = val_at(i, f"ema_slow_{params.get('slow_ema_period', 5)}")

    ema_gc = (prev_fast is not None and prev_slow is not None and cur_fast is not None and cur_slow is not None and prev_fast <= prev_slow and cur_fast > cur_slow)

    # volume momentum
    vol_spike = bool(val_at(i, 'VolumeSpike')) if 'VolumeSpike' in df2.columns else False
    above_vwap = bool(val_at(i, 'AboveVWAP')) if 'AboveVWAP' in df2.columns else False

    vol_mult = float(val_at(i, 'vol_mult') or 0.0)
    avg_vol = float(val_at(i, f"vol_med_{lookback}") or 0.0)
    vol = float(val_at(i, 'volume') or 0.0)

    # trend_ok/session_ok
    trend_ok = bool(val_at(i, 'trend_ok')) if 'trend_ok' in df2.columns else True
    session_ok = bool(val_at(i, 'session_ok')) if 'session_ok' in df2.columns else True

    buy_signal = bool(val_at(i, 'buy_signal'))

    print('Inspection time:', inspect_time)
    print('EMA prev:', prev_fast, prev_slow)
    print('EMA cur :', cur_fast, cur_slow)
    print('EMA golden cross (ema_gc):', ema_gc)
    print('trend_ok:', trend_ok, 'session_ok:', session_ok)
    print('Volume:', vol, 'AvgVolume:', avg_vol, 'vol_mult:', vol_mult)
    print('VolumeSpike:', vol_spike, 'AboveVWAP:', above_vwap)
    print('buy_signal (generated):', buy_signal)
    print('\nFull row:\n')
    pd.set_option('display.max_columns', 200)
    print(df2.loc[inspect_time])
