from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from engine_backend.core.engine_settings_store import (
    get_engine_settings,
    upsert_engine_settings,
    list_engine_settings,
)
import logging
import uuid
import time
import asyncio
from engine_backend.core import order_store
from engine_backend.core.order_executor import execute_order_sync
from engine_backend.core import trade_history_store
 

logger = logging.getLogger(__name__)
router = APIRouter()


class OrderRequest(BaseModel):
    engine: str
    symbol: str
    side: str
    type: str
    quantity: float
    price: Optional[float] = None
    reduceOnly: Optional[bool] = False
    idempotency_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# Simple in-memory store for skeleton (replace with DB in real implementation)
_ORDERS: Dict[str, Dict[str, Any]] = {}


class TradeHistoryRecord(BaseModel):
    engine_name: str
    symbol: str
    trade_datetime: str
    funds: float
    leverage: int
    profit_loss: float
    pnl_percent: float
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    position_side: Optional[str] = None


@router.post("/orders")
async def create_order(req: OrderRequest):
    """Accept internal order requests (final validation + execution).
    This is a skeleton: real implementation must persist to DB and enqueue for execution.
    """
    order_id = str(uuid.uuid4())
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    order = {
        "id": order_id,
        "engine": req.engine,
        "symbol": req.symbol,
        "side": req.side,
        "type": req.type,
        "quantity": req.quantity,
        "price": req.price,
        "reduceOnly": req.reduceOnly,
        "status": "PENDING",
        "created_at_utc": now,
        "updated_at_utc": now,
        "raw_response": None,
    }

    # persist synchronously in thread to avoid blocking
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, order_store.persist_order, order)
    logger.info(f"[ENGINE_BACKEND] Persisted order {order_id} for {req.symbol}")

    # schedule background execution
    async def _bg_execute(oid: str):
        await loop.run_in_executor(None, execute_order_sync, oid, None)

    asyncio.create_task(_bg_execute(order_id))

    return {"order_id": order_id, "status": "accepted"}


@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    order = _ORDERS.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/trade-history")
async def api_create_trade_history(record: TradeHistoryRecord):
    """Internal endpoint to persist a trade history record in engine DB.

    This is intended to be called only from trusted internal services
    (e.g., the main backend's EngineManager) to keep the engine backend's
    SQLite DB in sync with global trade history.
    """

    loop = asyncio.get_event_loop()

    def _persist() -> None:
        trade_history_store.insert_trade_record(
            engine_name=record.engine_name,
            symbol=record.symbol,
            trade_datetime=record.trade_datetime,
            funds=record.funds,
            leverage=record.leverage,
            profit_loss=record.profit_loss,
            pnl_percent=record.pnl_percent,
            entry_price=record.entry_price,
            exit_price=record.exit_price,
            position_side=record.position_side,
        )

    await loop.run_in_executor(None, _persist)
    return {"status": "ok"}


@router.delete("/trade-history")
async def api_delete_all_trade_history():
    """Delete all trade history records from the engine backend DB.

    This will typically be invoked by the main backend's admin/maintenance
    endpoint when the user requests a full history wipe from the GUI.
    """

    loop = asyncio.get_event_loop()

    def _delete() -> None:
        trade_history_store.delete_all_trade_history()

    await loop.run_in_executor(None, _delete)
    return {"status": "deleted"}


@router.delete("/trade-history/{engine_name}")
async def api_delete_trade_history_for_engine(engine_name: str):
    """Delete trade history records only for a specific engine.

    This is used by the main backend when the user requests
    per-engine history deletion from the GUI (Alpha/Beta/Gamma).
    """

    loop = asyncio.get_event_loop()

    def _delete_engine() -> None:
        trade_history_store.delete_trade_history_for_engine(engine_name)

    await loop.run_in_executor(None, _delete_engine)
    return {"status": "deleted", "engine": engine_name}

@router.get("/engine/settings")
async def api_list_engine_settings():
    return {"items": list_engine_settings()}

@router.get("/engine/settings/{engine_name}")
async def api_get_engine_settings(engine_name: str):
    settings = get_engine_settings(engine_name)
    if not settings:
        raise HTTPException(status_code=404, detail="Engine settings not found")
    return settings

@router.put("/engine/settings/{engine_name}")
async def api_update_engine_settings(
    engine_name: str,
    enabled: bool | None = None,
    max_position_usdt: float | None = None,
    max_leverage: int | None = None,
    cooldown_sec: float | None = None,
    note: str | None = None,
):
    upsert_engine_settings(
        engine_name=engine_name,
        enabled=enabled,
        max_position_usdt=max_position_usdt,
        max_leverage=max_leverage,
        cooldown_sec=cooldown_sec,
        note=note,
    )
    return get_engine_settings(engine_name) or {"engine_name": engine_name}


# Note: internal health/readiness endpoints were intentionally removed from this
# router to avoid duplication with the root-level health endpoints exposed by
# the application entrypoint. Health and readiness are now served at `/health`
# and `/ready` in `engine_backend/app_main.py`.
