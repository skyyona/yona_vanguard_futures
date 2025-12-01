import sys
import pytest
from PySide6.QtWidgets import QApplication

from gui.widgets.footer_engines_widget import TradingEngineWidget


def ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_leverage_not_applied_without_confirmation():
    app = ensure_app()
    widget = TradingEngineWidget('Alpha', '#4CAF50')
    # Set a non-zero account balance so funds calculations produce deterministic results
    widget.set_account_total_balance(1000.0)

    initial_leverage = widget.leverage_slider.value()
    initial_funds_pct = widget.funds_slider.value()

    exec_params = {'leverage': 5, 'position_size': 0.5}

    # Call without ui_meta (or with explicit False) — should NOT apply leverage/position_size
    widget.update_strategy_from_analysis('TEST', 3.0, {}, exec_params, ui_meta=None)
    app.processEvents()

    assert widget.leverage_slider.value() == initial_leverage
    assert widget.funds_slider.value() == initial_funds_pct


def test_leverage_applied_with_confirmation():
    app = ensure_app()
    widget = TradingEngineWidget('Alpha', '#4CAF50')
    widget.set_account_total_balance(1000.0)

    exec_params = {'leverage': 5, 'position_size': 0.5}

    widget.update_strategy_from_analysis('TEST', 3.0, {}, exec_params, ui_meta={'leverage_user_confirmed': True})
    app.processEvents()

    assert widget.leverage_slider.value() == 5
    # position_size 0.5 -> 50%
    assert widget.funds_slider.value() == 50
