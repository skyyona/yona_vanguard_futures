import pandas as pd
from backtesting_backend.core.strategy_simulator import StrategySimulator


def make_df(prices):
    idx = pd.date_range("2025-01-01", periods=len(prices), freq="T")
    # allow injecting precomputed signals
    df = pd.DataFrame({"close": prices}, index=idx)
    return df


def test_simulator_scaling_with_default_capital_fraction():
    """Verify that when strategy does not specify position sizing:
    - profit percentage is independent of initial_balance (for same leverage)
    - profit percentage scales linearly with leverage
    """
    sim = StrategySimulator()

    # simple two-bar scenario: buy at 100, sell at 110
    prices = [100.0, 110.0]
    df = make_df(prices)
    # precompute signals so simulator executes a single buy->sell
    df.loc[df.index[0], 'buy_signal'] = True
    df.loc[df.index[1], 'sell_signal'] = True

    params = {
        # ensure simulator uses precomputed signals and default sizing
        'use_precomputed_signals': True,
        # do not specify position_size or position_size_policy so fallback applies
    }

    res_a = sim.run_simulation('TEST', '1m', df, initial_balance=100.0, leverage=1, strategy_parameters=params)
    res_b = sim.run_simulation('TEST', '1m', df, initial_balance=1000.0, leverage=1, strategy_parameters=params)
    res_c = sim.run_simulation('TEST', '1m', df, initial_balance=100.0, leverage=5, strategy_parameters=params)

    pct_a = float(res_a.get('profit_percentage', 0.0))
    pct_b = float(res_b.get('profit_percentage', 0.0))
    pct_c = float(res_c.get('profit_percentage', 0.0))

    # same leverage -> profit percentages should be approximately equal
    assert abs(pct_a - pct_b) < 1e-6

    # increased leverage should scale profit percentage roughly linearly
    assert abs(pct_c - pct_a * 5) < 1e-6
