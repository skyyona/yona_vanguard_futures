#!/usr/bin/env python3
"""
Headless GUI capture script.
- Fetches strategy-analysis JSON
- Instantiates StrategyAnalysisDialog and TradingEngineWidget
- Emits analysis update, simulates Assign
- Saves screenshots and logs to `scripts/` folder
"""
import sys
import os
import time
import json
import traceback

import requests
from PySide6.QtWidgets import QApplication

# Ensure workspace root is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

LOG_PATH = os.path.join(os.path.dirname(__file__), 'gui_capture_log.txt')
DIALOG_SS = os.path.join(os.path.dirname(__file__), 'dialog_screenshot.png')
ENGINE_SS = os.path.join(os.path.dirname(__file__), 'engine_screenshot.png')

def log(msg):
    print(msg)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')


def main():
    try:
        url = 'http://127.0.0.1:8001/api/v1/backtest/strategy-analysis?symbol=SQDUSDT&period=1w&interval=1h'
        log('[TEST] Fetching analysis from backend: %s' % url)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        raw = resp.json()
        # normalize using central mapper if backend returned a flat row
        from gui.utils.analysis_payload_mapper import ensure_ui_payload
        data = ensure_ui_payload(raw).get('data')
        if not data:
            log('[ERROR] No data returned from strategy-analysis')
            return 2

        log('[TEST] Received analysis keys: %s' % list(data.keys()))

        # Import GUI widgets
        from gui.widgets.strategy_analysis_dialog import StrategyAnalysisDialog
        from gui.widgets.footer_engines_widget import TradingEngineWidget

        app = QApplication(sys.argv)

        # Create and show the dialog. Try constructors with/without analysis_data.
        try:
            dialog = StrategyAnalysisDialog(None, data)
        except TypeError:
            try:
                dialog = StrategyAnalysisDialog(data)
            except TypeError:
                dialog = StrategyAnalysisDialog(None)

        # emit the analysis update signal used in-app (or call fallback handler)
        try:
            dialog.analysis_update.emit(data)
        except Exception:
            try:
                dialog._on_analysis_update(data)
            except Exception:
                log('[WARN] Could not emit analysis_update signal or call _on_analysis_update')

        dialog.show()
        app.processEvents()
        time.sleep(0.6)

        # Save dialog screenshot
        try:
            pix = dialog.grab()
            pix.save(DIALOG_SS)
            log('[OK] Dialog screenshot saved: %s' % DIALOG_SS)
        except Exception as e:
            log('[ERROR] Saving dialog screenshot: %s' % e)

        # Simulate Assign for the best engine (if attribute exists) or "alpha"
        best = data.get('best_engine') or 'alpha'
        engine_key = best if isinstance(best, str) else 'alpha'
        log('[TEST] Simulating Assign (%s)' % engine_key)
        try:
            # call the same internal handler used by GUI when Assign clicked
            dialog._on_engine_assigned(engine_key)
            log('[TEST] dialog._on_engine_assigned called -> %s' % engine_key)
        except Exception as e:
            log('[WARN] dialog._on_engine_assigned failed: %s' % e)

        # Now instantiate an engine widget and apply params
        try:
            engine_name = engine_key.capitalize()
            # TradingEngineWidget constructor signature may vary across versions.
            # Try common variants until one works.
            engine_widget = None
            tried = []
            for args in [ (engine_name,), (engine_name, 'blue'), (engine_name, None), (None,), () ]:
                try:
                    engine_widget = TradingEngineWidget(*args)
                    break
                except TypeError as te:
                    tried.append((args, str(te)))
            if engine_widget is None:
                log('[ERROR] Could not instantiate TradingEngineWidget. Tried: %s' % tried)
                raise TypeError('TradingEngineWidget ctor not matched')
            exec_params = data.get('engine_results', {}).get(engine_key, {}).get('executable_parameters', {})
            max_target_profit = data.get('max_target_profit', {}).get(engine_key)
            risk_management = data.get('risk_management', {})

            log('[TEST] engine=%s has executable_parameters? %s  sample: %s' % (
                engine_key, bool(exec_params), list(exec_params.items())[:5] if exec_params else exec_params
            ))

            engine_widget.update_strategy_from_analysis(
                data.get('symbol'),
                max_target_profit,
                risk_management,
                exec_params,
                data.get('ui_meta')
            )
            engine_widget.show()
            app.processEvents()
            time.sleep(0.4)

            # Save engine widget screenshot
            try:
                pix2 = engine_widget.grab()
                pix2.save(ENGINE_SS)
                log('[OK] Engine screenshot saved: %s' % ENGINE_SS)
            except Exception as e:
                log('[ERROR] Saving engine screenshot: %s' % e)

            log('[MAIN] ✅ 전략 분석 완료')
            log('[%s] 🔧 executable_parameters: %s' % (engine_name, json.dumps(exec_params, ensure_ascii=False)))
            log('[%s] ✅ 전략 업데이트 완료' % engine_name)

        except Exception as e:
            log('[ERROR] Engine widget flow failed: %s' % e)
            log(traceback.format_exc())

        # Allow a bit before quitting
        time.sleep(0.5)
        # exit
        return 0

    except Exception as e:
        log('[FATAL] %s' % e)
        log(traceback.format_exc())
        return 3


if __name__ == '__main__':
    rc = main()
    sys.exit(rc)
