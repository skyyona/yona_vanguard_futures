import sys
import os
import json
import time
from PySide6.QtWidgets import QApplication

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gui.widgets.strategy_analysis_dialog import StrategyAnalysisDialog
from gui.utils.analysis_payload_mapper import ensure_ui_payload
from gui.widgets.footer_engines_widget import TradingEngineWidget


def run_headless_test(json_path: str):
    print('[GUI-TEST] Loading analysis JSON:', json_path)
    # tolerate BOM or non-strict encodings by using 'utf-8-sig'
    with open(json_path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)

    app = QApplication([])

    # Create dialog with placeholder
    dialog = StrategyAnalysisDialog(symbol=data.get('symbol', 'SYM'), analysis_data={'best_engine':'loading','volatility':0,'max_target_profit':{},'risk_management':{},'engine_results':{}})

    assigned = {}
    def on_assigned(engine_name, strategy_data):
        print('[GUI-TEST] engine_assigned ->', engine_name)
        assigned['engine'] = engine_name
        assigned['strategy_data'] = strategy_data

    dialog.engine_assigned.connect(on_assigned)

    # Emit analysis update (ensure UI-shaped payload)
    payload = ensure_ui_payload(data)
    dialog.analysis_update.emit(payload.get('data', {}))
    # process events
    for _ in range(30):
        app.processEvents()
        time.sleep(0.01)

    print('[GUI-TEST] dialog.analysis_data keys:', list(dialog.analysis_data.keys()))

    engine_results = dialog.analysis_data.get('engine_results', {}) or {}
    for e in ['alpha','beta','gamma']:
        er = engine_results.get(e, {})
        execp = er.get('executable_parameters')
        print(f'[GUI-TEST] engine={e} has executable_parameters? {bool(execp)}')

    # simulate preview+assign for Alpha (auto-confirm)
    dialog._test_auto_confirm = True
    dialog.leverage_override_checkbox.setChecked(False)
    dialog._preview_and_assign('Alpha')
    print('[GUI-TEST] after assign attempt (no leverage) assigned keys:', list(assigned.keys()))

    # if assigned, show some fields
    if assigned:
        sd = assigned.get('strategy_data', {})
        execp_assigned = sd.get('executable_parameters', {})
        print('[GUI-TEST] assigned executable sample:', {k: execp_assigned.get(k) for k in ('fast_ema_period','slow_ema_period','stop_loss_pct','leverage','position_size')})

    # Test applying params to engine widget
    engine_widget = TradingEngineWidget('Alpha', '#4CAF50')
    print('[GUI-TEST] engine_widget before - leverage:', engine_widget.leverage_slider.value(), engine_widget.leverage_value_label.text())
    alpha_exec = payload.get('data', {}).get('engine_results', {}).get('alpha', {}).get('executable_parameters')
    if alpha_exec:
        engine_widget.update_strategy_from_analysis(payload.get('data', {}).get('symbol','SYM'), payload.get('data', {}).get('max_target_profit',{}).get('alpha',0), payload.get('data', {}).get('risk_management',{}), alpha_exec, {'leverage_user_confirmed': True})
        print('[GUI-TEST] engine_widget after - leverage:', engine_widget.leverage_slider.value(), engine_widget.leverage_value_label.text())

    print('[GUI-TEST] finished')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python scripts/gui_emit_analysis.py <analysis_json_path>')
        raise SystemExit(1)
    run_headless_test(sys.argv[1])
