import os
import sys
import csv
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from backtesting_backend.core.strategy_simulator import StrategySimulator


def parse_params_from_wf_row(row: dict) -> dict:
    return {
        'fast_ema_period': int(row.get('fast_ema_period') or 3),
        'slow_ema_period': int(row.get('slow_ema_period') or 5),
        'enable_volume_momentum': True,
        'enable_sr_detection': True,
        'enable_sr_filter': True,
        'stop_loss_pct': float(row.get('stop_loss_pct') or 0.005),
        'take_profit_pct': float(row.get('take_profit_pct') or 0.0),
        'position_size': float(row.get('position_size') or 0.005),
        'volume_spike_factor': float(row.get('volume_spike_factor') or 1.4),
        'volume_avg_period': int(row.get('volume_avg_period') or 20),
    }


def load_top_candidate(symbol: str):
    wf_path = os.path.join('results', f"{symbol.lower()}_wf_verify.csv")
    if not os.path.exists(wf_path):
        raise SystemExit('WF file missing: ' + wf_path)
    wf = pd.read_csv(wf_path)
    if wf.empty:
        raise SystemExit('WF file empty: ' + wf_path)
    return wf.iloc[0].to_dict()


def snapshot_flag(df2, idx, params):
    # idx is timestamp index value
    try:
        pos = df2.index.get_loc(idx)
    except Exception:
        return None
    prev_pos = pos - 1 if pos - 1 >= 0 else None
    fast = params.get('fast_ema_period', 3)
    slow = params.get('slow_ema_period', 5)
    prev_fast = df2.iloc[prev_pos][f'ema_fast_{fast}'] if prev_pos is not None else None
    prev_slow = df2.iloc[prev_pos][f'ema_slow_{slow}'] if prev_pos is not None else None
    cur_fast = df2.iloc[pos][f'ema_fast_{fast}']
    cur_slow = df2.iloc[pos][f'ema_slow_{slow}']
    ema_gc = False
    try:
        ema_gc = (prev_fast is not None and prev_slow is not None and cur_fast is not None and cur_slow is not None and prev_fast <= prev_slow and cur_fast > cur_slow)
    except Exception:
        ema_gc = False
    vol_spike = bool(df2.iloc[pos].get('VolumeSpike', 0)) if 'VolumeSpike' in df2.columns else False
    above_vwap = bool(df2.iloc[pos].get('AboveVWAP', 0)) if 'AboveVWAP' in df2.columns else False
    trend_ok = bool(df2.iloc[pos].get('trend_ok', True))
    session_ok = bool(df2.iloc[pos].get('session_ok', True))
    vol_mult = float(df2.iloc[pos].get('vol_mult') or 0.0)
    return {
        'ema_gc': ema_gc,
        'vol_spike': vol_spike,
        'above_vwap': above_vwap,
        'trend_ok': trend_ok,
        'session_ok': session_ok,
        'vol_mult': vol_mult,
        'close': float(df2.iloc[pos]['close']) if 'close' in df2.columns else None,
        'volume': float(df2.iloc[pos]['volume']) if 'volume' in df2.columns else None,
    }


def main():
    symbol = 'PIPPINUSDT'
    top = load_top_candidate(symbol)
    params = parse_params_from_wf_row(top)

    df_path = os.path.join('data', f"{symbol}_5m.csv")
    if not os.path.exists(df_path):
        raise SystemExit('Data missing: ' + df_path)
    df = pd.read_csv(df_path, parse_dates=[0], index_col=0)

    analyzer = StrategyAnalyzer()
    sim = StrategySimulator(analyzer=analyzer)

    df2 = analyzer.calculate_indicators(df, params)
    df2 = analyzer.generate_signals(df2, params)

    # prepare vol_mult same as simulator used
    lookback = 10
    med_col = f"vol_med_{lookback}"
    mult_col = 'vol_mult'
    if med_col not in df2.columns:
        df2[med_col] = df2['volume'].rolling(window=lookback, min_periods=1).median()
    if mult_col not in df2.columns:
        df2[mult_col] = df2.apply(lambda r: (float(r['volume']) / float(r[med_col])) if pd.notna(r.get(med_col)) and float(r[med_col]) > 0 else 0.0, axis=1)

    res = sim.run_simulation(symbol, '5m', df.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=params)
    trades = res.get('trades', [])

    # classify breakout: ema_gc True, vol_spike True, above_vwap True (and trend/session ok)
    breakout_trades = []
    for t in trades:
        entry_idx = t.get('entry_index')
        if entry_idx is None:
            continue
        flags = snapshot_flag(df2, entry_idx, params)
        if flags is None:
            continue
        is_breakout = flags['ema_gc'] and flags['vol_spike'] and flags['above_vwap'] and flags['trend_ok'] and flags['session_ok']
        t2 = dict(t)
        t2.update(flags)
        t2['is_breakout'] = is_breakout
        breakout_trades.append(t2)

    total = len(trades)
    bo_total = sum(1 for t in breakout_trades if t['is_breakout'])
    bo_prof = [t for t in breakout_trades if t['is_breakout'] and t.get('net_pnl', 0) > 0]
    bo_loss = [t for t in breakout_trades if t['is_breakout'] and t.get('net_pnl', 0) <= 0]

    # stats
    def mean(xs):
        return sum(xs)/len(xs) if xs else 0.0
    bo_prof_mean = mean([t.get('net_pnl',0) for t in bo_prof])
    bo_loss_mean = mean([t.get('net_pnl',0) for t in bo_loss])
    bo_prof_winrate = len(bo_prof)/(bo_total) * 100 if bo_total else 0.0

    print('Total trades:', total)
    print('Breakout trades:', bo_total)
    print('Breakout profitable:', len(bo_prof), 'Breakout losses:', len(bo_loss))
    print('Breakout win rate (%):', round(bo_prof_winrate,2))
    print('Breakout profit mean (net_pnl):', bo_prof_mean)
    print('Breakout loss mean (net_pnl):', bo_loss_mean)

    # vol_mult distributions
    bo_prof_vols = [t.get('vol_mult',0) for t in bo_prof]
    bo_loss_vols = [t.get('vol_mult',0) for t in bo_loss]
    print('Breakout profitable vol_mult mean:', mean(bo_prof_vols), 'count', len(bo_prof_vols))
    print('Breakout losing vol_mult mean:', mean(bo_loss_vols), 'count', len(bo_loss_vols))

    # write CSV of breakout trades sample
    out_dir = 'results'
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"{symbol.lower()}_breakout_analysis.csv")
    with open(out_csv, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(breakout_trades[0].keys()) if breakout_trades else ['is_breakout'])
        writer.writeheader()
        for r in breakout_trades:
            writer.writerow({k: ('' if r.get(k) is None else r.get(k)) for k in writer.fieldnames})

    print('Wrote', out_csv)

if __name__ == '__main__':
    main()
