import json
import sys

import requests

BASE = "http://127.0.0.1:8001/api/v1/backtest"


def _extract_base_params(data: dict, engine: str) -> dict:
    """Extract base parameters from strategy-analysis response.

    Supports both legacy engine_results shape and current best_parameters shape.
    """
    if not isinstance(data, dict):
        return {}

    # 1) Legacy shape: data.engine_results[engine].params
    engine_results = data.get("engine_results")
    if isinstance(engine_results, dict):
        alpha = engine_results.get(engine)
        if isinstance(alpha, dict):
            params = alpha.get("params") or {}
            if isinstance(params, dict):
                return params

    # 2) Current shape: data.best_parameters
    best_params = data.get("best_parameters") or {}
    if isinstance(best_params, dict):
        return best_params

    return {}


def main() -> int:
    symbol = "BTCUSDT"
    # Use a lighter interval/period for quicker analysis during tests
    interval = "5m"
    engine = "alpha"

    try:
        print(f"[assign_test] Calling strategy-analysis for {symbol} {interval} (period=1d, timeout=300s)...")
        r = requests.get(
            f"{BASE}/strategy-analysis",
            params={"symbol": symbol, "period": "1d", "interval": interval},
            timeout=300,
        )
        print("[assign_test] strategy-analysis status:", r.status_code)
        if r.status_code != 200:
            print(r.text)
            return 1
        data = r.json().get("data", {})
    except Exception as e:
        print("[assign_test] ERROR calling strategy-analysis:", e)
        return 1

    base_params = _extract_base_params(data, engine)
    if not base_params:
        print(f"[assign_test] Could not extract base parameters for engine={engine} from response:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 1

    # Build executable parameters for assignment
    params = dict(base_params)
    params.update(
        {
            "symbol": symbol,
            "interval": interval,
            "leverage": 1,
            "position_size": base_params.get("position_size", 0.02),
            "stop_loss_pct": base_params.get("stop_loss_pct", 0.02),
            "take_profit_pct": 0.0,
            "trailing_stop_pct": 0.0,
            "fee_pct": 0.001,
            "slippage_pct": 0.001,
            "no_compounding": True,
            "auto_trade_enabled": False,
            "direction": "LONG",
            "target_notional_usdt": 10.0,
        }
    )

    payload = {
        "symbol": symbol,
        "interval": interval,
        "engine": engine,
        "parameters": params,
        "source": "backtest-analysis",
        "assigned_by": "auto-test",
        "note": "BTCUSDT alpha DRY_RUN",
    }

    print("[assign_test] Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    try:
        r2 = requests.post(f"{BASE}/assign_strategy", json=payload, timeout=120)
        print("[assign_test] assign_strategy status:", r2.status_code)
        print("[assign_test] Response:")
        print(r2.text)
        return 0 if r2.status_code in (200, 201) else 1
    except Exception as e:
        print("[assign_test] ERROR calling assign_strategy:", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
