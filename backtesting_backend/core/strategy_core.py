"""High-level strategy entrypoints for backtesting.

This module provides a single function that runs the current
backtesting strategy over a DataFrame. It is a thin wrapper around the
StrategySimulator so callers don't need to know implementation
details.
"""
from __future__ import annotations

from typing import Dict, Any

import pandas as pd

from backtesting_backend.core.strategy_simulator import StrategySimulatorFeature


def run_backtest(
    symbol: str,
    interval: str,
    df: pd.DataFrame,
    initial_balance: float,
    leverage: int,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """Run the unified backtesting strategy and return detailed results.

    All higher-level services (e.g. /strategy-analysis) should prefer
    to call this function instead of instantiating StrategySimulator
    directly. This makes it easier to later swap the underlying
    implementation without changing call sites.
    """
    sim = StrategySimulatorFeature()
    return sim.run_simulation(symbol, interval, df, initial_balance, leverage, params)
