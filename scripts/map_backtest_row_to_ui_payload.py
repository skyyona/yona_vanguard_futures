import json
import os
from scripts.output_config import legacy_dir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(legacy_dir(), 'tmp_latest_analysis.json')
OUT = os.path.join(legacy_dir(), 'tmp_mapped_ui_payload.json')

with open(IN, 'r', encoding='utf-8') as f:
    row = json.load(f)

def map_row(r: dict) -> dict:
    # parameters_parsed may exist from earlier extractor
    params = r.get('parameters_parsed') or {}

    perf = {
        'profit_percentage': float(r.get('profit_percentage') or 0.0),
        'max_drawdown_pct': float(r.get('max_drawdown') or 0.0),
        'total_trades': int(r.get('total_trades') or 0),
        'win_rate': float(r.get('win_rate') or 0.0),
        'aborted_early': False,
        'insufficient_trades': bool(int(r.get('total_trades') or 0) < 5),
    }

    ui = {
        'symbol': r.get('symbol'),
        'run_id': r.get('run_id'),
        'initial_balance': float(r.get('initial_balance') or 0.0),
        'final_balance': float(r.get('final_balance') or 0.0),
        'period': '1w',
        'interval': r.get('interval') or '1m',
        'volatility': 0.0,
        'best_parameters': params,
        'performance': perf,
        'leverage_recommendation': {},
        'listing_meta': {'days_since_listing': 999, 'is_new_listing': False, 'new_listing_strategy_applied': False},
        'scenarios': {},
        'strategy_performance': [perf],
        'trade_logs': [],
        'engine_results': {
            'alpha': {'executable_parameters': params},
            'beta': {},
            'gamma': {},
        }
    }
    return ui

mapped = map_row(row)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump({'data': mapped}, f, ensure_ascii=False, indent=2)

print('WROTE', OUT)
print('SAMPLE_KEYS', list(mapped.keys()))
