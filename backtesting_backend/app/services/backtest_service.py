from typing import Any, Dict, Optional


class BacktestService:
    """Top-level backtest orchestration service.

    Coordinates data loading, simulator, strategy adapters, and ML inference.
    This is intentionally minimal and uses lazy imports to avoid heavy dependencies.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def run_backtest(self, strategy: str, symbol: str, start: str, end: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
        # Lazy import core simulator to keep startup light
        from backtesting_backend.core.strategy_simulator import StrategySimulator

        sim = StrategySimulator()
        return sim.run_once(strategy=strategy, symbol=symbol, start=start, end=end, config=config or {})
