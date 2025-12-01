import itertools
from typing import Dict, Any, Tuple, List, Optional
import asyncio

from backtesting_backend.core.strategy_simulator import StrategySimulator


class ParameterOptimizer:
    def __init__(self, simulator: Optional[StrategySimulator] = None):
        self.simulator = simulator or StrategySimulator()

    async def optimize_parameters(self, symbol: str, interval: str, start_time: int, end_time: int,
                                  initial_balance: float, leverage: int, strategy_name: str,
                                  optimization_ranges: Dict[str, List[Any]], df) -> Dict[str, Any]:
        """Simple grid search optimizer using the provided DataFrame for simulations.

        optimization_ranges: {param_name: [values]}
        Returns the best parameter set and its result.
        """
        keys = list(optimization_ranges.keys())
        best = None
        best_params = None

        # generate combinations
        combos = list(itertools.product(*(optimization_ranges[k] for k in keys)))

        for combo in combos:
            params = dict(zip(keys, combo))
            # run simulation (sync) - simulator is synchronous in current design
            result = self.simulator.run_simulation(symbol, interval, df, initial_balance, leverage, params)
            if best is None or result.get("profit", 0) > best.get("profit", -1e18):
                best = result
                best_params = params

        return {"best_params": best_params, "best_result": best}
