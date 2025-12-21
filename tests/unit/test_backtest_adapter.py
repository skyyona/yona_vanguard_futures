import os
import sys
import logging
import datetime
import pytest
import pandas as pd

# Ensure package path (yona_vanguard_futures) is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'yona_vanguard_futures')))

from backend.core.new_strategy.backtest_adapter import BacktestExecutor, BacktestConfig


def make_empty_df():
    return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "quote_volume", "trades"])


def test_position_size_as_fraction():
    cfg = BacktestConfig(initial_balance=1000.0, leverage=10)
    exe = BacktestExecutor(None, cfg, make_empty_df(), make_empty_df(), make_empty_df())
    price = 50000.0
    exe.balance = cfg.initial_balance

    exe._handle_entry({"entry_signal": {"direction": "LONG"}, "position_size": 0.02}, price, datetime.datetime.now())

    expected_qty = (0.02 * cfg.initial_balance * cfg.leverage) / price
    assert pytest.approx(expected_qty, rel=1e-6) == exe.position.quantity


def test_position_size_warning_logged(caplog):
    caplog.set_level(logging.WARNING)
    cfg = BacktestConfig(initial_balance=1000.0, leverage=50)
    exe = BacktestExecutor(None, cfg, make_empty_df(), make_empty_df(), make_empty_df())
    price = 50000.0
    exe.balance = cfg.initial_balance

    exe._handle_entry({"entry_signal": {"direction": "LONG"}, "position_size": 1.0}, price, datetime.datetime.now())

    # Ensure warning was emitted
    messages = [r.message for r in caplog.records]
    assert any("position_size >= 1.0 detected" in m for m in messages)

    expected_qty = (1.0 * cfg.initial_balance * cfg.leverage) / price
    assert pytest.approx(expected_qty, rel=1e-6) == exe.position.quantity


def test_order_quantity_overrides_position_size():
    cfg = BacktestConfig(initial_balance=1000.0, leverage=10)
    exe = BacktestExecutor(None, cfg, make_empty_df(), make_empty_df(), make_empty_df())
    price = 50000.0

    exe._handle_entry({"entry_signal": {"direction": "LONG"}, "position_size": 0.02, "order_quantity": 0.5}, price, datetime.datetime.now())

    assert pytest.approx(0.5, rel=1e-9) == exe.position.quantity
