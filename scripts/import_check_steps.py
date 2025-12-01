import traceback
import sys
import os

# Ensure project root is on sys.path so package imports from scripts/ succeed
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

modules = [
    'backtesting_backend.api.backtest_router',
    'backtesting_backend.core.logger',
    'backtesting_backend.database.db_manager',
    'backtesting_backend.core.config_manager',
    'backtesting_backend.api_client',
    'backtesting_backend.database.repositories.kline_repository',
    'backtesting_backend.database.repositories.backtest_result_repository',
    'backtesting_backend.core.data_loader',
    'backtesting_backend.core.strategy_analyzer',
    'backtesting_backend.core.strategy_simulator',
    'backtesting_backend.core.parameter_optimizer',
    'backtesting_backend.core.backtest_service',
]

for m in modules:
    print(f'--- IMPORTING: {m} ---')
    try:
        __import__(m, fromlist=['*'])
        print('OK')
    except Exception:
        traceback.print_exc()
        print('\n')

print('DONE')
