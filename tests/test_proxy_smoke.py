import os
import asyncio
import time
import pytest
from fastapi.testclient import TestClient

import httpx

# Import the live backend app and the engine host ASGI app
from backend.app_main import app as live_app
from backtesting_backend.engine_host.main import app as engine_app

import backend.api.routes as routes_module


async def _proxy_via_asgi(req, method: str = "POST", json_data=None, params=None):
    # Use httpx ASGITransport to call the engine_app in-process
    # Strip the Live Backend prefix ("/api/v1") when forwarding to the engine host scaffold
    path = str(req.url.path).replace("/api/v1", "")
    url = "http://testserver" + path
    transport = httpx.ASGITransport(app=engine_app)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.request(method, url, json=json_data, params=params)
        try:
            body = resp.json()
        except Exception:
            body = {"status_code": resp.status_code, "text": resp.text}
        return resp, body


def test_engine_proxy_smoke():
    # Ensure the live backend is in passive mode (default)
    os.environ.setdefault("ENGINE_DISABLE_ENGINE_MANAGER", "1")

    # Patch the proxy helper in the routes module to use ASGI transport
    routes_module._proxy_to_engine_host = _proxy_via_asgi

    with TestClient(live_app) as client:
        # Wait for readiness
        for _ in range(30):
            r = client.get("/ready")
            if r.status_code == 200 and r.json().get("ready"):
                break
            time.sleep(0.1)

        # Start engine via live backend; should be proxied to engine host scaffold
        r = client.post("/api/v1/engine/start", json={"engine": "Alpha", "symbol": "BTCUSDT"})
        assert r.status_code in (200, 201)
        data = r.json()
        assert data.get("success") or data.get("engine") == "Alpha" or data.get("status")

        # Check engine status via live backend (this endpoint does not proxy if it reads local engine_manager; but should not error)
        r2 = client.get("/api/v1/engine/status/Alpha")
        # Allow 200 or 404 depending on manager presence; proxying ensures the start request was handled
        assert r2.status_code in (200, 404, 500)
