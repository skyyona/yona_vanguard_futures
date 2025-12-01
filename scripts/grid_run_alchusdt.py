"""Grid-run driver for ALCHUSDT: execute next_open_masked_sim.py over parameter grid and date range,
collect per-day summaries and aggregate into a single CSV for analysis.

Usage:
  python .\scripts\grid_run_alchusdt.py
"""
from __future__ import annotations
import subprocess, os, csv
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def run_one(symbol, date, vol_threshold, confirmation, atr_mult, overshoot_threshold=10.0):
    cmd = [
        'python', os.path.join('scripts', 'next_open_masked_sim.py'),
        '--symbol', symbol,
        '--date', date,
        '--vol-threshold', str(vol_threshold),
        '--confirmation-bars', str(confirmation),
        '--atr-mult', str(atr_mult),
        '--overshoot-threshold', str(overshoot_threshold)
    ]
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return res.returncode

def collect_summary(symbol, date):
    out_dir = os.path.join('results', f"{symbol.lower()}_masked_next_open")
    summary_path = os.path.join(out_dir, f"{date}_summary.csv")
    if not os.path.exists(summary_path):
        return None
    with open(summary_path, newline='', encoding='utf-8') as fh:
        rdr = csv.DictReader(fh)
        rows = list(rdr)
        return rows[0] if rows else None

def daterange(start_date, end_date):
    cur = start_date
    while cur <= end_date:
        yield cur
        cur += timedelta(days=1)

def main():
    symbol = 'ALCHUSDT'
    # date range inclusive
    start = datetime(2025,11,18)
    end = datetime(2025,11,24)

    vols = [3.0, 4.0, 5.0]
    confs = [0,1]
    atrs = [1.5, 2.0]

    out_rows = []
    for v in vols:
        for c in confs:
            for a in atrs:
                for dt in daterange(start, end):
                    date_str = dt.strftime('%Y-%m-%d')
                    code = run_one(symbol, date_str, v, c, a)
                    summary = collect_summary(symbol, date_str)
                    if summary is None:
                        print(f"Missing summary for {date_str} (v={v},c={c},a={a}), rc={code}")
                        continue
                    summary_out = dict(summary)
                    summary_out.update({'vol_threshold': v, 'confirmation': c, 'atr_mult': a, 'date': date_str})
                    out_rows.append(summary_out)

    os.makedirs('results', exist_ok=True)
    out_path = os.path.join('results', f"{symbol.lower()}_next_open_grid_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv")
    if out_rows:
        fieldnames = list(out_rows[0].keys())
        with open(out_path, 'w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for r in out_rows:
                writer.writerow(r)
        print('Wrote grid results to', out_path)
    else:
        print('No results collected')

if __name__ == '__main__':
    main()
