from fastapi import FastAPI
from engine_backend.api.routes import router as engine_router
from engine_backend.db.manager import init_db
from engine_backend.core.trading_loop import run_trading_loop
import asyncio
import threading
import logging

logger = logging.getLogger(__name__)


def create_app():
    app = FastAPI(title="Engine Backend (Order Executor)")
    app.include_router(engine_router, prefix="/internal/v1")

    @app.get("/health")
    async def root_health():
        return {"status": "ok"}

    @app.get("/ready")
    async def root_ready():
        try:
            from engine_backend.workers import consumer as consumer_mod
            ready = consumer_mod.is_ready()
            return {"ready": ready, "status": "ready" if ready else "not_ready"}
        except Exception as e:
            return {"ready": False, "status": "error", "error": str(e)}

    @app.on_event("startup")
    async def _startup():
        # Initialize DB synchronously in thread to avoid blocking event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, init_db)

        # Start Redis Streams consumer in background thread if broker enabled
        try:
            from backend.utils.config_loader import ENGINE_BROKER_ENABLED
            if ENGINE_BROKER_ENABLED:
                from engine_backend.workers import consumer as consumer_mod
                # stop_event stored on app.state for shutdown
                stop_event = threading.Event()
                app.state._consumer_stop_event = stop_event
                t = threading.Thread(
                    target=consumer_mod.run_consumer,
                    kwargs={"group_name": "engine_group", "consumer_name": None, "block_ms": 2000, "stop_event": stop_event},
                    daemon=True,
                )
                t.start()
                app.state._consumer_thread = t
                logger.info("Engine Backend consumer thread started via FastAPI startup event")
        except Exception:
            logger.exception("Failed to start engine consumer on startup")

        # Start trading loop in background thread (always runs, but respects LIVE_TRADING_ENABLED)
        try:
            stop_event = threading.Event()
            app.state._trading_stop_event = stop_event
            t_trade = threading.Thread(
                target=run_trading_loop,
                kwargs={"poll_interval_sec": 30, "stop_event": stop_event},
                daemon=True,
            )
            t_trade.start()
            app.state._trading_thread = t_trade
            logger.info("Engine Backend trading loop thread started via FastAPI startup event")
        except Exception:
            logger.exception("Failed to start trading loop on startup")

    @app.on_event("shutdown")
    async def _shutdown():
        # Signal consumer to stop and wait for thread to exit
        try:
            stop_event = getattr(app.state, "_consumer_stop_event", None)
            t = getattr(app.state, "_consumer_thread", None)
            if stop_event is not None:
                stop_event.set()
            if t is not None:
                t.join(timeout=5)
                logger.info("Engine Backend consumer thread stopped on shutdown")
        except Exception:
            logger.exception("Error while stopping consumer thread on shutdown")

        # Signal trading loop to stop
        try:
            t_stop = getattr(app.state, "_trading_stop_event", None)
            t_trade = getattr(app.state, "_trading_thread", None)
            if t_stop is not None:
                t_stop.set()
            if t_trade is not None:
                t_trade.join(timeout=5)
                logger.info("Engine Backend trading loop thread stopped on shutdown")
        except Exception:
            logger.exception("Error while stopping trading loop thread on shutdown")

    return app


app = create_app()
