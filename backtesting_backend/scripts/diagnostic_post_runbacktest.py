import json, time, requests
from datetime import datetime, timedelta

url = "http://127.0.0.1:8001/api/v1/backtest/run_backtest"

# compute start/end in ms
end_ms = int(time.time() * 1000)
start_dt = datetime.utcnow() - timedelta(days=7)
start_ms = int(start_dt.timestamp() * 1000)

body = {
    "strategy_name": "auto_test_tp",
    "symbol": "BTCUSDT",
    "interval": "1m",
    "start_time": start_ms,
    "end_time": end_ms,
    "initial_balance": 1000.0,
    "leverage": 1,
    "parameters": {
        "fast_ema_period": 9,
        "slow_ema_period": 21,
        "stop_loss_pct": 0.005
    },
    "optimization_mode": False,
    "optimization_ranges": None,
    # new execution params (top-up)
    "take_profit_pct": 0.02,
    "trailing_stop_pct": 0.01,
    "fee_pct": 0.0005,
    "slippage_pct": 0.001,
    "position_size": 1.0
}

print(json.dumps({"posting_to": url, "body_sample": {k: body[k] for k in ["strategy_name","symbol","interval","initial_balance"]}}, ensure_ascii=False, indent=2))
try:
    r = requests.post(url, json=body, timeout=120)
    try:
        print(json.dumps({'status_code': r.status_code, 'json': r.json()}, ensure_ascii=False, indent=2))
    except Exception:
        print(json.dumps({'status_code': r.status_code, 'text': r.text}, ensure_ascii=False, indent=2))
except Exception as e:
    print(json.dumps({'error': str(e)}))
