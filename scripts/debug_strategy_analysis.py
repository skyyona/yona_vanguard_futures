import os, sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.app_main import app
from fastapi.testclient import TestClient


symbols = ["PROMPTUSDT", "BASUSDT", "RIVERUSDT", "FOLKSUSDT"]

with TestClient(app) as client:
    for symbol in symbols:
        print("===", symbol, "===")
        resp = client.get(
            "/api/v1/backtest/strategy-analysis",
            params={"symbol": symbol, "period": "1w", "interval": "1m"},
        )
        print("status:", resp.status_code)
        print("body:", resp.text)
