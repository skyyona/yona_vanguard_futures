import os
import time
import subprocess
import tempfile
import threading
import sqlite3
import json
import importlib

import pytest


def start_redis_container(name: str = None):
    name = name or f"yona_test_redis_{int(time.time())}"
    # Pull and run redis container, map to host 6379
    cmd = ["docker", "run", "-d", "--name", name, "-p", "6379:6379", "redis:7"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to start redis container: {proc.stderr}")
    cid = proc.stdout.strip()
    return cid, name


def stop_redis_container(container_name_or_id: str):
    subprocess.run(["docker", "rm", "-f", container_name_or_id], capture_output=True)


@pytest.mark.integration
def test_redis_stream_publish_consume_end_to_end(tmp_path, monkeypatch):
    # Requires Docker available locally and python redis package installed.
    # Setup temporary DB path
    db_file = str(tmp_path / "engine_orders.db")
    os.environ["ENGINE_BACKEND_DB_PATH"] = db_file

    # Start Redis container
    cid, cname = start_redis_container()

    try:
        # Wait for Redis to be ready
        time.sleep(2)

        # Configure broker URL before importing modules
        os.environ["ENGINE_BROKER_URL"] = "redis://localhost:6379/0"
        os.environ["ENGINE_BROKER_STREAM"] = "test_orders_stream"
        os.environ["ENGINE_BROKER_ENABLED"] = "true"

        # Reload config and broker modules to pick up env changes
        import backend.utils.config_loader as cfg_mod
        importlib.reload(cfg_mod)
        import backend.utils.redis_broker as broker_mod
        importlib.reload(broker_mod)

        # Initialize DB
        import engine_backend.db.manager as dbman
        importlib.reload(dbman)
        dbman.init_db(db_file)

        # Monkeypatch BinanceClient used by executor to a dummy
        from backend.api_client import binance_client as bc_mod

        class DummyBinance:
            def create_market_order(self, symbol, side, quantity):
                return {"orderId": 12345, "status": "FILLED", "executedQty": str(quantity)}

        monkeypatch.setattr(bc_mod, "BinanceClient", lambda *args, **kwargs: DummyBinance())

        # Start consumer in background thread
        import engine_backend.workers.consumer as consumer_mod
        importlib.reload(consumer_mod)

        # start consumer with a stop event so we can shut it down cleanly
        stop_event = threading.Event()
        t = threading.Thread(target=consumer_mod.run_consumer, kwargs={"group_name": "test_group", "consumer_name": "test_consumer", "block_ms": 2000, "stop_event": stop_event}, daemon=True)
        t.start()

        # wait until consumer signals readiness
        ready = consumer_mod.wait_until_ready(timeout=10)
        assert ready, "Consumer failed to signal ready within timeout"

        # Publish an ORDER message to stream
        payload = {
            "type": "ORDER",
            "engine": "TestEngine",
            "symbol": "ITESTUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 0.5
        }
        xid = broker_mod.publish_to_stream(payload, stream=os.environ["ENGINE_BROKER_STREAM"])
        assert xid, "Publish to stream failed"

        # Wait up to 20s for consumer to process and DB to show FILLED order
        deadline = time.time() + 20
        found = False
        while time.time() < deadline:
            # Query sqlite DB directly
            conn = sqlite3.connect(db_file)
            cur = conn.cursor()
            cur.execute("SELECT id, symbol, status, raw_response FROM orders WHERE symbol = ?", ("ITESTUSDT",))
            rows = cur.fetchall()
            conn.close()
            if rows:
                for r in rows:
                    sid, sym, status, raw = r
                    if status == 'FILLED':
                        found = True
                        break
            if found:
                break
            time.sleep(1)

        assert found, "Order was not processed to FILLED state within timeout"

    finally:
        # Signal consumer to stop and wait for thread to exit
        try:
            stop_event.set()
            t.join(timeout=5)
        except Exception:
            pass
        # Cleanup container
        stop_redis_container(cid)
