from __future__ import annotations
from typing import Dict, Any, Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class BacktestResult(BaseModel):
    run_id: UUID
    strategy_name: str
    symbol: str
    interval: str
    start_time: int
    end_time: int
    initial_balance: float
    final_balance: float
    profit_percentage: float
    max_drawdown: float
    total_trades: int
    win_rate: float
    parameters_used: Dict[str, Any]
    optimized_parameters: Optional[Dict[str, Any]] = None
    trades: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: int
    # pydantic v2: replace `class Config: orm_mode = True` with `model_config`
    model_config = {"from_attributes": True}
