#!/usr/bin/env python3
"""
Simple analyzer for MTF/backtest JSON results.

Usage:
  python scripts/analyze_mtf_result.py --file path/to/mtf_BEATUSDT_1m_1d.json
  python scripts/analyze_mtf_result.py --symbol BEATUSDT

The script looks for files under `backtest_results_mtf/` when given a symbol.
It extracts a `trades` list from the JSON and computes: total trades, wins, losses,
win rate, avg win, avg loss, gross win/loss, total fees (if present), net pnl.
Outputs a JSON summary to `backtest_results_mtf/analysis_<symbol>.json` and prints
an ASCII summary to stdout.
"""
import argparse
import glob
import json
import os
import sys
from typing import Any, Dict, List, Optional
from scripts.output_config import backtest_mtf_dir, legacy_dir


def find_trades(obj: Any) -> Optional[List[Dict[str, Any]]]:
    if isinstance(obj, dict):
        if 'trades' in obj and isinstance(obj['trades'], list):
            return obj['trades']
        for v in obj.values():
            t = find_trades(v)
            if t:
                return t
    elif isinstance(obj, list):
        for item in obj:
            t = find_trades(item)
            if t:
                return t
    return None


def num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None


def analyze_trades(trades: List[Dict[str, Any]], initial_balance: Optional[float]) -> Dict[str, Any]:
    rows = []
    wins = 0
    losses = 0
    gross_win = 0.0
    gross_loss = 0.0
    total_fees = 0.0
    pnls = []

    for tr in trades:
        pnl = None
        if 'pnl' in tr:
            pnl = num(tr.get('pnl'))
        elif 'realized_pnl' in tr:
            pnl = num(tr.get('realized_pnl'))
        elif 'pnl_pct' in tr and initial_balance is not None:
            pp = num(tr.get('pnl_pct'))
            if pp is not None:
                pnl = initial_balance * (pp / 100.0)

        fees = num(tr.get('fees') or tr.get('fee') or 0.0) or 0.0
        total_fees += fees

        if pnl is None:
            # try compute from entry/exit prices if side and qty provided
            ep = num(tr.get('entry_price') or tr.get('entry'))
            xp = num(tr.get('exit_price') or tr.get('exit'))
            qty = num(tr.get('qty') or tr.get('quantity') or tr.get('size') or 0)
            side = (tr.get('side') or '').lower()
            if ep is not None and xp is not None and qty:
                if side in ('sell', 'short', 'sellshort'):
                    pnl = (ep - xp) * qty
                else:
                    pnl = (xp - ep) * qty

        if pnl is not None:
            pnls.append(pnl)
            if pnl > 0:
                wins += 1
                gross_win += pnl
            else:
                losses += 1
                gross_loss += pnl

        rows.append({
            'entry_time': tr.get('entry_time') or tr.get('entryTs'),
            'exit_time': tr.get('exit_time') or tr.get('exitTs'),
            'entry_price': tr.get('entry_price') or tr.get('entry'),
            'exit_price': tr.get('exit_price') or tr.get('exit'),
            'qty': tr.get('qty') or tr.get('quantity') or tr.get('size'),
            'pnl': pnl,
            'fees': fees,
            'exit_reason': tr.get('exit_reason') or tr.get('reason') or tr.get('exitReason')
        })

    total_trades = len([r for r in rows if r.get('pnl') is not None])
    win_rate = (wins / total_trades * 100.0) if total_trades else None
    avg_win = (gross_win / wins) if wins else None
    avg_loss = (gross_loss / losses) if losses else None
    net_pnl = sum([r['pnl'] for r in rows if r.get('pnl') is not None]) - total_fees

    summary = {
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate_pct': round(win_rate, 3) if win_rate is not None else None,
        'avg_win': round(avg_win, 8) if avg_win is not None else None,
        'avg_loss': round(avg_loss, 8) if avg_loss is not None else None,
        'gross_win': round(gross_win, 8),
        'gross_loss': round(gross_loss, 8),
        'total_fees': round(total_fees, 8),
        'net_pnl': round(net_pnl, 8),
        'rows_with_pnl': total_trades
    }

    return {'summary': summary, 'trades': rows}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--file', '-f', help='Path to mtf JSON file')
    p.add_argument('--symbol', '-s', help='Symbol name to search under backtest_results_mtf/')
    args = p.parse_args()

    results_dir = backtest_mtf_dir()
    if args.file:
        path = args.file
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        files = [path]
    elif args.symbol:
        pattern = os.path.join(results_dir, f'*{args.symbol}*.json')
        files = sorted(glob.glob(pattern))
        if not files:
            print(f'No files found matching: {pattern}', file=sys.stderr)
            sys.exit(2)
    else:
        print('Either --file or --symbol is required', file=sys.stderr)
        sys.exit(2)

    for fpath in files:
        print('Processing', fpath)
        with open(fpath, 'r', encoding='utf-8') as fh:
            data = json.load(fh)

        # try to find initial_balance
        initial_balance = None
        if isinstance(data, dict):
            initial_balance = num(data.get('initial_balance') or data.get('initialBalance'))

        trades = find_trades(data)
        if not trades:
            print('No `trades` list found in file.', file=sys.stderr)
            continue

        res = analyze_trades(trades, initial_balance)

        # write summary into canonical backtest outputs directory
        sym = args.symbol or os.path.basename(fpath).split('.')[0]
        out_dir = backtest_mtf_dir()
        out_path = os.path.join(out_dir, f'analysis_{sym}.json')
        with open(out_path, 'w', encoding='utf-8') as ofh:
            json.dump(res, ofh, ensure_ascii=False, indent=2)

        # print concise table
        s = res['summary']
        print('\nSummary:')
        for k, v in s.items():
            print(f'  {k}: {v}')

    print('\nDone. Analysis files written to', results_dir)


if __name__ == '__main__':
    main()
