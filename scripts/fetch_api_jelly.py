import urllib.request, urllib.parse, json, sys

url = 'http://127.0.0.1:8001/api/v1/backtest/strategy-analysis'
params = {'symbol':'JELLYJELLYUSDT','period':'1w','interval':'1m'}
full = url + '?' + urllib.parse.urlencode(params)
try:
    with urllib.request.urlopen(full, timeout=300) as r:
        text = r.read().decode('utf-8')
    open('C:/Users/User/new/api_jelly_after_fix.json','w',encoding='utf-8').write(text)
    data = json.loads(text)
    print('SAVED C:/Users/User/new/api_jelly_after_fix.json')
    print('TOTAL_TRADES=' + str(data.get('data',{}).get('performance',{}).get('total_trades')))
except Exception as e:
    print('ERROR', e)
    sys.exit(2)
