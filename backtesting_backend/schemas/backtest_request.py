from __future__ import annotations
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    strategy_name: str
    symbol: str
    interval: str
    start_time: int = Field(..., description="UTC timestamp in milliseconds")
    end_time: int = Field(..., description="UTC timestamp in milliseconds")
    initial_balance: float = Field(..., description="Initial capital for simulation")
    leverage: int = Field(..., description="Leverage to apply during simulation")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    # Optional execution and risk parameters that simulators may consume
    take_profit_pct: float = Field(0.0, description="Take-profit as decimal (e.g., 0.02 for 2%)")
    trailing_stop_pct: float = Field(0.0, description="Trailing stop as decimal (e.g., 0.01 for 1%)")
    fee_pct: float = Field(0.0, description="Fee percent per trade side as decimal (e.g., 0.0005 for 0.05%)")
    slippage_pct: float = Field(0.0, description="Slippage percent per trade side as decimal (e.g., 0.001 for 0.1%)")
    position_size: float = Field(1.0, description="Notional position size in simulation units (default 1.0)")
    optimization_mode: bool = Field(False, description="If True, run parameter optimization")
    optimization_ranges: Optional[Dict[str, Any]] = None
    # pydantic v2 config
    model_config = {"from_attributes": True}
