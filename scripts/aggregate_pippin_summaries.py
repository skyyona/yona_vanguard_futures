"""Aggregate PIPPINUSDT per-run summary CSVs into one CSV and print top configurations.

Usage:
  python .\scripts\aggregate_pippin_summaries.py
"""
from __future__ import annotations
import os, csv, re
from glob import glob

SRC_DIR = os.path.join('results', 'pippinusdt_masked_next_open')
OUT_PATH = os.path.join('results', 'pippinusdt_aggregate_grid.csv')

def parse_meta_from_filename(fname):
    # filenames might be like 2025-11-21_v3.0_c1_a1.5_summary.csv or simple 2025-11-21_summary.csv
    base = os.path.basename(fname)
    m = re.search(r'_v(?P<v>[0-9\.]+)_c(?P<c>[0-9]+)_a(?P<a>[0-9\.]+)', base)
    if m:
        return {'vol_threshold': float(m.group('v')), 'confirmation': int(m.group('c')), 'atr_mult': float(m.group('a'))}
    return {}

def collect():
    rows = []
    if not os.path.isdir(SRC_DIR):
        print('No summaries directory:', SRC_DIR)
        return rows
    files = sorted(glob(os.path.join(SRC_DIR, '*_summary.csv')))
    if not files:
        print('No summary CSVs found in', SRC_DIR)
        return rows
    for fn in files:
        try:
            with open(fn, newline='', encoding='utf-8') as fh:
                rdr = csv.DictReader(fh)
                recs = list(rdr)
                if not recs:
                    continue
                rec = dict(recs[0])
                meta = parse_meta_from_filename(fn)
                # prefer filename meta if present, else keep fields from rec
                for k,v in meta.items():
                    rec[k] = v
                rec['source_file'] = os.path.basename(fn)
                rows.append(rec)
        except Exception as e:
            print('Failed to read', fn, '->', e)
    return rows

def write(rows):
    if not rows:
        print('No rows to write')
        return
    os.makedirs('results', exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(OUT_PATH, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    print('Wrote aggregate to', OUT_PATH)

def print_top(rows, by='profit_pct', top=10):
    # try multiple possible profit column names
    candidates = [by, 'profit_percentage', 'final_balance']
    col = None
    for c in candidates:
        if any(c in r for r in rows):
            col = c
            break
    if col is None:
        print('No profit column found. Available keys:', list(rows[0].keys()))
        return
    # convert values
    def keyfn(r):
        try:
            return float(r.get(col, 0))
        except:
            return 0.0
    rows_sorted = sorted(rows, key=keyfn, reverse=True)
    print(f'Top {top} by {col}:')
    for r in rows_sorted[:top]:
        print({k: r.get(k) for k in ['date','vol_threshold','confirmation','atr_mult','total_trades','profit_pct','profit_percentage','final_balance','source_file'] if k in r})

def main():
    rows = collect()
    if not rows:
        return
    write(rows)
    print_top(rows, top=20)

if __name__ == '__main__':
    main()
