import pandas as pd
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer


def make_df_with_ohlcv(n=30):
    idx = pd.date_range("2025-01-01", periods=n, freq="min")
    import random
    random.seed(0)
    prices = [100 + i * 0.1 + (random.random() - 0.5) * 0.2 for i in range(n)]
    vols = [100 + (random.random() * 200) for _ in range(n)]
    opens = [p - 0.05 for p in prices]
    highs = [p + 0.05 for p in prices]
    lows = [p - 0.1 for p in prices]
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": prices, "volume": vols}, index=idx)


def test_calculate_advanced_volume_momentum_calendar():
    df = make_df_with_ohlcv(50)
    an = StrategyAnalyzer()
    out = an.calculate_advanced_volume_momentum(df.copy(), avg_period=5, spike_factor=1.1)
    # expected columns present
    assert "AvgVolume" in out.columns
    assert "VolumeSpike" in out.columns
    assert "VWAP" in out.columns
    assert "AboveVWAP" in out.columns
    # AvgVolume should be finite for non-empty df
    assert out["AvgVolume"].notna().sum() > 0


def test_identify_support_resistance_basic():
    df = make_df_with_ohlcv(60)
    an = StrategyAnalyzer()
    supports, resistances = an.identify_support_resistance(df, lookback_period=40, num_levels=2)
    # returns lists
    assert isinstance(supports, list)
    assert isinstance(resistances, list)


def test_generate_signals_with_filters():
    df = make_df_with_ohlcv(60)
    an = StrategyAnalyzer()
    params = {
        "fast_ema_period": 3,
        "slow_ema_period": 5,
        "enable_volume_momentum": True,
        "volume_avg_period": 5,
        "volume_spike_factor": 1.1,
        "enable_sr_detection": True,
        "sr_lookback_period": 40,
        "sr_num_levels": 2,
        "enable_sr_filter": True,
        "sr_proximity_threshold": 0.01,
    }
    df2 = an.calculate_indicators(df.copy(), params)
    out = an.generate_signals(df2, params)
    # ensure the output contains buy_signal/sell_signal columns
    assert "buy_signal" in out.columns
    assert "sell_signal" in out.columns
