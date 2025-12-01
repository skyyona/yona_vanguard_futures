import requests, json, time
url='http://127.0.0.1:8001/api/v1/backtest/strategy-analysis'
symbols=['BTCUSDT','SQDUSDT','NEWLISTCOINUSDT']
out = {}
for s in symbols:
    try:
        r = requests.get(url, params={'symbol':s,'period':'1d','interval':'1m'}, timeout=30)
        try:
            out[s] = {'status_code': r.status_code, 'json': r.json()}
        except Exception:
            out[s] = {'status_code': r.status_code, 'text': r.text}
    except Exception as e:
        out[s] = {'error': str(e)}
    time.sleep(0.5)
with open('scripts/captured_strategy_analysis.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
