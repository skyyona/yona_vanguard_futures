import sys
import csv
import statistics

def summarize(path):
    with open(path, newline='', encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))
    total = len(rows)
    aborted = sum(1 for r in rows if (r.get('aborted_early') or '').lower() in ('true','1'))
    insufficient = sum(1 for r in rows if (r.get('insufficient_trades') or '').lower() in ('true','1'))
    runtimes = [float(r.get('runtime_sec') or 0) for r in rows]
    avg_runtime = statistics.mean(runtimes) if runtimes else 0.0
    print(f"file: {path}")
    print(f"total_tasks: {total}")
    print(f"aborted_early_count: {aborted}")
    print(f"insufficient_trades_count: {insufficient}")
    print(f"avg_runtime_sec: {avg_runtime:.3f}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python scripts/summary_earlystop.py <csv_path>')
        sys.exit(2)
    summarize(sys.argv[1])
