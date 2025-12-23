#!/usr/bin/env python3
"""Batch caller for strategy-analysis endpoint across multiple symbols.

Saves results to `scripts/all_strategy_analysis_results.json`.

Behavior:
- Tries to call the backend at http://127.0.0.1:8001/api/v1/backtest/strategy-analysis
- Uses provided symbol list; for new-listing examples attempts to pick candidates from
  `scripts/find_new_listing_report.json` if present; otherwise creates synthetic entries
  (marked as synthetic).
"""
import os
import sys
import time
import json
import urllib.parse
import urllib.request

BASE_URL = 'http://127.0.0.1:8001/api/v1/backtest/strategy-analysis'

TARGET_SYMBOLS = [
    'BTCUSDT',
    'ETHUSDT',
    'SOLUSDT',
    'DOGEUSDT'
]

from scripts.output_config import legacy_dir

OUT_PATH = os.path.join(legacy_dir(), 'all_strategy_analysis_results.json')


def fetch(symbol, period='1d', interval='1m', timeout=30):
    qs = urllib.parse.urlencode({'symbol': symbol, 'period': period, 'interval': interval})
    url = BASE_URL + '?' + qs
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = r.getcode()
            try:
                body = json.load(r)
            except Exception:
                body = {'raw': r.read().decode('utf-8', errors='ignore')}
            return {'symbol': symbol, 'status': status, 'body': body, 'error': None}
    except Exception as e:
        return {'symbol': symbol, 'status': getattr(e, 'code', None), 'body': None, 'error': str(e)}


def find_candidates_from_capture():
    path = os.path.join(os.path.dirname(__file__), 'find_new_listing_report.json')
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
    except Exception:
        return []
    candidates = []
    # look for any captured 'out' structure with symbol/engine_results
    out = payload.get('out') or payload
    # the capture format may place analyzed symbol in different keys; scan for engine_results
    def scan(obj):
        if not isinstance(obj, dict):
            return
        if 'engine_results' in obj and 'symbol' in obj:
            candidates.append(obj.get('symbol'))
        for v in obj.values():
            if isinstance(v, (dict, list)):
                scan(v) if isinstance(v, dict) else [scan(i) for i in v if isinstance(i, dict)]

    scan(out)
    # unique
    return list(dict.fromkeys(candidates))


def main():
    results = {'meta': {'started_at': time.time()}, 'calls': []}

    print('[BATCH] Looking for new-listing candidates in local capture...')
    candidates = find_candidates_from_capture()
    print(f'[BATCH] Found candidates in capture: {candidates}')

    # extend target list with at least two new-listing test cases (if possible)
    # We'll attempt to pick one candidate as 'new_enough' and one as 'new_data_missing' if available
    extra_new_enough = None
    extra_new_missing = None
    if candidates:
        extra_new_enough = candidates[0]
        if len(candidates) > 1:
            extra_new_missing = candidates[1]

    # Prepare full symbol list (preserve order)
    full_symbols = list(TARGET_SYMBOLS)
    if extra_new_enough and extra_new_enough not in full_symbols:
        full_symbols.append(extra_new_enough)
    if extra_new_missing and extra_new_missing not in full_symbols:
        full_symbols.append(extra_new_missing)

    # If no real candidates, synthesize two placeholder symbols to represent new-listing cases
    if not extra_new_enough:
        full_symbols.append('SYNTH_NEW_ENOUGH')
        full_symbols.append('SYNTH_NEW_MISSING')

    # wait for backend to be ready (quick probe)
    print('[BATCH] Probing backend availability...')
    ready = False
    for i in range(12):
        try:
            test = fetch('BTCUSDT', timeout=2)
            if test.get('status') and test.get('status') == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(1)

    if not ready:
        print('[BATCH] Backend did not respond with 200 to probe; proceeding anyway and recording errors.')

    for sym in full_symbols:
        print(f'[BATCH] Calling strategy-analysis for {sym}...')
        if sym.startswith('SYNTH_'):
            # create synthetic result structure consistent with backend schema
            synthetic = {
                'symbol': sym,
                'is_new_listing': True if sym == 'SYNTH_NEW_ENOUGH' else True,
                'data_missing': False if sym == 'SYNTH_NEW_ENOUGH' else True,
                'confidence': 0.6 if sym == 'SYNTH_NEW_ENOUGH' else 0.3,
                'engine_results': {
                    'alpha': {'executable_parameters': {'fast_ema_period':5,'slow_ema_period':21,'stop_loss_pct':0.02,'position_size':0.02}},
                    'beta': {},
                    'gamma': {}
                }
            }
            results['calls'].append({'symbol': sym, 'status': 'synthetic', 'payload': synthetic})
            continue

        res = fetch(sym)
        results['calls'].append(res)

    results['meta']['finished_at'] = time.time()
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'[BATCH] Done. Saved results to {OUT_PATH}')


if __name__ == '__main__':
    main()
