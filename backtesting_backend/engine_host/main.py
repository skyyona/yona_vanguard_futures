"""Engine Host scaffold used for local integration and testing.

Provides simple in-memory engine control and order recording endpoints so
the Live Backend can proxy calls during integration testing. This file is
intended as a temporary scaffold and should be replaced by the real Engine
Host implementation when ready.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import os

# Align logging and dotenv loading with backtesting_backend core utilities
from backtesting_backend.core.logger import configure_logging

configure_logging()

app = FastAPI(title="YONA Engine Host (scaffold)", version="0.1")

# Use a child logger so formatting/handlers from core logger are inherited
logger = logging.getLogger("backtest.engine_host")

# Runtime state (in-memory for scaffold)
app.state.engines = {}
app.state.orders = []

# Environment-driven defaults (dotenv already loaded by configure_logging)
DEFAULT_DRY_RUN = os.getenv("ENGINE_HOST_DEFAULT_DRY_RUN", os.getenv("DEFAULT_DRY_RUN", "1")) in ("1", "true", "True")


class EngineControlRequest(BaseModel):
    engine: str
    symbol: Optional[str] = None
    dry_run: Optional[bool] = None


class OrderRequest(BaseModel):
    engine: str
    symbol: str
    side: str  # "BUY" | "SELL"
    quantity: float
    price: Optional[float] = None
    dry_run: Optional[bool] = None


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Liveness endpoint"""
    return {"status": "ok", "engine_host": True, "default_dry_run": DEFAULT_DRY_RUN}


@app.post("/engine/start")
async def start_engine(req: EngineControlRequest):
    dry = DEFAULT_DRY_RUN if req.dry_run is None else bool(req.dry_run)
    name = req.engine
    state = app.state.engines.get(name, {})
    if state.get("running"):
        return {"success": False, "error": "already_running"}

    app.state.engines[name] = {"running": True, "symbol": req.symbol, "dry_run": dry}
    logger.info(f"Engine host: started engine {name} (symbol={req.symbol}, dry_run={dry})")
    return {"success": True, "engine": name, "dry_run": dry}


@app.post("/engine/stop")
async def stop_engine(req: EngineControlRequest):
    name = req.engine
    state = app.state.engines.get(name)
    if not state or not state.get("running"):
        return {"success": False, "error": "not_running"}
    state["running"] = False
    logger.info(f"Engine host: stopped engine {name}")
    return {"success": True, "engine": name}


@app.post("/orders")
async def create_order(req: OrderRequest):
    engine_state = app.state.engines.get(req.engine)
    if engine_state is None or not engine_state.get("running"):
        raise HTTPException(status_code=400, detail="engine_not_running")

    dry = engine_state.get("dry_run", DEFAULT_DRY_RUN) if req.dry_run is None else bool(req.dry_run)

    order = {
        "engine": req.engine,
        "symbol": req.symbol,
        "side": req.side,
        "quantity": req.quantity,
        "price": req.price,
        "dry_run": dry,
        "status": "accepted" if dry else "submitted",
    }

    app.state.orders.append(order)
    logger.info(f"Engine host: order received (engine={req.engine}, symbol={req.symbol}, dry_run={dry})")
    return {"success": True, "order": order}


@app.get("/orders")
async def list_orders():
    return {"success": True, "orders": list(app.state.orders)}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("ENGINE_HOST_PORT", os.getenv("FASTAPI_PORT", "8203")))
    logger.info("Starting Engine Host (scaffold) on %s:%s", host, port)
    uvicorn.run("backtesting_backend.engine_host.main:app", host=host, port=port, reload=False)


def create_app() -> FastAPI:
    """Factory-compatible entry point returning the ASGI `app`.

    Keeps parity with `backtesting_backend.app_main.create_app` so callers
    can import and construct the app reliably.
    """
    return app
