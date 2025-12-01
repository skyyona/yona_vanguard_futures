import json
import datetime
import pytest
import httpx


def to_ms(dt_str: str) -> int:
    dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    return int((dt.astimezone(datetime.timezone.utc) - epoch).total_seconds() * 1000)


@pytest.mark.integration
def test_run_backtest_endpoint(tmp_path):
    """Integration test: POST to backtesting backend run_backtest endpoint.

    This test will be skipped if the backtesting backend is not running on
    `127.0.0.1:8001` to avoid failing collection or CI unexpectedly.
    """
    body = {
        "strategy_name": "default",
        "symbol": "BTCUSDT",
        "interval": "1h",
        "start_time": to_ms("2025-01-01T00:00:00Z"),
        "end_time": to_ms("2025-01-10T00:00:00Z"),
        "initial_balance": 100.0,
        "leverage": 1,
    }

    url = "http://127.0.0.1:8001/backtest/run_backtest"

    try:
        r = httpx.post(url, json=body, timeout=300.0)
    except httpx.ConnectError:
        pytest.skip("backtesting backend not available on 127.0.0.1:8001")

    # Save response for local inspection
    out_file = tmp_path / "last_run_response.json"
    out_file.write_text(r.text, encoding="utf-8")

    assert r.status_code == 200, f"Backtest endpoint returned {r.status_code}: {r.text}"
