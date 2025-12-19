from typing import Dict, Any


def to_order_dict(symbol: str, side: str, price: float, quantity: float) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "side": side,
        "price": price,
        "quantity": quantity,
    }


def simulate_fill(order: Dict[str, Any], broker) -> Dict[str, Any]:
    # Uses broker.place_order interface if available
    if hasattr(broker, "place_order"):
        return broker.place_order(symbol=order.get("symbol"), side=order.get("side"), price=order.get("price"), quantity=order.get("quantity"))
    # fallback: return a fill dict
    return {"id": "sim-1", "symbol": order.get("symbol"), "filled_price": order.get("price"), "quantity": order.get("quantity")}
