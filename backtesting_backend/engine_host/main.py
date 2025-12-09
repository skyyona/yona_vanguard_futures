"""Minimal engine_host.main shim used by tests when engine_host is missing.

This provides a small FastAPI app named `app` (and `engine_app`) so
tests that import `backtesting_backend.engine_host.main` succeed.
"""
from fastapi import FastAPI

app = FastAPI(title="Backtesting Engine Host (shim)")
engine_app = app


@app.get("/_ping")
def ping():
    """Health-check endpoint used by tests and CI."""
    return {"status": "ok"}


@app.on_event("startup")
async def _startup():
    # no-op startup hook for the shim
    return None


@app.on_event("shutdown")
async def _shutdown():
    # no-op shutdown hook for the shim
    return None
"""
Minimal Engine Host (Stage B scaffold)
- FastAPI app exposing health, engine control and order endpoints
- Default behaviour is dry-run (does not perform market writes)
- Intended for local testing and to be run on canonical port 8203
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import os

app = FastAPI(title="YONA Engine Host (scaffold)", version="0.1")

logger = logging.getLogger("engine_host")
logging.basicConfig(level=logging.INFO)

# Runtime state (in-memory for scaffold)
app.state.engines = {}
app.state.orders = []

# Environment-driven defaults
DEFAULT_DRY_RUN = os.getenv("ENGINE_HOST_DEFAULT_DRY_RUN", "1") in ("1", "true", "True")

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
    return {
        "status": "ok",
        "engine_host": True,
        "default_dry_run": DEFAULT_DRY_RUN,
    }

@app.post("/engine/start")
async def start_engine(req: EngineControlRequest):
    """Start a named engine. Default to dry-run unless explicitly disabled."""
    dry = DEFAULT_DRY_RUN if req.dry_run is None else bool(req.dry_run)
    name = req.engine
    state = app.state.engines.get(name, {})
    if state.get("running"):
        return {"success": False, "error": "already_running"}

    app.state.engines[name] = {
        "running": True,
        "symbol": req.symbol,
        "dry_run": dry,
    }
    logger.info(f"Engine host: started engine {name} (symbol={req.symbol}, dry_run={dry})")
    return {"success": True, "engine": name, "dry_run": dry}

@app.post("/engine/stop")
async def stop_engine(req: EngineControlRequest):
    """Stop a named engine."""
    name = req.engine
    state = app.state.engines.get(name)
    if not state or not state.get("running"):
        return {"success": False, "error": "not_running"}

    # Mark stopped
    state["running"] = False
    logger.info(f"Engine host: stopped engine {name}")
    return {"success": True, "engine": name}

@app.post("/orders")
async def create_order(req: OrderRequest):
    """Create an order. If dry-run, the request is recorded but not sent to exchange."""
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

    # Record the order in-memory for scaffold purposes
    app.state.orders.append(order)

    logger.info(f"Engine host: order received (engine={req.engine}, symbol={req.symbol}, dry_run={dry})")

    return {"success": True, "order": order}

@app.get("/orders")
async def list_orders():
    """List recorded orders (scaffold)."""
    return {"success": True, "orders": list(app.state.orders)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("ENGINE_HOST_PORT", "8203"))
    uvicorn.run("backtesting_backend.engine_host.main:app", host="0.0.0.0", port=port, reload=False)
