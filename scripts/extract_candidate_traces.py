"""Extract per-candidate sample simulation traces and summaries.

Usage:
  python scripts/extract_candidate_traces.py --symbol PIPPINUSDT --samples 5
"""
from __future__ import annotations
import os, csv, argparse, json, random
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
import sys
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.core.strategy_simulator import StrategySimulator
from scripts.output_config import legacy_dir


def parse_candidate_row(row: dict) -> dict:
    # replicate parse_params_from_wf_row from mc_robustness
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


def run_sample_simulation(symbol, interval, df, params, seed, slippage, fee, noise_sigma):
    rng = random.Random(seed)
    # apply simple noise same as mc_robustness noisy_df
    if noise_sigma and noise_sigma > 0:
        df2 = df.copy()
        for col in ['open','high','low','close']:
            if col in df2.columns:
                noise = [rng.gauss(0, noise_sigma) for _ in range(len(df2))]
                df2[col] = df2[col] * (1.0 + pd.Series(noise, index=df2.index))
    else:
        df2 = df

    sim = StrategySimulator()
    p = dict(params)
    p['slippage_pct'] = slippage
    p['fee_pct'] = fee
    # use deterministic initial_balance and leverage to match MC
    res = sim.run_simulation(symbol, interval, df2.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=p)
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--interval', default='5m')
    p.add_argument('--samples', type=int, default=5)
    p.add_argument('--outdir', default=None)
    p.add_argument('--slippage', type=float, default=0.001)
    p.add_argument('--fee', type=float, default=0.0005)
    p.add_argument('--noise-sigma', type=float, default=0.001)
    args = p.parse_args()

    symbol = args.symbol.upper()
    mc_csv = os.path.join('results', f"{symbol.lower()}_mc_robustness.csv")
    wf_csv = os.path.join('results', f"{symbol.lower()}_wf_verify.csv")
    if not os.path.exists(mc_csv):
        print('MC results CSV not found:', mc_csv)
        return
    if not os.path.exists(os.path.join('data', f"{symbol}_{args.interval}.csv")):
        print('Market data CSV missing for symbol/interval:', symbol, args.interval)
        return

    outdir = args.outdir if args.outdir else os.path.join(legacy_dir(), 'traces')
    os.makedirs(outdir, exist_ok=True)
    traces_dir = os.path.join(outdir, symbol.lower())
    os.makedirs(traces_dir, exist_ok=True)

    # read mc csv rows as candidates
    candidates = []
    with open(mc_csv, newline='', encoding='utf-8') as fh:
        dr = csv.DictReader(fh)
        for r in dr:
            candidates.append(r)

    df_market = pd.read_csv(os.path.join('data', f"{symbol}_{args.interval}.csv"), parse_dates=[0], index_col=0)

    summary_rows = []
    base_seed = 99999
    for row in candidates:
        rank = int(row.get('rank') or 0)
        params = parse_candidate_row(row)
        cand_summary = {'rank': rank, 'runs': []}
        for i in range(args.samples):
            seed = base_seed + rank * 1000 + i
            res = run_sample_simulation(symbol, args.interval, df_market, params, seed, args.slippage, args.fee, args.noise_sigma)
            # write trades csv for this run
            runs_dir = os.path.join(traces_dir, f'rank_{rank}')
            os.makedirs(runs_dir, exist_ok=True)
            trades = res.get('trades', [])
            trades_file = os.path.join(runs_dir, f'run_{i+1}_trades.csv')
            with open(trades_file, 'w', newline='', encoding='utf-8') as fh:
                if trades:
                    keys = sorted(trades[0].keys())
                    writer = csv.DictWriter(fh, fieldnames=keys)
                    writer.writeheader()
                    for t in trades:
                        writer.writerow({k: t.get(k) for k in keys})
                else:
                    fh.write('')

            # collect run-level metrics
            run_metrics = {
                'run': i+1,
                'profit_pct': res.get('profit_percentage'),
                'total_trades': res.get('total_trades'),
                'win_rate': res.get('win_rate'),
                'max_drawdown_pct': res.get('max_drawdown_pct'),
                'aborted_early': res.get('aborted_early'),
                'insufficient_trades': res.get('insufficient_trades'),
            }
            # exit reasons distribution and avg trade pnl
            exit_reasons = {}
            pnls = []
            for t in trades:
                reason = t.get('exit_reason') or 'UNKNOWN'
                exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
                pnls.append(t.get('net_pnl') or 0.0)
            run_metrics['exit_reasons'] = exit_reasons
            run_metrics['avg_trade_net_pnl'] = sum(pnls)/len(pnls) if pnls else 0.0
            cand_summary['runs'].append(run_metrics)

        # write candidate summary json
        cand_summary_file = os.path.join(traces_dir, f'rank_{rank}_summary.json')
        with open(cand_summary_file, 'w', encoding='utf-8') as fh:
            json.dump(cand_summary, fh, indent=2)
        summary_rows.append(cand_summary)

    # write consolidated summary
    consolidated = os.path.join(args.outdir, f'{symbol.lower()}_trace_consolidated.json')
    with open(consolidated, 'w', encoding='utf-8') as fh:
        json.dump(summary_rows, fh, indent=2)

    print('Wrote traces to', traces_dir)


if __name__ == '__main__':
    main()
