#!/usr/bin/env python3
"""자동 GUI 캡처 및 Assign 페이로드 저장 스크립트

사용법 (PowerShell):
  python .\scripts\gui_auto_capture.py BTCUSDT AIUSDT RECENT_NEW_LOWDATA

동작:
 - 백엔드에서 `strategy-analysis` 호출을 시도하고 실패하면 `scripts/find_new_listing_report.json` 또는
   `scripts/all_strategy_analysis_results.json`에서 대체 페이로드를 찾습니다.
 - `StrategyAnalysisDialog`를 생성하고 렌더하여 `scripts/screenshots/{symbol}.png`로 저장합니다.
 - Assign(Alpha)를 시뮬레이트하고, 전달된 payload를 `scripts/screenshots/{symbol}_assign_payload.json`에 기록합니다.
"""
import sys
import os
import time
import json
import urllib.parse
import urllib.request

from PySide6.QtWidgets import QApplication
from scripts.output_config import legacy_dir

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from gui.widgets.strategy_analysis_dialog import StrategyAnalysisDialog
from gui.utils.popup import set_suppress_popups
from gui.utils.analysis_payload_mapper import ensure_ui_payload

BASE_URL = 'http://127.0.0.1:8001/api/v1/backtest/strategy-analysis'


def fetch_analysis(symbol: str, timeout=8):
    qs = urllib.parse.urlencode({'symbol': symbol, 'period': '1d', 'interval': '1m'})
    url = BASE_URL + '?' + qs
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.load(r).get('data', {})
            return data
    except Exception as e:
        print(f'[AUTO] Backend fetch failed for {symbol}: {e}')

    # fallback: search local captures
    candidates = [
        os.path.join(os.path.dirname(__file__), 'all_strategy_analysis_results.json'),
        os.path.join(os.path.dirname(__file__), 'find_new_listing_report.json')
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
                    # try different structures
                    if 'results' in payload:
                        for item in payload['results']:
                            if item.get('symbol') == symbol:
                                return item.get('data', {})
                    if 'out' in payload and isinstance(payload['out'], dict):
                        # legacy capture
                        out = payload['out']
                        if out.get('symbol') == symbol:
                            return out
                        # scan engine_results
                        if 'engine_results' in out and out.get('symbol'):
                            return out
            except Exception:
                continue

    print(f'[AUTO] No local capture found for {symbol}, using minimal synthetic payload')
    # synthetic fallback
    return {
        'symbol': symbol,
        'best_engine': 'Alpha',
        'volatility': 0,
        'max_target_profit': {'alpha': 3.5, 'beta': 4.0, 'gamma': 6.0},
        'risk_management': {'stop_loss': 0.2, 'trailing_stop': 0.1},
        'engine_results': {
            'alpha': {'executable_parameters': {'fast_ema_period': 5, 'slow_ema_period': 21, 'stop_loss_pct': 0.02, 'position_size': 0.005, 'leverage': 1}, 'confidence': 0.75},
            'beta': {},
            'gamma': {}
        },
        'is_new_listing': True if 'NEW' in symbol or 'AI' in symbol else False,
        'data_missing': False,
        'confidence': 0.6
    }


def ensure_out_dir():
    out_dir = os.path.join(legacy_dir(), 'screenshots')
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def capture_for_symbol(symbol: str):
    data = fetch_analysis(symbol)
    app = QApplication.instance() or QApplication([])

    # normalize payload to UI shape before creating dialog
    payload = ensure_ui_payload(data)
    dialog = StrategyAnalysisDialog(symbol=payload.get('data', {}).get('symbol', symbol), analysis_data=payload.get('data', {}))

    captured = {'symbol': symbol, 'analysis_keys': list((payload.get('data') or {}).keys())}

    # connect to capture assign payload
    assign_payload = {}

    def on_assigned(engine, payload):
        assign_payload['engine'] = engine
        assign_payload['strategy_data'] = payload

    dialog.engine_assigned.connect(on_assigned)

    dialog.show()
    # allow events to render
    app.processEvents()
    time.sleep(0.5)

    out_dir = ensure_out_dir()
    img_path = os.path.join(out_dir, f'{symbol}.png')
    try:
        pix = dialog.grab()
        pix.save(img_path)
        print(f'[AUTO] Saved screenshot: {img_path}')
        captured['screenshot'] = img_path
    except Exception as e:
        print(f'[AUTO] Screenshot failed: {e}')

    # simulate Assign -> Alpha: suppress real popups in automated capture
    try:
        set_suppress_popups(True)
        dialog._preview_and_assign('Alpha')
        time.sleep(0.1)
    except Exception as e:
        print(f'[AUTO] Assign simulation failed: {e}')
    finally:
        set_suppress_popups(False)

    # write captured assign payload
    payload_path = os.path.join(out_dir, f'{symbol}_assign_payload.json')
    try:
        with open(payload_path, 'w', encoding='utf-8') as f:
            json.dump(assign_payload, f, ensure_ascii=False, indent=2)
        print(f'[AUTO] Saved assign payload: {payload_path}')
        captured['assign_payload'] = payload_path
    except Exception as e:
        print(f'[AUTO] Failed to save assign payload: {e}')

    # close dialog
    dialog.accept()
    app.processEvents()
    return captured


def main(argv):
    symbols = argv[1:] if len(argv) > 1 else ['BTCUSDT', 'AIUSDT', 'RECENT_NEW_LOWDATA']
    results = []
    for s in symbols:
        print(f'[AUTO] Processing {s}...')
        r = capture_for_symbol(s)
        results.append(r)

    out_dir = ensure_out_dir()
    summary_path = os.path.join(out_dir, 'capture_summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'[AUTO] Done. Summary: {summary_path}')


if __name__ == '__main__':
    main(sys.argv)
