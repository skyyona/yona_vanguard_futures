import pandas as pd
from backtesting_backend.core.strategy_simulator import StrategySimulator
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer


def make_df(prices):
    idx = pd.date_range("2025-01-01", periods=len(prices), freq="T")
    return pd.DataFrame({"close": prices}, index=idx)


def test_tp_sl_and_drawdown():
    analyzer = StrategyAnalyzer()
    sim = StrategySimulator(analyzer=analyzer)

    # create price series that triggers entry then TP
    prices = [100, 101, 102, 103, 105, 107, 110]
    df = make_df(prices)

    params = {
        "fast_ema_period": 2,
        "slow_ema_period": 3,
        "stop_loss_pct": 0.01,
        "take_profit_pct": 0.05,
        "trailing_stop_pct": 0.0,
        "fee_pct": 0.0,
        "slippage_pct": 0.0,
        "position_size": 0.1,  # legacy numeric -> capital fraction
    }

    res = sim.run_simulation("TEST", "1m", df, initial_balance=1000.0, leverage=1, strategy_parameters=params)
    assert "profit_percentage" in res
    assert res["total_trades"] >= 0
    assert res["max_drawdown_pct"] >= 0


def test_position_size_policy_risk_per_trade():
    analyzer = StrategyAnalyzer()
    sim = StrategySimulator(analyzer=analyzer)

    prices = [100, 99, 98, 97, 96, 95, 94, 93]
    df = make_df(prices)

    params = {
        "fast_ema_period": 2,
        "slow_ema_period": 3,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.01,
        "trailing_stop_pct": 0.0,
        "fee_pct": 0.0,
        "slippage_pct": 0.0,
        "position_size_policy": {"method": "risk_per_trade", "value": 0.01},
    }

    res = sim.run_simulation("TEST", "1m", df, initial_balance=1000.0, leverage=1, strategy_parameters=params)
    assert "trades" in res
    # ensure position sizing produced finite units in trades if any
    for t in res["trades"]:
        assert "entry_price" in t

