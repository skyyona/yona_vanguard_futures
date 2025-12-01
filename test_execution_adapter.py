"""ExecutionAdapter 단위 테스트 (Mock BinanceClient)"""
import time
from typing import Dict, Any

from backend.core.new_strategy.execution_adapter import ExecutionAdapter, ExecutionRetryPolicy
from backend.core.new_strategy.data_structures import OrderResult


class FakeBinanceClient:
    def __init__(self):
        self._attempts_order = 0
        self._attempts_close = 0
        self._leverage_set = None
        self._margin_set = None

    # Publics used by adapter
    def get_mark_price(self, symbol: str) -> Dict[str, Any]:
        return {"markPrice": "50000.0"}

    def _round_qty_by_filters(self, symbol: str, raw_qty: float, price_hint: float = None) -> Dict[str, Any]:
        # Allow min notional 5 USDT, step 0.001, minQty 0.001
        # For simplicity, accept and echo qty
        if raw_qty * (price_hint or 50000.0) < 5.0:
            return {"ok": False, "reason": "Notional below minNotional"}
        return {"ok": True, "qty": float(f"{raw_qty:.3f}")}

    def set_margin_type(self, symbol: str, isolated: bool = True) -> Dict[str, Any]:
        self._margin_set = (symbol, isolated)
        return {"symbol": symbol, "marginType": "ISOLATED" if isolated else "CROSSED"}

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        self._leverage_set = (symbol, leverage)
        return {"symbol": symbol, "leverage": leverage}

    def create_market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        # Fail first attempt, then succeed
        self._attempts_order += 1
        if self._attempts_order == 1:
            return {"error": "temporary error", "code": -1}
        return {
            "orderId": 12345,
            "symbol": symbol,
            "status": "FILLED",
            "avgPrice": "50010.0",
            "executedQty": f"{quantity:.3f}",
            "fills": [
                {"price": "50010.0", "qty": f"{quantity:.3f}", "commission": "0.05", "commissionAsset": "USDT"}
            ]
        }

    def close_position_market(self, symbol: str, side: str = None) -> Dict[str, Any]:
        # Fail first attempt, then succeed
        self._attempts_close += 1
        if self._attempts_close == 1:
            return {"error": "temporary error", "code": -1}
        return {
            "orderId": 67890,
            "symbol": symbol,
            "status": "FILLED",
            "avgPrice": "49990.0",
            "executedQty": "0.010",
        }


def test_prepare_and_place_and_close():
    client = FakeBinanceClient()
    adapter = ExecutionAdapter(client, retry=ExecutionRetryPolicy(max_attempts=3, base_backoff_sec=0.01))

    # prepare
    ok = adapter.prepare_symbol("BTCUSDT", leverage=50, isolated=True)
    assert ok is True
    assert client._leverage_set == ("BTCUSDT", 50)
    assert client._margin_set == ("BTCUSDT", True)

    # quantity normalization should pass (0.001 * 50000 = 50 >= 5)
    norm = adapter.normalize_quantity("BTCUSDT", 0.001)
    assert norm.get("ok")
    assert abs(norm.get("qty") - 0.001) < 1e-9

    # place market long (first attempt fails, second succeeds)
    result: OrderResult = adapter.place_market_long("BTCUSDT", 0.001)
    print("Place Result:", result)
    assert result.ok is True
    assert result.order_id == 12345
    assert result.side == "BUY"
    assert result.executed_qty is not None
    assert result.avg_price is not None

    # close market long (first attempt fails, second succeeds)
    close_result: OrderResult = adapter.close_market_long("BTCUSDT")
    print("Close Result:", close_result)
    assert close_result.ok is True
    assert close_result.order_id == 67890
    assert close_result.side == "SELL"


if __name__ == "__main__":
    print("ExecutionAdapter 테스트 실행")
    test_prepare_and_place_and_close()
    print("✓ 테스트 통과")
