import json, requests
url = "http://127.0.0.1:8001/api/v1/backtest/strategy-analysis?symbol=BTCUSDT&interval=1m&period=1w"
try:
    r = requests.get(url, timeout=120)
    try:
        print(json.dumps({'status_code': r.status_code, 'json': r.json()}, ensure_ascii=False, indent=2))
    except Exception:
        print(json.dumps({'status_code': r.status_code, 'text': r.text}, ensure_ascii=False, indent=2))
except Exception as e:
    print(json.dumps({'error': str(e)}, ensure_ascii=False, indent=2))
