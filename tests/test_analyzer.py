import pandas as pd
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer


def make_df(prices, start_ts="2025-01-01"):
    idx = pd.date_range(start_ts, periods=len(prices), freq="T")
    return pd.DataFrame({"close": prices}, index=idx)


def test_trend_filter_column_and_behavior():
    analyzer = StrategyAnalyzer()
    prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
    df = make_df(prices)

    params = {"enable_trend_filter": True, "trend_tf": "3T", "trend_fast": 2, "trend_slow": 4}
    df2 = analyzer.calculate_indicators(df, params)
    assert "trend_ok" in df2.columns

    df3 = analyzer.generate_signals(df2, {"fast_ema_period": 2, "slow_ema_period": 4})
    # ensure buy_signal column exists
    assert "buy_signal" in df3.columns
    assert "sell_signal" in df3.columns

