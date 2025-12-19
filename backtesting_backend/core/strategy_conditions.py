"""Strategy condition module for backtesting.

This module is intended to be the *single* place where the
entry/exit/indicator rules for the backtesting strategy are defined.

By default it delegates to StrategyAnalyzer so that existing behaviour
remains unchanged. In the future, strategy authors can modify or
replace the logic here (compute_indicators / generate_signals) without
having to touch the simulator or service layers.
"""
from __future__ import annotations

from typing import Dict, Any

import logging
import pandas as pd

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer

logger = logging.getLogger("backtest")


def compute_indicators(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """Add indicators required by the strategy to the DataFrame.

    This is the canonical entry point for indicator calculation used by
    the backtesting strategy. It currently forwards to StrategyAnalyzer
    but can be customised here.
    """
    # Basic defensive checks: ensure expected price/volume columns exist before
    # delegating to the analyzer. If columns are missing, log and raise a
    # clear ValueError so callers can handle it appropriately.
    required_cols = ["open", "high", "low", "close", "volume"]
    if not isinstance(df, pd.DataFrame):
        logger.error("compute_indicators: expected DataFrame, got %s", type(df))
        raise ValueError("compute_indicators: input must be a pandas DataFrame")

    present = set(df.columns)
    missing = [c for c in required_cols if c not in present]
    if missing:
        logger.error("compute_indicators: missing required columns: %s. available=%s", missing, list(df.columns))
        raise ValueError(f"compute_indicators: missing required columns: {missing}")

    analyzer = StrategyAnalyzer()
    return analyzer.calculate_indicators(df, params)


def generate_signals(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
    """Generate buy/sell signals for the strategy.

    The returned DataFrame should contain at least ``buy_signal`` and
    ``sell_signal`` boolean columns. Existing behaviour is
    implemented by StrategyAnalyzer and reused here.
    """
    analyzer = StrategyAnalyzer()
    return analyzer.generate_signals(df, params)
