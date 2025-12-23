import urllib.request, urllib.parse, json, sys, os
from scripts.output_config import legacy_dir

url = 'http://127.0.0.1:8001/api/v1/backtest/strategy-analysis'
params = {'symbol':'JELLYJELLYUSDT','period':'1w','interval':'1m'}
full = url + '?' + urllib.parse.urlencode(params)
try:
    with urllib.request.urlopen(full, timeout=300) as r:
        text = r.read().decode('utf-8')
    out_path = os.path.join(legacy_dir(), 'api_jelly_after_fix.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path,'w',encoding='utf-8').write(text)
    data = json.loads(text)
    print(f'SAVED {out_path}')
    print('TOTAL_TRADES=' + str(data.get('data',{}).get('performance',{}).get('total_trades')))
except Exception as e:
    print('ERROR', e)
    sys.exit(2)
