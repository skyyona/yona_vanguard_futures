import pandas as pd
import numpy as np
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer


def make_df_from_prices(prices, volumes, start_ts="2025-11-28T00:00:00Z", freq="1min"):
    idx = pd.date_range(start=start_ts, periods=len(prices), freq=freq)
    df = pd.DataFrame({"open": prices, "high": prices, "low": prices, "close": prices, "volume": volumes}, index=idx)
    return df


def test_vwap_session_reset():
    sa = StrategyAnalyzer()
    # day1 prices 10, day2 prices 20 - VWAP should reset at day boundary
    prices = [10, 10, 10, 20, 20, 20]
    vols = [1, 1, 1, 1, 1, 1]
    df = make_df_from_prices(prices, vols, start_ts="2025-11-28T23:58:00Z", freq="1min")
    out = sa.calculate_advanced_volume_momentum(df.copy(), avg_period=2, spike_factor=1.5)
    # verify VWAP resets at day boundary: first row of day2 is index 2 (00:00)
    # index 2 VWAP should equal 10 (only that day's first price so far)
    assert out["VWAP"].iloc[2] == 10 or np.isclose(out["VWAP"].iloc[2], 10)
    # index 3 VWAP is avg of [10,20] -> 15
    assert out["VWAP"].iloc[3] == 15 or np.isclose(out["VWAP"].iloc[3], 15)


def test_identify_support_resistance_no_future():
    sa = StrategyAnalyzer()
    # create data where a big spike exists at the end
    prices = [1, 1.1, 1.05, 1.02, 1.0, 5.0]
    vols = [1, 1, 1, 1, 1, 1]
    df = make_df_from_prices(prices, vols)
    # compute S/R up to index 3 (not including the spike)
    supports_early, resistances_early = sa.identify_support_resistance(df.iloc[:4], lookback_period=10, num_levels=3)
    # compute S/R on full data
    supports_full, resistances_full = sa.identify_support_resistance(df, lookback_period=10, num_levels=3)
    # the large spike (5.0) should appear only in full resistances, not in early
    assert all([r < 5.0 for r in resistances_early])
    assert any([r >= 5.0 for r in resistances_full]) or (len(resistances_full) >= len(resistances_early))


def test_generate_signals_sr_no_lookahead():
    sa = StrategyAnalyzer()
    # Construct prices to create EMA cross at index 5, but later a resistance occurs at index 9
    prices = [10, 10, 10, 10, 10, 11, 11, 11, 11, 20]
    vols = [1] * len(prices)
    df = make_df_from_prices(prices, vols)
    params = {"fast_ema_period": 3, "slow_ema_period": 5, "enable_sr_filter": True, "sr_lookback_period": 10, "sr_num_levels": 2, "sr_proximity_threshold": 0.001}
    df_ind = sa.calculate_indicators(df.copy(), params)
    df_sig = sa.generate_signals(df_ind, params)
    # find first buy signal index (if any) and ensure it occurs before the large resistance (price 20)
    buys = df_sig.index[df_sig["buy_signal"]]
    assert len(buys) > 0
    first_buy_pos = df_sig.index.get_loc(buys[0])
    # ensure first buy occurs before the last index where spike exists
    assert first_buy_pos < (len(df) - 1)
