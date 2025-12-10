from typing import Any, Dict, Optional, Callable

from .adapter import StrategyAdapter, EventCallback


class OrchestratorAdapter:
    """Thin adapter that bridges the live StrategyOrchestrator to the StrategyAdapter API.

    This adapter expects a broker client that is a simulator (no network I/O).
    """

    def __init__(self, config: Any, broker_client: Optional[Any] = None):
        self._config = config
        self._broker = broker_client
        self._orch = None
        self._event_cb: Optional[EventCallback] = None

        # Lazy import to avoid import-time side effects
        try:
            from backend.core.new_strategy import StrategyOrchestrator

            # instantiate orchestrator lazily when start() called
            self._orch_class = StrategyOrchestrator
        except Exception:
            self._orch_class = None

    def _ensure_orch(self):
        if self._orch is None and self._orch_class is not None:
            self._orch = self._orch_class(binance_client=self._broker, config=self._config, auto_prepare_symbol=False)
            try:
                self._orch.set_event_callback(self._on_orch_event)
            except Exception:
                pass

    def _on_orch_event(self, result: Dict[str, Any]):
        if self._event_cb:
            try:
                self._event_cb(result)
            except Exception:
                pass

    def start(self) -> bool:
        self._ensure_orch()
        if self._orch is None:
            # orchestrator unavailable — act as no-op
            return False
        try:
            self._orch.start()
            return True
        except Exception:
            return False

    def stop(self) -> bool:
        if self._orch is None:
            return False
        try:
            self._orch.stop()
            return True
        except Exception:
            return False

    def on_market_update(self, bar_or_tick: Dict[str, Any]) -> None:
        # Best-effort: if orchestrator exposes a market-data ingestion method, call it
        if self._orch is None:
            return
        if hasattr(self._orch, "on_market_data"):
            try:
                self._orch.on_market_data(bar_or_tick)
            except Exception:
                pass

    def inject_historical_data(self, data: Any) -> None:
        # Orchestrator-specific data injection not guaranteed — rely on BrokerSimulator
        return

    def get_state(self) -> Dict[str, Any]:
        if self._orch is None:
            return {}
        try:
            return self._orch.get_status()
        except Exception:
            return {}

    def set_event_callback(self, cb: EventCallback) -> None:
        self._event_cb = cb
