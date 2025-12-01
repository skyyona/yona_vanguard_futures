import httpx
import json
import datetime


def to_ms(dt_str):
    dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    return int((dt.astimezone(datetime.timezone.utc) - epoch).total_seconds() * 1000)

body = {
    "strategy_name": "default",
    "symbol": "BTCUSDT",
    "interval": "1h",
    "start_time": to_ms("2025-01-01T00:00:00Z"),
    "end_time": to_ms("2025-01-10T00:00:00Z"),
    "initial_balance": 100.0,
    "leverage": 1
}

url = "http://127.0.0.1:8001/backtest/run_backtest"
print("POST", url)
print("Request body:", json.dumps(body))

try:
    r = httpx.post(url, json=body, timeout=300.0)
    print("Status code:", r.status_code)
    print("Response text:", r.text)
    with open("backtesting_backend/last_run_response.json", "w", encoding="utf-8") as f:
        f.write(r.text)
    print("Saved response to backtesting_backend/last_run_response.json")
except Exception as e:
    print("Request failed:", e)
    raise
