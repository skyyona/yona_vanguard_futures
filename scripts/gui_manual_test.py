"""
Interactive GUI test launcher for StrategyAnalysisDialog.
- Launches the dialog with a representative payload and blocks until you close it.
- Logs `engine_assigned` emissions to stdout.

Run:
    python .\scripts\gui_manual_test.py

"""
import sys
import os
import json
import logging

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

from PySide6.QtWidgets import QApplication

try:
    from gui.widgets.strategy_analysis_dialog import StrategyAnalysisDialog
except Exception as e:
    logging.exception('Failed to import StrategyAnalysisDialog: %s', e)
    raise


def make_sample_payload():
    return {
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


def on_engine_assigned(engine_name, payload):
    logging.info('engine_assigned -> %s', engine_name)
    # print some keys for inspection
    try:
        keys = list(payload.keys())
    except Exception:
        keys = str(type(payload))
    logging.info('assigned payload keys: %s', keys)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    payload = make_sample_payload()

    dialog = StrategyAnalysisDialog(symbol=payload.get('symbol', 'TEST'), analysis_data=payload)
    dialog.engine_assigned.connect(on_engine_assigned)

    logging.info('Showing StrategyAnalysisDialog - interact with it, then close the dialog to finish test')
    # Use exec_()/exec() to block until the dialog is closed by user
    try:
        result = dialog.exec()
        logging.info('Dialog closed with result: %s', result)
    except Exception:
        logging.exception('Dialog run failed')

    logging.info('Interactive GUI test finished')
    sys.exit(0)
