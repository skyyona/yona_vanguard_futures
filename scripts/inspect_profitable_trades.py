import os
import sys
import pandas as pd

# ensure imports work
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


def snapshot_row(df2: pd.DataFrame, ts):
    # ts may be string or Timestamp
    try:
        t = pd.to_datetime(ts)
    except Exception:
        return None
    if t in df2.index:
        return df2.loc[t]
    # try nearest
    try:
        pos = df2.index.get_loc(t)
        return df2.iloc[pos]
    except Exception:
        return None


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
    lookback = int(params.get('vol_spike_lookback', 10))
    med_col = f"vol_med_{lookback}"
    mult_col = 'vol_mult'
    if med_col not in df2.columns:
        df2[med_col] = df2['volume'].rolling(window=lookback, min_periods=1).median()
    if mult_col not in df2.columns:
        df2[mult_col] = df2.apply(lambda r: (float(r['volume']) / float(r[med_col])) if pd.notna(r.get(med_col)) and float(r[med_col]) > 0 else 0.0, axis=1)

    # run single deterministic sim (no noise/slippage)
    res = sim.run_simulation(symbol, '5m', df.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=params)

    trades = res.get('trades', [])
    if not trades:
        print('No trades executed for top candidate')
        return

    # find profitable trades
    prof_trades = [t for t in trades if t.get('net_pnl', 0) > 0]
    print(f"Total trades: {len(trades)}, profitable trades: {len(prof_trades)}")

    # sort by net_pnl desc and print top 5
    prof_trades_sorted = sorted(prof_trades, key=lambda x: x.get('net_pnl', 0), reverse=True)
    top_n = prof_trades_sorted[:10]

    bad_event_time = pd.to_datetime('2025-11-21T12:30:00')
    bad_row = snapshot_row(df2, bad_event_time)
    print('\nBad event snapshot (2025-11-21T12:30:00):')
    if bad_row is not None:
        print(bad_row[['open','high','low','close','volume']].to_dict())
        print('vol_mult:', bad_row.get('vol_mult'), 'AvgVolume:', bad_row.get('AvgVolume'), 'VWAP:', bad_row.get('VWAP'))
    else:
        print('Bad event not in index')

    print('\nTop profitable trades (up to 10) and their entry snapshots:')
    for t in top_n:
        entry_idx = t.get('entry_index')
        exit_idx = t.get('exit_index')
        net_pnl = t.get('net_pnl')
        entry_price = t.get('entry_price')
        exit_price = t.get('exit_price')
        print('---')
        print('Entry index:', entry_idx, 'Entry price:', entry_price, 'Exit index:', exit_idx, 'Exit price:', exit_price, 'Net PnL:', net_pnl)
        row = snapshot_row(df2, entry_idx)
        if row is None:
            print('  Entry row not found in index')
            continue
        # print key indicators
        keys = ['open','high','low','close','volume', f"ema_fast_{params.get('fast_ema_period',3)}", f"ema_slow_{params.get('slow_ema_period',5)}", 'VolumeSpike','AboveVWAP', med_col, 'vol_mult','VWAP','AvgVolume']
        out = {}
        for k in keys:
            if k in row.index:
                out[k] = row[k]
        print('  indicators at entry:', out)
        # compare to bad event vol_mult
        try:
            entry_vol_mult = float(row.get('vol_mult') or 0.0)
            bad_vol_mult = float(bad_row.get('vol_mult') or 0.0) if bad_row is not None else None
            print('  vol_mult difference: entry', entry_vol_mult, ' vs bad_event', bad_vol_mult)
        except Exception:
            pass

    # summary stats
    mean_profit = sum(t.get('net_pnl',0) for t in prof_trades)/len(prof_trades) if prof_trades else 0
    print('\nSummary: profitable trades mean net_pnl:', mean_profit)


if __name__ == '__main__':
    main()
