from __future__ import annotations

from typing import Dict, Any, Optional

from pydantic import BaseModel, Field


class StrategyAssignmentCreate(BaseModel):
    """Request model for assigning a strategy to an engine.

    The parameters field should contain the executable parameters selected
    from strategy-analysis (e.g. engine_results[engine]["executable_parameters"]).
    """

    symbol: str = Field(..., description="Trading symbol, e.g. BTCUSDT")
    interval: str = Field(..., description="Kline interval, e.g. 1m, 5m")
    engine: str = Field(..., description="Engine identifier, e.g. alpha/beta/gamma")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Executable strategy parameters for this symbol/engine.",
    )
    source: Optional[str] = Field(
        default="manual",
        description="Source of assignment (e.g. gui, auto, backtest-analysis)",
    )
    assigned_by: Optional[str] = Field(
        default=None,
        description="Who initiated this assignment (user id, system, etc.)",
    )
    note: Optional[str] = Field(default=None, description="Optional human-readable note")

    # pydantic v2 config
    model_config = {"from_attributes": True}


class StrategyAssignmentRead(BaseModel):
    """Combined view of assignment and its parameter set."""

    id: int
    symbol: str
    interval: str
    engine: str
    parameter_set_id: int
    parameters: Dict[str, Any] = Field(default_factory=dict)
    assigned_at: int
    assigned_by: Optional[str] = None
    note: Optional[str] = None

    # pydantic v2 config
    model_config = {"from_attributes": True}


class StrategyAssignmentListResponse(BaseModel):
    """List wrapper for multiple assignments."""

    items: list[StrategyAssignmentRead] = Field(default_factory=list)
