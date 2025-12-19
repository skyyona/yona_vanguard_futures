from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

router = APIRouter()


class BacktestRequest(BaseModel):
    strategy: str
    symbol: str
    start: str
    end: str
    config: Dict[str, Any] = {}


@router.post("/backtest")
async def run_backtest(req: BacktestRequest):
    """Run a quick backtest using the strategy simulator (lightweight)."""
    try:
        # Lazy import to avoid heavy startup if simulator missing
        from backtesting_backend.core.strategy_simulator import StrategySimulator

        sim = StrategySimulator()
        result = sim.run_once(strategy=req.strategy, symbol=req.symbol, start=req.start, end=req.end, config=req.config)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
