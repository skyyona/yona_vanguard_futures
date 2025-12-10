from typing import Dict, Any, Iterable, List
import uuid


class BrokerSimulator:
    """Simple deterministic broker simulator for backtests.

    This simulator provides a minimal surface: place_order, cancel_order,
    get_account, and a replay helper for historical bars.
    """

    def __init__(self, starting_balance: float = 100000.0):
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._balance = starting_balance
        self._positions: List[Dict[str, Any]] = []
        # Optional whitelist of symbols the simulator understands. If None, all symbols are supported.
        self._supported_symbols = None

    def place_order(self, symbol: str, side: str, price: float, quantity: float) -> Dict[str, Any]:
        order_id = str(uuid.uuid4())
        fill = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "filled_price": price,
            "quantity": quantity,
        }
        self._orders[order_id] = fill
        # update position simplistically
        pos = {"symbol": symbol, "side": side, "entry_price": price, "quantity": quantity}
        self._positions.append(pos)
        return fill

    def cancel_order(self, order_id: str) -> bool:
        return self._orders.pop(order_id, None) is not None

    def get_account(self) -> Dict[str, Any]:
        return {"balance": self._balance}

    def replay_market_data(self, bars: Iterable[Dict[str, Any]]):
        """Yield bars for replay. Bars are dicts with at least timestamp and close."""
        for bar in bars:
            yield bar

    def get_positions(self) -> List[Dict[str, Any]]:
        return list(self._positions)

    def is_symbol_supported(self, symbol: str) -> bool:
        """Return True if the symbol is supported by this simulator.

        The orchestrator expects the broker client to expose `is_symbol_supported` during warmup.
        By default the simulator accepts all symbols unless a whitelist was provided via
        `self._supported_symbols`.
        """
        if self._supported_symbols is None:
            return True
        return symbol in self._supported_symbols
