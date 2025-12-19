"""Simple trading loop for Engine Backend.

Reads strategy configurations from the local strategies table and, if trading is
enabled, submits market orders to Binance via the existing order store and
executor.

Expected parameter keys in strategies.parameters for auto-trading:

- auto_trade_enabled: bool (must be True to allow trading)
- direction: "LONG" or "SHORT" (determines BUY vs SELL)
- target_notional_usdt: float (desired position notional in USDT)
- leverage: int (desired leverage)

If these fields are missing or invalid, the loop will log and skip that
strategy without placing any orders.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Any, Optional, Tuple

from backend.utils.config_loader import BINANCE_USE_TESTNET
from backend.api_client.binance_client import BinanceClient
from engine_backend.core.strategy_store import list_all_strategies
from engine_backend.core.engine_settings_store import list_engine_settings
from engine_backend.core.order_store import persist_order
from engine_backend.core.order_executor import execute_order_sync


logger = logging.getLogger(__name__)


def _build_order_from_strategy(
    cfg: Dict[str, Any],
    price: float,
    max_position_limit_usdt: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Given a strategy config row and current price, build an order dict.

    Returns None if required fields are missing or invalid.
    """

    symbol = cfg.get("symbol")
    engine_name = cfg.get("engine_name")
    params = cfg.get("parameters") or {}

    if not symbol or not engine_name:
        logger.warning("strategy row missing symbol/engine_name: %s", cfg)
        return None

    if not params.get("auto_trade_enabled"):
        # explicit opt-in required
        logger.debug("auto_trade_disabled for %s, skipping", symbol)
        return None

    direction = str(params.get("direction", "")).upper()
    if direction not in ("LONG", "SHORT"):
        logger.warning("strategy for %s has no valid direction (LONG/SHORT), skipping", symbol)
        return None

    try:
        target_notional = float(params.get("target_notional_usdt", 0.0))
    except Exception:
        target_notional = 0.0

    if target_notional <= 0:
        logger.warning("strategy for %s has no positive target_notional_usdt, skipping", symbol)
        return None

    # Enforce per-engine max position size only if the user explicitly configured it
    if max_position_limit_usdt is not None:
        try:
            limit = float(max_position_limit_usdt)
            if limit > 0:
                target_notional = min(target_notional, limit)
        except Exception:
            # If the per-engine limit is invalid, ignore it and proceed with the strategy value
            pass

    if price <= 0:
        logger.warning("invalid price for %s: %s", symbol, price)
        return None

    qty = target_notional / float(price)
    if qty <= 0:
        logger.warning("computed quantity <= 0 for %s (notional=%s, price=%s)", symbol, target_notional, price)
        return None

    side = "BUY" if direction == "LONG" else "SELL"

    order = {
        "engine": engine_name,
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": qty,
        "price": None,
        "reduceOnly": False,
        "status": "PENDING",
    }
    return order


def _maybe_set_leverage(binance: BinanceClient, symbol: str, leverage: int) -> None:
    try:
        if leverage <= 0:
            return
        # Use the leverage specified by the strategy as-is; no global clamp
        binance.set_leverage(symbol, leverage)
    except Exception as e:
        logger.warning("failed to set leverage for %s: %s", symbol, e)


def run_trading_loop(poll_interval_sec: int = 30, stop_event: Optional[threading.Event] = None) -> None:
    """Main trading loop.

    Periodically reads all strategies from the local DB.
    For each strategy with auto_trade_enabled=True, builds a MARKET order
    based on target_notional_usdt and direction. Always persists the order
    and executes it via the existing order executor.
    """

    # Always operate in LIVE mode; DRY_RUN is not used in this application.
    mode = "LIVE"
    env = "TESTNET" if BINANCE_USE_TESTNET else "MAINNET"
    logger.info("Starting trading loop (mode=%s, env=%s)", mode, env)

    binance = BinanceClient()
    last_order_ts: Dict[Tuple[str, str], float] = {}
    default_cooldown_sec = 60.0

    while True:
        try:
            if stop_event is not None and stop_event.is_set():
                logger.info("Trading loop stop_event set; exiting loop")
                break

            strategies = list_all_strategies()
            settings_list = list_engine_settings()
            settings_by_engine: Dict[str, Dict[str, Any]] = {s["engine_name"]: s for s in settings_list}
            now = time.time()

            for cfg in strategies:
                symbol = cfg.get("symbol")
                engine_name = cfg.get("engine_name")
                if not symbol or not engine_name:
                    continue

                settings = settings_by_engine.get(engine_name)
                # If settings exist and engine is disabled, skip
                if settings is not None and not bool(settings.get("enabled", True)):
                    logger.debug("engine %s disabled by settings; skipping %s", engine_name, symbol)
                    continue

                # Per-engine overrides
                max_pos_limit = None
                if settings is not None:
                    try:
                        max_pos_limit = (
                            float(settings.get("max_position_usdt"))
                            if settings.get("max_position_usdt") is not None
                            else None
                        )
                    except Exception:
                        max_pos_limit = None

                engine_cooldown = default_cooldown_sec
                if settings is not None and settings.get("cooldown_sec") is not None:
                    try:
                        engine_cooldown = float(settings.get("cooldown_sec")) or default_cooldown_sec
                    except Exception:
                        engine_cooldown = default_cooldown_sec

                key = (engine_name, symbol)
                last_ts = last_order_ts.get(key, 0.0)
                if now - last_ts < engine_cooldown:
                    # avoid spamming orders; one opportunity per cooldown window
                    continue

                try:
                    mp = binance.get_mark_price(symbol)
                    price = float(mp.get("markPrice", 0)) if isinstance(mp, dict) else 0.0
                except Exception as e:
                    logger.warning("failed to fetch mark price for %s: %s", symbol, e)
                    continue

                order = _build_order_from_strategy(cfg, price, max_position_limit_usdt=max_pos_limit)
                if not order:
                    continue

                params = cfg.get("parameters") or {}
                lev = 0
                try:
                    lev = int(params.get("leverage", 0) or 0)
                except Exception:
                    lev = 0

                # Apply per-engine leverage override if configured
                settings_max_lev = None
                if settings is not None and settings.get("max_leverage") is not None:
                    try:
                        settings_max_lev = int(settings.get("max_leverage"))
                    except Exception:
                        settings_max_lev = None
                if settings_max_lev is not None and settings_max_lev > 0:
                    lev = min(lev, settings_max_lev)

                # Always persist and execute orders in LIVE mode
                _maybe_set_leverage(binance, symbol, lev)
                oid = persist_order(order)
                logger.info(
                    "[trading_loop] submitted order candidate %s -> %s %s qty=%s (engine=%s)",
                    oid,
                    order["symbol"],
                    order["side"],
                    order["quantity"],
                    order["engine"],
                )
                res = execute_order_sync(oid)
                logger.info("[trading_loop] execution result for %s: %s", oid, res)

                last_order_ts[key] = now

            time.sleep(poll_interval_sec)
        except Exception as loop_ex:
            logger.exception("trading loop iteration error: %s", loop_ex)
            time.sleep(poll_interval_sec)
