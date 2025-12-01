"""Quick parameter sweep over top WF/MC candidates to find profitable parameter combos.

Usage:
  python scripts/param_sweep_quick.py --symbol PIPPINUSDT
"""
from __future__ import annotations
import os, csv, argparse, json
import pandas as pd
import itertools

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
import sys
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.core.strategy_simulator import StrategySimulator


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


def load_candidates(wf_csv, max_candidates=3):
    rows = []
    with open(wf_csv, newline='', encoding='utf-8') as fh:
        dr = csv.DictReader(fh)
        for r in dr:
            rows.append(r)
    try:
        rows = sorted(rows, key=lambda r: float(r.get('wf_mean_profit_pct') or 0), reverse=True)
    except Exception:
        pass
    return rows[:max_candidates]


def run_sim(symbol, interval, df_market, params, slippage, fee):
    sim = StrategySimulator()
    p = dict(params)
    p['slippage_pct'] = slippage
    p['fee_pct'] = fee
    res = sim.run_simulation(symbol, interval, df_market.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=p)
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--interval', default='5m')
    p.add_argument('--max-candidates', type=int, default=3)
    p.add_argument('--out', default='results/param_sweep_quick.json')
    args = p.parse_args()

    symbol = args.symbol.upper()
    wf_csv = os.path.join('results', f"{symbol.lower()}_wf_verify.csv")
    mc_csv = os.path.join('results', f"{symbol.lower()}_mc_robustness.csv")
    data_csv = os.path.join('data', f"{symbol}_{args.interval}.csv")
    if not os.path.exists(wf_csv) or not os.path.exists(mc_csv) or not os.path.exists(data_csv):
        print('Required files missing (wf, mc results, or market data).')
        return

    candidates = load_candidates(wf_csv, max_candidates=args.max_candidates)
    df_market = pd.read_csv(data_csv, parse_dates=[0], index_col=0)

    # small grid to keep runtime short
    stop_losses = [0.002, 0.01]
    take_profits = [0.01, 0.02]
    pos_policies = [
        ("capital_fraction", 0.005),
        ("capital_fraction", 0.01),
        ("risk_per_trade", 0.005),
    ]
    slippages = [0.0, 0.001]
    fees = [0.0, 0.0005]

    results = []
    for idx, row in enumerate(candidates, start=1):
        base_params = parse_params_from_wf_row(row)
        for sl, fee, slp, tp, (method, val) in itertools.product(slippages, fees, stop_losses, take_profits, pos_policies):
            params = dict(base_params)
            params['stop_loss_pct'] = slp
            params['take_profit_pct'] = tp
            # set position sizing policy
            if method == 'capital_fraction':
                params['position_size'] = val
            else:
                params['position_size_policy'] = {'method': 'risk_per_trade', 'value': val}
            try:
                res = run_sim(symbol, args.interval, df_market, params, slippage=sl, fee=fee)
                results.append({
                    'rank': int(row.get('rank') or idx),
                    'stop_loss_pct': slp,
                    'take_profit_pct': tp,
                    'position_policy': method,
                    'position_value': val,
                    'slippage': sl,
                    'fee': fee,
                    'profit_pct': res.get('profit_percentage'),
                    'total_trades': res.get('total_trades'),
                    'win_rate': res.get('win_rate'),
                    'max_drawdown_pct': res.get('max_drawdown_pct'),
                })
            except Exception as e:
                results.append({'rank': int(row.get('rank') or idx), 'error': str(e)})

    # sort and write best results per rank
    df = pd.DataFrame(results)
    out = {'symbol': symbol, 'summary': []}
    for r, g in df.groupby('rank'):
        g2 = g[g['profit_pct'].notna()] if 'profit_pct' in g.columns else g
        if g2.empty:
            out['summary'].append({'rank': r, 'best': None})
            continue
        best = g2.sort_values(by='profit_pct', ascending=False).head(3).to_dict(orient='records')
        out['summary'].append({'rank': r, 'best': best})

    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2)

    print('Wrote sweep summary to', args.out)


if __name__ == '__main__':
    main()
