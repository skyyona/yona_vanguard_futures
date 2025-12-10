from typing import Protocol, Any, Dict, Optional, Callable, TypedDict


class OrchestratorEvent(TypedDict, total=False):
    type: str
    price: float
    quantity: float
    error: Optional[str]


EventCallback = Callable[[Dict[str, Any]], None]


class StrategyAdapter(Protocol):
    """Protocol for strategy adapters used by the simulator.

    Implementations MUST NOT perform live network I/O during simulation.
    """

    def start(self) -> bool: ...
    def stop(self) -> bool: ...
    def on_market_update(self, bar_or_tick: Dict[str, Any]) -> None: ...
    def inject_historical_data(self, data: Any) -> None: ...
    def get_state(self) -> Dict[str, Any]: ...
    def set_event_callback(self, cb: EventCallback) -> None: ...
