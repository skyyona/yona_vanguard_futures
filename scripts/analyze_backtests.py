import os, json, math, statistics

BASE = os.getcwd()
DIRS = [os.path.join(BASE, 'backtest_results'), os.path.join(BASE, 'backtest_results_extended')]
OUT = os.path.join(BASE, 'backtest_analysis_report.md')
INITIAL_BALANCE = 1000.0

files = []
for d in DIRS:
    if not os.path.isdir(d):
        continue
    for fn in os.listdir(d):
        if fn.lower().endswith('.json'):
            files.append(os.path.join(d, fn))

summary = []

for path in sorted(files):
    with open(path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception as e:
            print('failed', path, e)
            continue
    symbol = os.path.splitext(os.path.basename(path))[0]
    total_trades = data.get('total_trades', 0)
    profit_pct = data.get('profit_percentage', None)
    final_balance = data.get('final_balance', None)
    win_rate = data.get('win_rate', None)
    max_dd = data.get('max_drawdown_pct', None)
    trades = data.get('trades', []) or []
    per_trade_percents = []
    for t in trades:
        net = t.get('net_pnl')
        if net is None:
            net = t.get('net_pnl', 0)
        try:
            pct = (float(net) / INITIAL_BALANCE) * 100.0
            per_trade_percents.append(pct)
        except Exception:
            pass
    # metrics vs 3% TP
    tp_target = 3.0
    trades_meeting_tp = sum(1 for p in per_trade_percents if p >= tp_target)
    trades_meeting_tp_pct = (trades_meeting_tp / len(per_trade_percents) * 100.0) if per_trade_percents else 0
    avg_trade_pct = statistics.mean(per_trade_percents) if per_trade_percents else 0
    median_trade_pct = statistics.median(per_trade_percents) if per_trade_percents else 0
    stdev_trade_pct = statistics.pstdev(per_trade_percents) if per_trade_percents else 0

    summary.append({
        'file': path,
        'symbol': symbol,
        'total_trades': total_trades,
        'profit_pct': profit_pct,
        'final_balance': final_balance,
        'win_rate': win_rate,
        'max_drawdown_pct': max_dd,
        'n_trades_meeting_3pct': trades_meeting_tp,
        'pct_trades_meeting_3pct': trades_meeting_tp_pct,
        'avg_trade_pct': avg_trade_pct,
        'median_trade_pct': median_trade_pct,
        'stdev_trade_pct': stdev_trade_pct,
        'n_trades_with_data': len(per_trade_percents)
    })

# write report
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('# Backtest Analysis Report\n\n')
    f.write('Goal: short-term scalping with reliable 3% take-profit per trade (compound).\n\n')
    for s in summary:
        f.write(f"## {s['symbol']}\n")
        f.write(f"- Source file: {s['file']}\n")
        f.write(f"- Total trades: {s['total_trades']}\n")
        f.write(f"- Trades with trade-level data: {s['n_trades_with_data']}\n")
        f.write(f"- Final profit %: {s['profit_pct']}\n")
        f.write(f"- Final balance: {s['final_balance']}\n")
        f.write(f"- Win rate: {s['win_rate']}\n")
        f.write(f"- Max drawdown (%): {s['max_drawdown_pct']}\n")
        f.write(f"- Avg trade % (net_pnl / initial_balance*100): {s['avg_trade_pct']:.4f}%\n")
        f.write(f"- Median trade %: {s['median_trade_pct']:.4f}%\n")
        f.write(f"- Stddev trade %: {s['stdev_trade_pct']:.4f}%\n")
        f.write(f"- Trades >= 3% TP: {s['n_trades_meeting_3pct']} ({s['pct_trades_meeting_3pct']:.2f}%)\n\n")

    # high level assessment
    f.write('## High-level assessment\n')
    avg_profit = sum((s['profit_pct'] or 0) for s in summary) / len(summary) if summary else 0
    avg_win_rate = sum((s['win_rate'] or 0) for s in summary) / len(summary) if summary else 0
    f.write(f"- Average final profit% across analyzed backtests: {avg_profit:.4f}%\n")
    f.write(f"- Average win rate across analyzed backtests: {avg_win_rate:.2f}%\n\n")

    f.write('## Fit to 3% TP scalping goal\n')
    f.write('- The report below shows per-symbol how often individual trades achieved >=3% net profit (as % of initial balance).\n')
    f.write('- Desired properties for the strategy to reliably compound at ~3% per-trade:\n')
    f.write('  - A substantial fraction of trades should hit >=3% TP (recommended > 20%).\n')
    f.write('  - Win rate sufficiently high to overcome losses and trading costs (example: win_rate > 50% if average win near 3% and average loss similar magnitude).\n')
    f.write('  - Low max_drawdown relative to capital to avoid blowups.\n\n')

    for s in summary:
        f.write(f"### {s['symbol']} assessment\n")
        if s['n_trades_with_data'] == 0:
            f.write('- No per-trade data available; cannot assess trade-level TP attainment.\n\n')
            continue
        f.write(f"- {s['pct_trades_meeting_3pct']:.2f}% of trades reached >=3% TP.\n")
        if s['pct_trades_meeting_3pct'] >= 20.0:
            f.write('- Meets recommended per-trade TP frequency threshold (>=20%).\n')
        else:
            f.write('- BELOW recommended per-trade TP frequency (improvement needed).\n')
        f.write(f"- Average trade %: {s['avg_trade_pct']:.4f}%, Median: {s['median_trade_pct']:.4f}%.\n")
        if (s['avg_trade_pct'] >= 3.0):
            f.write('- Average trade exceeds 3% — promising for 3% TP compounding.\n')
        else:
            f.write('- Average trade below 3% — strategy on average does not deliver 3% per trade.\n')
        f.write(f"- Win rate: {s['win_rate']}%, Max DD: {s['max_drawdown_pct']}%.\n")
        if s['max_drawdown_pct'] and s['max_drawdown_pct'] > 50:
            f.write('- Very large drawdown observed; capital protection / risk sizing must be improved.\n')
        f.write('\n')

    f.write('## Recommended optimization directions\n')
    f.write('- Filter entries for stronger momentum: require multi-timeframe confirmation (e.g., 15m EMA alignment + 5m entry).\n')
    f.write('- Use a volatility-adaptive position sizing so that a 3% TP corresponds to a fixed volatility band (ATR-based sizing).\n')
    f.write('- Tighten exits: explicitly set TP at 3% with a short timeout; test using different SL rules (e.g., -1% fixed, ATR-based).\n')
    f.write('- Reduce exposure on low-liquidity / high-slippage symbols; prefer high-liquidity coins.\n')
    f.write('- Add pre-entry filters: volume spike, spread check, and avoid trading across major news.\n')
    f.write('- Perform parameter grid search for TP/SL/entry thresholds and re-run on walk-forward windows.\n')
    f.write('- Add transaction costs and slippage modeling in backtests to ensure 3% TP survives real conditions.\n')
    f.write('- Consider shorter holding-time heuristics and limit max trade duration to avoid large adverse moves.\n')

    f.write('\n## Next steps / actions to implement\n')
    f.write('1. Run parameter sweep for TP in [1%,2%,3%,4%,5%] with SL in [-0.5%,-1%,-2%] across symbols and intervals.\n')
    f.write('2. Implement ATR-based position sizing so that risk per trade is capped (e.g., 0.5% of capital).\n')
    f.write('3. Add multi-timeframe EMA alignment filter and test improvement in TP attainment.\n')
    f.write('4. Re-run extended backtests with realistic fees/slippage and produce a final recommended set of params for live testing.\n')

print('Analysis written to', OUT)
