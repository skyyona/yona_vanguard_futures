from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class Kline(BaseModel):
    symbol: str
    interval: str
    open_time: int = Field(..., description="UTC timestamp in milliseconds")
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int = Field(..., description="UTC timestamp in milliseconds")
    quote_asset_volume: Optional[float] = None
    number_of_trades: Optional[int] = None
    taker_buy_base_asset_volume: Optional[float] = None
    taker_buy_quote_asset_volume: Optional[float] = None
    ignore: Optional[float] = None
    # pydantic v2 config
    model_config = {"from_attributes": True}
