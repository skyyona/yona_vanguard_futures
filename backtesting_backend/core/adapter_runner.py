from typing import Any, Dict, List, Optional
import json
import time

from backtesting_backend.app.services.strategies.adapter import StrategyAdapter
from backtesting_backend.app.services.adapters.broker_simulator import BrokerSimulator


class AdapterRunner:
    """Lightweight adapter-driven runner for quick backtests.

    This is the previous lightweight implementation extracted into its own module.
    It exposes `run_once(strategy, symbol, start, end, config)` for compatibility.
    """

    def __init__(self, broker: Optional[BrokerSimulator] = None):
        self.broker = broker or BrokerSimulator()

    def run_once(self, strategy: str, symbol: str, start: str, end: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        # Create adapter per strategy name (only alpha implemented via factory)
        if strategy.lower() == "alpha":
            from backtesting_backend.app.services.strategies.alpha_strategy_adapter import make_alpha_adapter

            adapter: StrategyAdapter = make_alpha_adapter(symbol=symbol, broker_client=self.broker)
        else:
            from backtesting_backend.app.services.strategies.alpha_strategy_adapter import make_alpha_adapter

            adapter: StrategyAdapter = make_alpha_adapter(symbol=symbol, broker_client=self.broker)

        # attach event callback to capture orchestrator events
        events: List[Dict[str, Any]] = []

        def _cb(res: Dict[str, Any]):
            events.append(res)

        adapter.set_event_callback(_cb)

        # start adapter
        adapter.start()

        # for demo purposes, load fixture file named by symbol or short_bars.json
        try:
            with open("backtesting_backend/tests/fixtures/short_bars.json", "r", encoding="utf-8") as f:
                bars = json.load(f)
        except Exception:
            bars = []

        # replay bars
        for bar in bars:
            adapter.on_market_update(bar)
            time.sleep(0)

        # stop adapter
        adapter.stop()

        # return summary
        return {
            "strategy": strategy,
            "symbol": symbol,
            "events_count": len(events),
            "events": events[:20],
        }


if __name__ == "__main__":
    runner = AdapterRunner()
    out = runner.run_once(strategy="alpha", symbol="BTCUSDT", start="2025-01-01", end="2025-01-02")
    print(json.dumps(out, indent=2))
