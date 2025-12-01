import sys
import asyncio
import requests
import ast
from pathlib import Path

# ensure repo root on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtesting_backend.database.repositories.backtest_result_repository import BacktestResultRepository

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "1c14b2cd-ddb4-4060-b541-ec95c1c4ce17"
STATUS_URL = f"http://127.0.0.1:8001/api/v1/backtest/backtest_status/{RUN_ID}"

async def main():
    try:
        r = requests.get(STATUS_URL, timeout=5)
        r.raise_for_status()
        status = r.json()
    except Exception as e:
        print("Failed to fetch status:", e)
        return

    result = status.get("result")
    if not result:
        print("No result payload available in status for run_id", RUN_ID)
        return

    md = result.get("max_drawdown_pct") or result.get("max_drawdown")
    if md is None:
        print("No max_drawdown_pct found in result payload")
        return

    repo = BacktestResultRepository()
    updates = {"max_drawdown": float(md)}
    updated = await repo.update_backtest_result(RUN_ID, updates)
    if updated:
        print(f"Updated run {RUN_ID} max_drawdown to {md}")
    else:
        print(f"No DB record found for run {RUN_ID}")

if __name__ == '__main__':
    asyncio.run(main())
