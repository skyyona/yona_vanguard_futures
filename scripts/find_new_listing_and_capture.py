import requests, time, json

BASE = 'https://fapi.binance.com'
exchange_info_url = BASE + '/fapi/v1/exchangeInfo'
klines_url = BASE + '/fapi/v1/klines'
backtest_url = 'http://127.0.0.1:8001/api/v1/backtest/strategy-analysis'

now_ms = int(time.time() * 1000)
start_ms = now_ms - 24*60*60*1000

print('Fetching exchangeInfo...')
r = requests.get(exchange_info_url, timeout=10)
if r.status_code != 200:
    print('Failed to fetch exchangeInfo', r.status_code, r.text)
    raise SystemExit(1)

symbols = r.json().get('symbols', [])
# filter for USDT futures TRA DING symbols
candidates = [s['symbol'] for s in symbols if s.get('quoteAsset')=='USDT' and s.get('status')=='TRADING']
print('Total USDT symbols:', len(candidates))

found = None
out = {'candidates_checked': []}
for sym in candidates[:300]:  # limit to first 300 to avoid long loops
    try:
        params = {'symbol': sym, 'interval': '1m', 'startTime': start_ms, 'endTime': now_ms, 'limit': 1000}
        kr = requests.get(klines_url, params=params, timeout=10)
        if kr.status_code != 200:
            out['candidates_checked'].append({'symbol': sym, 'error': kr.text[:200]})
            continue
        data = kr.json()
        cnt = len(data)
        out['candidates_checked'].append({'symbol': sym, 'count': cnt})
        # pick a symbol with small but non-zero candles, e.g., <200
        if 0 < cnt < 200:
            print('Found candidate', sym, 'candles=', cnt)
            found = sym
            break
    except Exception as e:
        out['candidates_checked'].append({'symbol': sym, 'error': str(e)})

if not found:
    print('No candidate with <200 candles found in sampled symbols; will fallback to next step')
    # as fallback, pick a random small-cap symbol from the list where count >0 but small
    min_pair = None
    min_cnt = 999999
    for c in out['candidates_checked']:
        if 'count' in c and c['count']>0 and c['count']<min_cnt:
            min_cnt = c['count']
            min_pair = c['symbol']
    if min_pair:
        found = min_pair
        print('Fallback pick', found, 'candles=', min_cnt)
    else:
        print('No valid candidate found. Exiting.')
        with open('scripts/find_new_listing_report.json','w',encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        raise SystemExit(1)

# call backtest strategy-analysis for found symbol
print('Calling strategy-analysis for', found)
try:
    r = requests.get(backtest_url, params={'symbol': found, 'period':'1d', 'interval':'1m'}, timeout=30)
    try:
        resp = r.json()
    except Exception:
        resp = {'text': r.text}
    result = {'symbol': found, 'status_code': r.status_code, 'response': resp}
except Exception as e:
    result = {'symbol': found, 'error': str(e)}

with open('scripts/find_new_listing_report.json','w',encoding='utf-8') as f:
    json.dump({'out': out, 'result': result}, f, ensure_ascii=False, indent=2)

print(json.dumps({'out_sample': out['candidates_checked'][:10], 'result': result}, ensure_ascii=False, indent=2))
