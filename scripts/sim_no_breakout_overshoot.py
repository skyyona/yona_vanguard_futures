import os
import sys
import json
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


def mask_signals(df2: pd.DataFrame, params: dict, vol_threshold: float = 5.0, overshoot_threshold: float = 10.0):
    """Zero-out buy signals where breakout OR overshoot conditions hold.
    breakout: ema_gc & VolumeSpike & AboveVWAP
    overshoot: vol_mult >= overshoot_threshold OR price deviation from VWAP large
    """
    fast = params.get('fast_ema_period', 3)
    slow = params.get('slow_ema_period', 5)
    lookback = int(params.get('vol_spike_lookback', 10))
    med_col = f"vol_med_{lookback}"
    mult_col = 'vol_mult'
    if med_col not in df2.columns:
        df2[med_col] = df2['volume'].rolling(window=lookback, min_periods=1).median()
    if mult_col not in df2.columns:
        df2[mult_col] = df2.apply(lambda r: (float(r['volume']) / float(r[med_col])) if pd.notna(r.get(med_col)) and float(r[med_col]) > 0 else 0.0, axis=1)

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

        # if either condition, mask buy_signal
        if is_breakout or is_overshoot:
            if 'buy_signal' in df2.columns:
                df2.iat[i, df2.columns.get_loc('buy_signal')] = False
    return df2


def summarize_results(res: dict):
    out = {
        # Do not reveal initial capital or leverage in exported summaries
        'final_balance': res.get('final_balance'),
        'profit': res.get('profit'),
        'profit_percentage': res.get('profit_percentage'),
        'total_trades': res.get('total_trades'),
        'win_rate': res.get('win_rate'),
        'max_drawdown_pct': res.get('max_drawdown_pct'),
    }
    return out


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

    # compute indicators and signals
    df2 = analyzer.calculate_indicators(df, params)
    df2 = analyzer.generate_signals(df2, params)

    # baseline: run simulation with precomputed signals (no masking)
    p_base = dict(params)
    p_base['use_precomputed_signals'] = True
    res_base = sim.run_simulation(symbol, '5m', df2.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=p_base)
    summary_base = summarize_results(res_base)

    # masked run: remove breakout & overshoot entries
    vol_threshold = 5.0
    overshoot_threshold = 10.0
    df_masked = mask_signals(df2.copy(), params, vol_threshold=vol_threshold, overshoot_threshold=overshoot_threshold)
    p_mask = dict(params)
    p_mask['use_precomputed_signals'] = True
    res_mask = sim.run_simulation(symbol, '5m', df_masked.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=p_mask)
    summary_mask = summarize_results(res_mask)

    # output comparison
    out = {
        'symbol': symbol,
        'vol_threshold': vol_threshold,
        'overshoot_threshold': overshoot_threshold,
        'baseline': summary_base,
        'masked': summary_mask,
    }

    out_dir = 'results'
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{symbol.lower()}_no_breakout_overshoot_summary.json")
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2)

    print('Wrote', out_path)
    print('Baseline summary:', summary_base)
    print('Masked summary  :', summary_mask)

if __name__ == '__main__':
    main()
