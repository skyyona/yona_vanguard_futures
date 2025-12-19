from typing import Optional, Any, Dict

from backtesting_backend.app.services.strategies.adapter import StrategyAdapter


class LongOnlyAdapter:
    """Simple long-only strategy adapter placeholder for backtests."""

    def __init__(self, symbol: str = "BTCUSDT", broker_client: Optional[Any] = None):
        self.symbol = symbol
        self.broker = broker_client
        self._event_cb = None
        self._running = False

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> bool:
        self._running = False
        return True

    def on_market_update(self, bar_or_tick: Dict[str, Any]) -> None:
        # very small placeholder: generate a HOLD event (no-op)
        return

    def inject_historical_data(self, data: Any) -> None:
        return

    def get_state(self) -> Dict[str, Any]:
        return {"running": self._running}

    def set_event_callback(self, cb):
        self._event_cb = cb


def make_long_only_adapter(symbol: str = "BTCUSDT", broker_client: Optional[Any] = None):
    return LongOnlyAdapter(symbol=symbol, broker_client=broker_client)
