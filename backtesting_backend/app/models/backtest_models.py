from pydantic import BaseModel
from typing import Dict, Any, Optional


class BacktestRequestModel(BaseModel):
    strategy: str
    symbol: str
    start: str
    end: str
    config: Optional[Dict[str, Any]] = None


class BacktestResultModel(BaseModel):
    strategy: str
    symbol: str
    events_count: int
    events: Optional[Any] = None
