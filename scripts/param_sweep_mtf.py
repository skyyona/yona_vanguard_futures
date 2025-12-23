import os
import sys
import asyncio
import json
from itertools import product

# ensure project root and scripts path are importable
ROOT = os.getcwd()
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
SCRIPTS_DIR = os.path.join(ROOT, 'scripts')
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import run_xpin_mtf

from backtesting_backend.database.db_manager import BacktestDB
import backend.core.new_strategy.backtest_adapter as adapter_mod
import backend.core.new_strategy.orchestrator as orch_mod


async def init_db():
    await BacktestDB.get_instance().init()


def make_wrapped_backtestconfig(orig_cls, fee, slippage):
    class Wrapped(orig_cls):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            # override commission/slippage for this run
            try:
                self.commission_rate = float(fee)
                self.slippage_rate = float(slippage)
            except Exception:
                pass

    return Wrapped


def make_step_wrapper(orig_step, pos_size):
    def wrapped(self, *a, **kw):
        res = orig_step(self, *a, **kw)
        try:
            if isinstance(res, dict) and 'position_size' not in res:
                res['position_size'] = pos_size
        except Exception:
            pass
        return res

    return wrapped


def run_sweep():
    # small variations (user asked for small changes)
    fees = [0.001, 0.002]
    slippages = [0.0001, 0.0005, 0.001]
    pos_sizes = [0.02, 0.1, 0.5]

    combos = list(product(fees, slippages, pos_sizes))

    symbol = os.environ.get('SYMBOL', 'BEATUSDT')
    results = []

    orig_BacktestConfig = adapter_mod.BacktestConfig
    orig_step = orch_mod.StrategyOrchestrator.step

    try:
        asyncio.run(init_db())
    except Exception as e:
        print('DB init failed:', e)

    for fee, slip, ps in combos:
        print(f"Running combo fee={fee} slip={slip} pos_size={ps}")
        # patch BacktestConfig
        adapter_mod.BacktestConfig = make_wrapped_backtestconfig(orig_BacktestConfig, fee, slip)
        # patch orchestrator.step to inject position_size
        orch_mod.StrategyOrchestrator.step = make_step_wrapper(orig_step, ps)

        # run the single mtf run (uses run_xpin_mtf.run_for)
        try:
            res = asyncio.run(run_xpin_mtf.run_for(symbol, run_xpin_mtf.INTERVAL, run_xpin_mtf.DAYS, params=None))
        except Exception as e:
            print('Run failed for combo', fee, slip, ps, 'error:', e)
            res = None

        # collect summary
        summary = {
            'fee': fee,
            'slippage': slip,
            'position_size': ps,
            'result': res,
        }
        results.append(summary)

    # restore originals
    adapter_mod.BacktestConfig = orig_BacktestConfig
    orch_mod.StrategyOrchestrator.step = orig_step

    out_dir = os.path.join(os.getcwd(), 'backtest_results_mtf')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f'param_sweep_{symbol}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print('Sweep complete. Results written to', out_path)


if __name__ == '__main__':
    run_sweep()
