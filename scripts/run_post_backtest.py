import json, urllib.request
req=json.load(open('tmp_backtest_req.json'))
url='http://127.0.0.1:8001/api/v1/backtest/run_backtest'
data=json.dumps(req).encode()
reqp=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'})
with urllib.request.urlopen(reqp, timeout=60) as resp:
    print(resp.read().decode())
