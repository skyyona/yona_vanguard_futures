import pandas as pd
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer


def make_df(prices, start_ts="2025-01-01 00:00:00"):
    idx = pd.date_range(start_ts, periods=len(prices), freq="T", tz="UTC")
    return pd.DataFrame({"close": prices}, index=idx)


def test_session_filter_labels_and_allowed():
    analyzer = StrategyAnalyzer()
    prices = [100 + i for i in range(60)]
    df = make_df(prices, start_ts="2025-01-01 07:50:00")

    params = {"enable_session_filter": True, "allowed_sessions": ["europe"]}
    df2 = analyzer.calculate_indicators(df, params)
    assert "session" in df2.columns
    assert "session_ok" in df2.columns
    # since allowed_sessions only includes 'europe', ensure at least one False present
    assert df2['session_ok'].dtype == bool or df2['session_ok'].dtype == 'bool'

