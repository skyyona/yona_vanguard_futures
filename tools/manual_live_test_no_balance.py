"""One-shot live trading test for a single strategy.

This script:
- loads the BTCUSDT/alpha strategy from the engine DB
- fetches current mark price from Binance
- builds the MARKET order using the same helpers as trading_loop
- sets leverage via BinanceClient
- persists the order and executes it once

It is intended for accounts with no or very small balance, to verify that
leverage/position sizing logic works and that Binance rejects the order
(e.g. insufficient margin) instead of executing it.
"""

from __future__ import annotations

import json
import logging

from backend.api_client.binance_client import BinanceClient
from engine_backend.db.manager import init_db
from engine_backend.core.strategy_store import list_all_strategies
from engine_backend.core.trading_loop import _build_order_from_strategy, _maybe_set_leverage
from engine_backend.core.order_store import persist_order
from engine_backend.core.order_executor import execute_order_sync

logger = logging.getLogger(__name__)


def main() -> None:
    # Ensure DB is initialized
    init_db()

    strategies = list_all_strategies()
    if not strategies:
        print("No strategies found in DB; nothing to test.")
        return

    # Pick BTCUSDT/alpha if present; otherwise just take the first auto_trade_enabled strategy
    cfg = None
    for s in strategies:
        if s.get("symbol") == "BTCUSDT" and s.get("engine_name") == "alpha":
            cfg = s
            break
    if cfg is None:
        for s in strategies:
            params = s.get("parameters") or {}
            if params.get("auto_trade_enabled"):
                cfg = s
                break

    if cfg is None:
        print("No auto_trade_enabled strategy found; nothing to test.")
        return

    symbol = cfg.get("symbol")
    engine_name = cfg.get("engine_name")
    params = cfg.get("parameters") or {}

    print("Selected strategy:")
    print(json.dumps({
        "symbol": symbol,
        "engine_name": engine_name,
        "parameters": params,
    }, indent=2, ensure_ascii=False))

    binance = BinanceClient()

    # Fetch current mark price
    mp = binance.get_mark_price(symbol)
    price = float(mp.get("markPrice", 0)) if isinstance(mp, dict) else 0.0
    print(f"Current mark price for {symbol}: {price}")

    # Override target_notional_usdt so that quantity is above Binance minQty
    # user intent: slightly larger (e.g. 30~50 USDT), but also guaranteed
    # to exceed minQty based on current price.
    orig_notional = float(params.get("target_notional_usdt", 0) or 0)
    # assume minQty ~= 0.001 BTC and add a small safety factor
    min_notional_for_minqty = price * 0.0012
    override_notional = max(orig_notional, 50.0, min_notional_for_minqty)

    params_overridden = dict(params)
    params_overridden["target_notional_usdt"] = override_notional
    cfg_overridden = dict(cfg)
    cfg_overridden["parameters"] = params_overridden

    print(f"Overriding target_notional_usdt from {orig_notional} to {override_notional}")

    order = _build_order_from_strategy(cfg_overridden, price, max_position_limit_usdt=None)
    if not order:
        print("_build_order_from_strategy returned None (strategy invalid for trading).")
        return

    # Determine leverage from strategy parameters
    lev = 0
    try:
        lev = int(params.get("leverage", 0) or 0)
    except Exception:
        lev = 0

    print(f"Applying leverage: {lev}")
    _maybe_set_leverage(binance, symbol, lev)

    # Persist and execute the order once
    oid = persist_order(order)
    print(f"Persisted order id: {oid}")
    print("Order payload:")
    print(json.dumps(order, indent=2, ensure_ascii=False))

    print("Executing order via Binance...")
    res = execute_order_sync(oid)
    print("Execution result:")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
