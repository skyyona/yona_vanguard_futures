import pandas as pd
import numpy as np
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer


def make_df_from_prices(prices, volumes, start_ts="2025-11-28T00:00:00Z", freq="1min"):
    idx = pd.date_range(start=start_ts, periods=len(prices), freq=freq)
    df = pd.DataFrame({"open": prices, "high": prices, "low": prices, "close": prices, "volume": volumes}, index=idx)
    return df


def test_sequential_causality_volume_vwap():
    sa = StrategyAnalyzer()
    prices = [10, 10, 11, 11, 12, 12, 12]
    vols = [1, 2, 1, 5, 1, 1, 10]
    df = make_df_from_prices(prices, vols)
    # compute full indicators
    full = sa.calculate_advanced_volume_momentum(df.copy(), avg_period=3, spike_factor=1.5)

    # now compute stepwise and compare each index
    for i in range(len(df)):
        part = sa.calculate_advanced_volume_momentum(df.iloc[: i + 1].copy(), avg_period=3, spike_factor=1.5)
        # compare the last row of partial to the corresponding row in full
        f_row = full.iloc[i]
        p_row = part.iloc[-1]
        # VolumeSpike should match
        assert int(f_row["VolumeSpike"]) == int(p_row["VolumeSpike"]) or (pd.isna(f_row["VolumeSpike"]) and pd.isna(p_row["VolumeSpike"]))
        # VWAP should match when enough data exists or be NaN consistently
        if pd.isna(f_row["VWAP"]) and pd.isna(p_row["VWAP"]):
            continue
        assert np.isclose(f_row["VWAP"], p_row["VWAP"], equal_nan=True)


def test_vwap_edge_cases_missing_index_and_nan_volume():
    sa = StrategyAnalyzer()
    prices = [10, 10, 10, 20]
    vols = [1, pd.NA, 2, 1]
    # create df without datetime index (simulate raw API frame)
    df = pd.DataFrame({"open": prices, "high": prices, "low": prices, "close": prices, "volume": vols})
    # should not raise
    out = sa.calculate_advanced_volume_momentum(df.copy(), avg_period=2, spike_factor=1.5)
    # VWAP may be NaN where volume missing but function should return a column
    assert "VWAP" in out.columns
    # VolumeSpike should be integer-like column; entries with NaN volume should be 0
    assert (out["VolumeSpike"].fillna(0).isin([0, 1]).all())
