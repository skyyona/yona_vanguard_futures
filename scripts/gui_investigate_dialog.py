"""
Non-destructive diagnostic for StrategyAnalysisDialog.
- Instantiates the dialog with a placeholder analysis_data, then emits
  several synthetic/edge-case payloads via `analysis_update.emit(...)`.
- Processes Qt events to allow queued handlers to run, captures any
  exceptions and logs full tracebacks to `logs/gui_investigate_dialog.log`.

Run: python .\scripts\gui_investigate_dialog.py

This script does NOT modify application code; it only imports and
instantiates the dialog to exercise its UI-building paths.
"""

import sys
import os
import time
import logging
import traceback
import json

# ensure project root on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

LOGDIR = os.path.join(ROOT, 'logs')
if not os.path.exists(LOGDIR):
    os.makedirs(LOGDIR, exist_ok=True)
LOGPATH = os.path.join(LOGDIR, 'gui_investigate_dialog.log')

logging.basicConfig(
    filename=LOGPATH,
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
)

logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Import the dialog class
try:
    from gui.widgets.strategy_analysis_dialog import StrategyAnalysisDialog
except Exception as e:
    logging.exception('Failed to import StrategyAnalysisDialog: %s', e)
    raise


def load_local_capture():
    path = os.path.join(os.path.dirname(__file__), 'find_new_listing_report.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
                # try to pick data key
                return payload.get('out', {}).get('data', payload.get('data', payload))
        except Exception:
            logging.exception('Failed to load local capture')
    return None


def make_payloads():
    # well-formed payload (synthetic)
    good = {
        'symbol': 'SQDUSDT',
        'best_engine': 'Alpha',
        'volatility': 12.3,
        'max_target_profit': {'alpha': 3.5, 'beta': 4.2, 'gamma': 6.0},
        'risk_management': {'stop_loss': 0.02, 'trailing_stop': 0.01},
        'is_new_listing': True,
        'data_missing': False,
        'confidence': 0.78,
        'metrics': {'total_return_pct': 5.0, 'win_rate': 60.0, 'max_drawdown_pct': 2.5, 'volatility_pct': 1.2},
        'executable_parameters': {'leverage': 1, 'position_size': 0.02, 'stop_loss_pct': 0.02},
        'engine_results': {
            'alpha': {'executable_parameters': {'fast_ema_period': 5, 'slow_ema_period': 21, 'stop_loss_pct': 0.02, 'leverage': 1, 'position_size': 0.02}},
            'beta': {},
            'gamma': {}
        }
    }

    # missing executable_parameters entirely
    missing_exec = dict(good)
    missing_exec.pop('executable_parameters', None)

    # malformed types
    malformed = dict(good)
    malformed['executable_parameters'] = 'this-should-be-dict'

    # very large payload (deep nested) to check performance/memory
    large = dict(good)
    large['notes'] = 'x' * 100000

    # payload with engine_results only (no top-level executable_parameters)
    engine_only = dict(good)
    engine_only.pop('executable_parameters', None)
    engine_only['executable_parameters'] = None
    engine_only['engine_results'] = {
        'alpha': {'executable_parameters': {'leverage': 3, 'position_size': 0.05}},
        'beta': {},
        'gamma': {}
    }

    # try local capture if available
    local = load_local_capture()

    payloads = [
        ('good', good),
        ('missing_exec', missing_exec),
        ('malformed', malformed),
        ('large', large),
        ('engine_only', engine_only),
    ]

    if local:
        payloads.append(('local_capture', local))

    return payloads


def run_test_loop():
    app = QApplication([])
    payloads = make_payloads()

    # Create a placeholder dialog with minimal initial data
    placeholder = {'best_engine': 'loading', 'volatility': 0, 'max_target_profit': {}, 'risk_management': {}, 'engine_results': {}}

    dialog = StrategyAnalysisDialog(symbol='SQDUSDT', analysis_data=placeholder)
    dialog.show()

    # Allow the GUI to initialize
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)

    for name, payload in payloads:
        logging.info('--- Testing payload: %s ---', name)
        try:
            # Use queued emit if available
            try:
                dialog.analysis_update.emit(payload)
            except Exception:
                logging.exception('Emit failed, trying direct set and _init_ui')
                try:
                    dialog.analysis_data = payload
                    dialog._init_ui()
                except Exception:
                    logging.exception('Direct UI rebuild failed')

            # Process events to allow queued slot to run
            for i in range(40):
                app.processEvents()
                time.sleep(0.05)

            logging.info('Payload %s processed without uncaught exception', name)
        except Exception as e:
            logging.exception('Unhandled exception while processing payload %s: %s', name, e)

    logging.info('All payload tests complete. Keeping dialog open briefly for manual inspection...')

    # keep visible for a short while
    for _ in range(80):
        app.processEvents()
        time.sleep(0.05)

    dialog.close()
    app.quit()


if __name__ == '__main__':
    logging.info('Starting StrategyAnalysisDialog investigation')
    try:
        run_test_loop()
    except Exception:
        logging.exception('Investigation script failed')
    logging.info('Investigation finished. Log: %s', LOGPATH)
    print('\nInvestigation log saved to:', LOGPATH)
