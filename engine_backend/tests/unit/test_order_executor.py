import pytest
import os
import tempfile

from engine_backend.core.order_store import persist_order, get_order, update_order
from engine_backend.core.order_executor import execute_order_sync


class DummyBinance:
    def create_market_order(self, symbol, side, quantity):
        return {"orderId": 9999, "status": "FILLED", "executedQty": str(quantity)}


def test_execute_order_integration(monkeypatch, tmp_path):
    # Setup DB in temporary file
    db_file = str(tmp_path / "test_orders.db")
    os.environ["ENGINE_BACKEND_DB_PATH"] = db_file

    # create DB
    from engine_backend.db.manager import init_db
    init_db(db_file)

    order = {
        "engine": "TestEngine",
        "symbol": "TESTUSDT",
        "side": "BUY",
        "type": "MARKET",
        "quantity": 1.0,
        "status": "PENDING",
    }
    oid = persist_order(order, db_path=db_file)

    # monkeypatch BinanceClient inside executor
    from backend.api_client import binance_client as bc_mod

    monkeypatch.setattr(bc_mod, "BinanceClient", lambda *args, **kwargs: DummyBinance())

    # execute order
    res = execute_order_sync(oid, db_path=db_file)
    assert res.get("ok") is True
    # verify DB updated
    rec = get_order(oid, db_path=db_file)
    assert rec is not None
    assert rec.get("status") == "FILLED"
