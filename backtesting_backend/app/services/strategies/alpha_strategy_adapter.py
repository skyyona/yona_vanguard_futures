from typing import Optional, Dict, Any

from .orchestrator_adapter import OrchestratorAdapter


def make_alpha_adapter(symbol: str = "BTCUSDT", leverage: int = 50, order_quantity: float = 0.001, broker_client: Optional[Any] = None):
    """Factory for an Alpha strategy adapter configured for backtests."""
    # Lazy import OrchestratorConfig if available
    try:
        from backend.core.new_strategy import OrchestratorConfig

        config = OrchestratorConfig(symbol=symbol, leverage=leverage, order_quantity=order_quantity, enable_trading=True, loop_interval_sec=1.0)
    except Exception:
        # Fallback simple config dict
        config = {
            "symbol": symbol,
            "leverage": leverage,
            "order_quantity": order_quantity,
        }

    return OrchestratorAdapter(config=config, broker_client=broker_client)
