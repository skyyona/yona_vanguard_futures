import sys
import os
import urllib.request
import json
from PySide6.QtWidgets import QApplication

# ensure project root is in sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gui.widgets.strategy_analysis_dialog import StrategyAnalysisDialog
from gui.widgets.footer_engines_widget import TradingEngineWidget


def fetch_analysis(symbol='SQDUSDT'):
    url = f'http://127.0.0.1:8001/api/v1/backtest/strategy-analysis?symbol={symbol}&period=1w&interval=1h'
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.load(r).get('data', {})
    except Exception as e:
        # fallback: load last captured analysis (offline test)
        print('[TEST] Backend fetch failed, falling back to local capture:', e)
        local_path = os.path.join(os.path.dirname(__file__), 'find_new_listing_report.json')
        if os.path.exists(local_path):
            with open(local_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
                return payload.get('out', {}).get('data', payload.get('data', {}))
        raise


def main():
    app = QApplication([])
    print('[TEST] Fetching analysis from backend...')
    data = fetch_analysis()
    print('[TEST] Received analysis keys:', list(data.keys()))

    # If backend/local capture returned no useful data, create a synthetic minimal payload
    if not data:
        print('[TEST] No analysis data found - using synthetic sample payload for GUI test')
        data = {
            'symbol': 'SQDUSDT',
            'best_engine': 'Alpha',
            'volatility': 12.3,
            'max_target_profit': {'alpha': 3.5, 'beta': 4.2, 'gamma': 6.0},
            'risk_management': {'stop_loss': 0.2, 'trailing_stop': 0.1},
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
                },
                'beta': {},
                'gamma': {}
            }
        }

    # Create dialog with placeholder then update
    dialog = StrategyAnalysisDialog(symbol=data.get('symbol','SQDUSDT'), analysis_data={
        'best_engine':'loading', 'volatility':0, 'max_target_profit':{}, 'risk_management':{}, 'engine_results':{}
    })

    # Connect engine_assigned to capture
    assigned = {}
    def on_assigned(engine_name, strategy_data):
        print('[TEST] engine_assigned emitted ->', engine_name)
        assigned['engine'] = engine_name
        assigned['strategy_data'] = strategy_data

    dialog.engine_assigned.connect(on_assigned)

    # Update dialog with real data via signal (mimic worker)
    dialog.analysis_update.emit(data)

    # Check rendered content by inspecting dialog.analysis_data
    print('[TEST] dialog.analysis_data keys:', list(dialog.analysis_data.keys()))
    engine_results = dialog.analysis_data.get('engine_results', {})
    for e in ['alpha','beta','gamma']:
        er = engine_results.get(e, {})
        execp = er.get('executable_parameters')
        print(f'[TEST] engine={e} has executable_parameters? {bool(execp)}')
        if execp:
            # Pretty print some fields
            print('  sample:', {k: execp.get(k) for k in ('fast_ema_period','slow_ema_period','stop_loss_pct','leverage','position_size')})

    # Simulate clicking Assign for Alpha by emitting a headless-friendly payload
    print('[TEST] Simulating Assign (Alpha) via simulated payload')
    simulated_payload = {
        'symbol': data.get('symbol','SQDUSDT'),
        'engine_name': 'Alpha',
        'analysis_data': data,
        'executable_parameters': data.get('engine_results', {}).get('alpha', {}).get('executable_parameters', {}),
        'applied_risk_overrides': {},
        'ui_meta': {'confirmed_by_user': True, 'confirmed_at': None, 'source': 'tests/gui_assign_test'}
    }
    dialog.engine_assigned.emit('Alpha', simulated_payload)

    print('[TEST] Assigned payload:', assigned.keys())
    if assigned:
        sd = assigned.get('strategy_data',{})
        ad = sd.get('analysis_data',{})
        alpha_exec = ad.get('engine_results',{}).get('alpha',{}).get('executable_parameters')
        print('[TEST] extracted alpha executable:', alpha_exec)

    # Create engine widget and apply params
    engine_widget = TradingEngineWidget('Alpha','#4CAF50')
    print('[TEST] Before apply - leverage slider value:', engine_widget.leverage_slider.value(), engine_widget.leverage_value_label.text())
    print('[TEST] Before apply - funds slider value:', engine_widget.funds_slider.value(), engine_widget.funds_value_label.text())

    if alpha_exec:
        engine_widget.update_strategy_from_analysis(data.get('symbol','SQDUSDT'), data.get('max_target_profit',{}).get('alpha',0), data.get('risk_management',{}), alpha_exec)
        print('[TEST] After apply - leverage slider value:', engine_widget.leverage_slider.value(), engine_widget.leverage_value_label.text())
        print('[TEST] After apply - funds slider value:', engine_widget.funds_slider.value(), engine_widget.funds_value_label.text())

    print('[TEST] Done')
    # don't exec app.exec() - this is headless test

if __name__ == '__main__':
    main()
