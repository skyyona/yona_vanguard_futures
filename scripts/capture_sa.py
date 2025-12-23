import requests, json, time, os
from scripts.output_config import legacy_dir
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
out_path = os.path.join(legacy_dir(), 'captured_strategy_analysis.json')
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=2))
