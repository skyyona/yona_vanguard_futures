"""Order executor implementation that calls BinanceClient and updates DB."""
from typing import Dict, Any
import logging
import backend.api_client.binance_client as bc_mod
from engine_backend.core.order_store import get_order, update_order

logger = logging.getLogger(__name__)


def execute_order_sync(order_id: str, db_path: str = None) -> Dict[str, Any]:
    """Synchronous execution helper. Intended to be run in a thread executor.

    Steps:
    - load order from DB
    - perform necessary checks (omitted here for brevity)
    - call BinanceClient to create order
    - update order status and raw_response
    """
    order = get_order(order_id, db_path=db_path)
    if not order:
        logger.error(f"Order {order_id} not found")
        return {"ok": False, "error": "order not found"}

    binance = bc_mod.BinanceClient()

    # for now, only implement MARKET orders
    try:
        side = order.get("side")
        symbol = order.get("symbol")
        qty = float(order.get("quantity") or 0)

        logger.info(f"[order_executor] submitting market order {order_id} -> {symbol} {side} {qty}")
        res = binance.create_market_order(symbol, side, qty)

        if isinstance(res, dict) and "error" in res:
            update_order(order_id, {"status": "FAILED", "raw_response": str(res)}, db_path=db_path)
            return {"ok": False, "error": res}

        # success
        exchange_id = res.get("orderId") or res.get("clientOrderId") or res.get("order_id") or res.get("exchange_order_id")
        update_order(order_id, {"status": "FILLED", "exchange_order_id": exchange_id, "raw_response": str(res)}, db_path=db_path)
        return {"ok": True, "exchange_order_id": exchange_id, "result": res}

    except Exception as e:
        logger.exception(f"Exception while executing order {order_id}: {e}")
        update_order(order_id, {"status": "FAILED", "raw_response": str(e)}, db_path=db_path)
        return {"ok": False, "error": str(e)}
