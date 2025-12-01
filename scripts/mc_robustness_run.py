"""Run-friendly copy of the Monte‑Carlo pilot (clean file used for execution).

This avoids any potential duplicate/concatenation issues in the original file.
"""
from __future__ import annotations
import argparse, os, sys, csv, random
from concurrent.futures import ProcessPoolExecutor, as_completed
from statistics import mean, pstdev

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from backtesting_backend.core.strategy_simulator import StrategySimulator


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--interval', default='5m')
    p.add_argument('--start', required=False)
    p.add_argument('--end', required=False)
    p.add_argument('--mc-iter', type=int, default=20)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--max-candidates', type=int, default=5)
    p.add_argument('--max-slippage', type=float, default=0.002)
    p.add_argument('--max-fee', type=float, default=0.0005)
    p.add_argument('--noise-sigma', type=float, default=0.001)
    return p.parse_args()


def read_wf_candidates(path: str, max_candidates: int):
    rows = []
    with open(path, newline='', encoding='utf-8') as fh:
        dr = csv.DictReader(fh)
        for r in dr:
            rows.append(r)
    filtered = [r for r in rows if int(float(r.get('wf_positive_windows') or 0)) >= 2]
    try:
        sorted_rows = sorted(filtered, key=lambda r: float(r.get('wf_mean_profit_pct') or 0), reverse=True)
    except Exception:
        sorted_rows = filtered
    return sorted_rows[:max_candidates]


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


def noisy_df(df: pd.DataFrame, sigma: float, rng: random.Random) -> pd.DataFrame:
    if sigma and sigma > 0:
        df2 = df.copy()
        for col in ['open', 'high', 'low', 'close']:
            if col in df2.columns:
                noise = [rng.gauss(0, sigma) for _ in range(len(df2))]
                df2[col] = df2[col] * (1.0 + pd.Series(noise, index=df2.index))
        return df2
    return df


def worker_task(task):
    symbol, interval, start, end, params, slippage, fee, noise_sigma, seed, cand_idx = task
    try:
        rng = random.Random(seed)
        df_path = os.path.join('data', f"{symbol}_{interval}.csv")
        if not os.path.exists(df_path):
            return {'error': f'data missing {df_path}', 'cand_idx': cand_idx}
        df = pd.read_csv(df_path, parse_dates=[0], index_col=0)
        if start:
            df = df[df.index >= pd.to_datetime(start)]
        if end:
            df = df[df.index <= pd.to_datetime(end)]
        df_noisy = noisy_df(df, noise_sigma, rng)
        analyzer = StrategyAnalyzer()
        sim = StrategySimulator(analyzer=analyzer)
        p = dict(params)
        p['slippage_pct'] = slippage
        p['fee_pct'] = fee
        res = sim.run_simulation(symbol, interval, df_noisy.copy(), initial_balance=1000.0, leverage=1, strategy_parameters=p)
        return {'profit_pct': res.get('profit_percentage', 0.0), 'cand_idx': cand_idx, 'error': None}
    except Exception as e:
        return {'profit_pct': None, 'cand_idx': cand_idx, 'error': str(e)}


def main():
    args = parse_args()
    symbol = args.symbol.upper()
    wf_path = os.path.join('results', f"{symbol.lower()}_wf_verify.csv")
    if not os.path.exists(wf_path):
        raise SystemExit('WF verify file not found: ' + wf_path)

    candidates = read_wf_candidates(wf_path, max_candidates=args.max_candidates)
    if not candidates:
        raise SystemExit('No WF candidates with sufficient positive windows found.')

    tasks = []
    seed_base = 12345
    for idx, row in enumerate(candidates, start=1):
        params_base = parse_params_from_wf_row(row)
        for it in range(args.mc_iter):
            slippage = random.uniform(0.0, args.max_slippage)
            fee = random.uniform(0.0, args.max_fee)
            seed = seed_base + idx * 1000 + it
            tasks.append((symbol, args.interval, args.start, args.end, params_base, slippage, fee, args.noise_sigma, seed, idx))

    total = len(tasks)
    print(f"Running MC: {total} simulations across {len(candidates)} candidates using {args.workers} workers")

    results_by_idx: dict[int, list[float]] = {i+1: [] for i in range(len(candidates))}
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(worker_task, t): t for t in tasks}
        for fut in as_completed(futs):
            r = fut.result()
            cand_idx = r.get('cand_idx')
            if cand_idx is None:
                continue
            if r.get('error'):
                continue
            results_by_idx.setdefault(cand_idx, []).append(r.get('profit_pct'))

    out_rows = []
    for idx, row in enumerate(candidates, start=1):
        profs = results_by_idx.get(idx, [])
        if profs:
            m = mean(profs)
            s = pstdev(profs) if len(profs) > 1 else 0.0
            sorted_p = sorted(profs)
            fifth = sorted_p[max(0, int(0.05 * len(sorted_p)) - 1)]
            neg_pct = sum(1 for p in profs if p < 0) / len(profs) * 100
            out_rows.append({
                'rank': int(row.get('rank', idx)),
                'stop_loss_pct': row.get('stop_loss_pct'),
                'position_size': row.get('position_size'),
                'take_profit_pct': row.get('take_profit_pct'),
                'volume_spike_factor': row.get('volume_spike_factor'),
                'mc_mean_profit_pct': m,
                'mc_std_profit_pct': s,
                'mc_5th_pct': fifth,
                'mc_negative_pct': neg_pct,
                'mc_samples': len(profs),
            })
        else:
            out_rows.append({
                'rank': int(row.get('rank', idx)),
                'stop_loss_pct': row.get('stop_loss_pct'),
                'position_size': row.get('position_size'),
                'take_profit_pct': row.get('take_profit_pct'),
                'volume_spike_factor': row.get('volume_spike_factor'),
                'mc_mean_profit_pct': None,
                'mc_std_profit_pct': None,
                'mc_5th_pct': None,
                'mc_negative_pct': None,
                'mc_samples': 0,
            })

    out_dir = 'results'
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f"{symbol.lower()}_mc_robustness.csv")
    fieldnames = ['rank','stop_loss_pct','position_size','take_profit_pct','volume_spike_factor','mc_mean_profit_pct','mc_std_profit_pct','mc_5th_pct','mc_negative_pct','mc_samples']
    with open(out_csv, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in sorted(out_rows, key=lambda x: int(x.get('rank', 999))):
            writer.writerow(r)

    print('Wrote', out_csv)


if __name__ == '__main__':
    main()
