import json, os
from statistics import mean, median, pstdev

IN_DIR = os.path.join(os.getcwd(), 'backtest_results_mtf')
OUT = os.path.join(os.getcwd(), 'backtest_analysis_report_mtf.md')

symbols = ['BTCUSDT','JELLYJELLYUSDT']
lines = []
lines.append('# MTF Stoch-RSI Backtest Comparison (1m+3m, 7d)')
lines.append('')

for s in symbols:
    base_file = os.path.join(IN_DIR, f'baseline_{s}_1m_7d.json')
    mtf_file = os.path.join(IN_DIR, f'mtf_{s}_1m_7d.json')
    if not os.path.exists(base_file) or not os.path.exists(mtf_file):
        continue
    with open(base_file, 'r', encoding='utf-8') as f:
        base = json.load(f)
    with open(mtf_file, 'r', encoding='utf-8') as f:
        mtf = json.load(f)

    def analyze(res):
        total = res.get('total_trades', 0)
        trades = res.get('trades', []) or []
        wins = [t for t in trades if t.get('net_pnl', 0) > 0]
        win_rate = (len(wins) / total * 100) if total else 0.0
        max_dd = res.get('max_drawdown_pct', 0.0)
        # trade percent relative to initial balance
        tperc = []
        for t in trades:
            npnl = t.get('net_pnl', 0.0)
            pct = (npnl / res.get('initial_balance', 1000.0)) * 100
            tperc.append(pct)
        trades_ge_3 = len([p for p in tperc if p >= 3.0])
        pct_ge_3 = (trades_ge_3 / total * 100) if total else 0.0
        avg = mean(tperc) if tperc else 0.0
        med = median(tperc) if tperc else 0.0
        sd = pstdev(tperc) if len(tperc) > 1 else 0.0
        return {
            'total': total,
            'win_rate': win_rate,
            'max_dd': max_dd,
            'trades_ge_3': trades_ge_3,
            'pct_ge_3': pct_ge_3,
            'avg_trade_pct': avg,
            'median_trade_pct': med,
            'std_trade_pct': sd,
        }

    b = analyze(base)
    m = analyze(mtf)

    lines.append(f'## {s}')
    lines.append(f'- Baseline: trades={b["total"]}, win_rate={b["win_rate"]:.2f}%, trades>=3%={b["trades_ge_3"]} ({b["pct_ge_3"]:.2f}%), max_dd={b["max_dd"]:.2f}%')
    lines.append(f'- MTF enabled: trades={m["total"]}, win_rate={m["win_rate"]:.2f}%, trades>=3%={m["trades_ge_3"]} ({m["pct_ge_3"]:.2f}%), max_dd={m["max_dd"]:.2f}%')
    lines.append('')
    # detailed delta
    lines.append('### Delta (MTF - Baseline)')
    lines.append(f'- Trade count change: {m["total"] - b["total"]}')
    lines.append(f'- Win rate change: {m["win_rate"] - b["win_rate"]:.2f}%')
    lines.append(f'- Trades >=3% change (abs): {m["trades_ge_3"] - b["trades_ge_3"]} ({m["pct_ge_3"] - b["pct_ge_3"]:.2f}pp)')
    lines.append(f'- Max drawdown change: {m["max_dd"] - b["max_dd"]:.2f}pp')
    lines.append('')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print('Wrote', OUT)
