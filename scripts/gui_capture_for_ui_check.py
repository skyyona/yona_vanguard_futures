import sys
import os
import time
import json
from PySide6.QtWidgets import QApplication

# Ensure project root in path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gui.widgets.strategy_analysis_dialog import StrategyAnalysisDialog
from gui.utils.analysis_payload_mapper import ensure_ui_payload


def main():
    app = QApplication([])

    # Synthetic minimal payload following earlier tests
    data = {
        'symbol': 'SQDUSDT',
        'best_engine': 'Alpha',
        'volatility': 12.3,
        'max_target_profit': {'alpha': 3.5, 'beta': 4.2, 'gamma': 6.0},
        'risk_management': {'stop_loss': 0.02, 'trailing_stop': 0.01, 'force_leverage': 3},
        'is_new_listing': True,
        'data_missing': False,
        'confidence': 0.78,
        'engine_results': {
            'alpha': {
                'suitability': '적합',
                'score': 92,
                'expected_profit': 3.2,
                'max_target_profit': 3.5,
                'win_rate': 62.5,
                'executable_parameters': {
                    'fast_ema_period': 5,
                    'slow_ema_period': 21,
                    'stop_loss_pct': 0.02,
                    'leverage': 1,
                    'position_size': 0.02
                },
                'is_new_listing': True,
                'data_missing': False,
                'confidence': 0.8
            }
        }
    }

    dialog = StrategyAnalysisDialog(symbol=data.get('symbol','SQDUSDT'), analysis_data={
        'best_engine':'loading', 'volatility':0, 'max_target_profit':{}, 'risk_management':{}, 'engine_results':{}
    })

    # emit update (normalized)
    payload = ensure_ui_payload(data)
    dialog.analysis_update.emit(payload.get('data', {}))
    for _ in range(10):
        app.processEvents()
        time.sleep(0.02)

    dialog.show()
    app.processEvents()
    time.sleep(0.2)

    try:
        out = os.path.join(os.path.dirname(__file__), 'dialog_ui_check.png')
        pix = dialog.grab()
        pix.save(out)
        print('[OK] Dialog screenshot saved:', out)
    except Exception as e:
        print('[ERROR] saving screenshot:', e)


if __name__ == '__main__':
    main()
