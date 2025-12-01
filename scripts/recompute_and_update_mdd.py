import sys
from pathlib import Path
import requests
import json
import asyncio

# Insert project root to import package modules
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))

from backtesting_backend.database.repositories.backtest_result_repository import BacktestResultRepository
from backtesting_backend.database.db_manager import BacktestDB

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "1c14b2cd-ddb4-4060-b541-ec95c1c4ce17"
STATUS_URL = f"http://127.0.0.1:8001/api/v1/backtest/backtest_status/{RUN_ID}"
RESULT_URL = f"http://127.0.0.1:8001/api/v1/backtest/backtest_result/{RUN_ID}"


def compute_max_drawdown_from_trades(initial_balance, trades):
    # trades: list of dict with 'net_pnl' field, in chronological order
    balances = [initial_balance]
    b = initial_balance
    for t in trades:
        pnl = t.get('net_pnl', 0.0) or 0.0
        try:
            pnl = float(pnl)
        except Exception:
            pnl = 0.0
        b = b + pnl
        balances.append(b)
    # compute peak->trough max drawdown
    peak = -1e18
    max_dd = 0.0
    for val in balances:
        if val > peak:
            peak = val
        if peak > 0:
            dd = (peak - val) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd * 100


async def main():
    try:
        r = requests.get(STATUS_URL, timeout=10)
        r.raise_for_status()
        status = r.json()
    except Exception as e:
        print('Failed to fetch status:', e)
        return

    result = status.get('result')
    if not result:
        print('No result payload in status for run_id', RUN_ID)
        return

    # if simulator already provided max_drawdown_pct, use it
    md = result.get('max_drawdown_pct')
    if md is None:
        # try compute from trades
        initial_balance = result.get('initial_balance') or result.get('initialBalance') or None
        if initial_balance is None:
            # fallback: fetch DB record to get initial_balance
            try:
                r2 = requests.get(RESULT_URL, timeout=5)
                r2.raise_for_status()
                rec = r2.json()
                initial_balance = rec.get('initial_balance') or rec.get('initialBalance')
            except Exception:
                initial_balance = 1000.0

        trades = result.get('trades') or []
        if not trades:
            print('No trades in result to compute drawdown')
            return
        md = compute_max_drawdown_from_trades(float(initial_balance), trades)
        print(f'Computed max_drawdown_pct = {md:.6f}% from {len(trades)} trades')
    else:
        print('Found max_drawdown_pct in result payload:', md)

    # update DB record
    # ensure DB initialized (when running standalone script)
    await BacktestDB.get_instance().init()
    repo = BacktestResultRepository()
    updates = {'max_drawdown': float(md)}
    updated = await repo.update_backtest_result(RUN_ID, updates)
    if updated:
        print(f'Updated DB run {RUN_ID} with max_drawdown = {md:.6f}%')
    else:
        print(f'No DB record found for run {RUN_ID}')

if __name__ == '__main__':
    asyncio.run(main())
