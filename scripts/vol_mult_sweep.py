import os
import sys
import csv
import json
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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


def prepare_df2(df, params, lookback=10):
    analyzer = StrategyAnalyzer()
    df2 = analyzer.calculate_indicators(df, params)
    df2 = analyzer.generate_signals(df2, params)
    med_col = f"vol_med_{lookback}"
    mult_col = 'vol_mult'
    if med_col not in df2.columns:
        df2[med_col] = df2['volume'].rolling(window=lookback, min_periods=1).median()
    if mult_col not in df2.columns:
        df2[mult_col] = df2.apply(lambda r: (float(r['volume']) / float(r[med_col])) if pd.notna(r.get(med_col)) and float(r[med_col]) > 0 else 0.0, axis=1)
    return df2


def mask_by_vol_mult(df2: pd.DataFrame, threshold: float):
    dfm = df2.copy()
    if 'buy_signal' not in dfm.columns:
        dfm['buy_signal'] = False
    for i in range(len(dfm)):
        try:
            vm = float(dfm.iloc[i].get('vol_mult') or 0.0)
            if vm > threshold:
                dfm.iat[i, dfm.columns.get_loc('buy_signal')] = False
        except Exception:
            continue
    return dfm


def summarize_res(res: dict):
    return {
        'final_balance': res.get('final_balance'),
        'profit': res.get('profit'),
        'profit_percentage': res.get('profit_percentage'),
        'total_trades': res.get('total_trades'),
        'win_rate': res.get('win_rate'),
        'max_drawdown_pct': res.get('max_drawdown_pct'),
    }


def main():
    symbol = 'PIPPINUSDT'
    top = load_top_candidate(symbol)
    params = parse_params_from_wf_row(top)

    df_path = os.path.join('data', f"{symbol}_5m.csv")
    if not os.path.exists(df_path):
        raise SystemExit('Data missing: ' + df_path)
    df = pd.read_csv(df_path, parse_dates=[0], index_col=0)

    df2 = prepare_df2(df, params, lookback=10)
    sim = StrategySimulator()

    thresholds = [1.5, 2.0, 3.0, 4.0, 5.0, 8.0, 10.0]
    results = []

    for th in thresholds:
        dfm = mask_by_vol_mult(df2, th)
        p = dict(params)
        p['use_precomputed_signals'] = True
        res = sim.run_simulation(symbol, '5m', dfm.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=p)
        summary = summarize_res(res)
        summary['vol_mult_threshold'] = th
        results.append(summary)
        print('Threshold', th, '-> trades', summary['total_trades'], 'profit_pct', summary['profit_percentage'])

    # write CSV/JSON
    out_dir = 'results'
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"{symbol.lower()}_vol_mult_sweep.csv")
    json_path = os.path.join(out_dir, f"{symbol.lower()}_vol_mult_sweep.json")

    # CSV fields order (do not include initial balance or leverage)
    fieldnames = ['vol_mult_threshold','final_balance','profit','profit_percentage','total_trades','win_rate','max_drawdown_pct']
    with open(csv_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, '') for k in fieldnames})

    with open(json_path, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, indent=2)

    print('Wrote', csv_path)
    print('Wrote', json_path)

    # sanitize csv output
    if sanitize_csv_file is not None:
        try:
            s = sanitize_csv_file(Path(csv_path), inplace=False, dry_run=False)
            if s:
                print('Sanitized output ->', s)
        except Exception as e:
            print('Sanitization failed:', e)

if __name__ == '__main__':
    main()
