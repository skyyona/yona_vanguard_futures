import pandas as pd
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer


def make_toy_df(n=30):
    # create rising close and constant volume to test rolling/shift behavior
    idx = pd.date_range('2025-01-01', periods=n, freq='5T')
    df = pd.DataFrame({
        'open': [100 + i*0.1 for i in range(n)],
        'high': [100 + i*0.1 + 0.5 for i in range(n)],
        'low': [100 + i*0.1 - 0.5 for i in range(n)],
        'close': [100 + i*0.1 for i in range(n)],
        'volume': [100.0 + (i%5)*10 for i in range(n)],
    }, index=idx)
    return df


def test_avgvolume_shift():
    df = make_toy_df(30)
    analyzer = StrategyAnalyzer()
    params = {'enable_volume_momentum': True, 'volume_avg_period': 5, 'volume_spike_factor': 1.5}
    out = analyzer.calculate_advanced_volume_momentum(df.copy(), avg_period=5, spike_factor=1.5)
    # AvgVolume should equal past 5 bars mean shifted by 1 (i.e., at index i, AvgVolume == mean of volumes up to i-1)
    for i in range(1, len(out)):
        expected = out['volume'].iloc[max(0, i-5):i].mean()
        # Our implementation uses rolling(...).mean().shift(1) so expected matches
        if pd.isna(out['AvgVolume'].iloc[i]):
            # allow NaN for first rows
            continue
        assert abs(out['AvgVolume'].iloc[i] - expected) < 1e-6


def test_vwap_cumulative_no_lookahead():
    df = make_toy_df(30)
    analyzer = StrategyAnalyzer()
    out = analyzer.calculate_advanced_volume_momentum(df.copy(), avg_period=5, spike_factor=1.5)
    # VWAP at index i should be computed from cumulative up to i (no future data). So VWAP[i] equals (sum(tp*vol)/sum(vol)) up to i
    for i in range(len(out)):
        tp = (out['high'] + out['low'] + out['close'])/3.0
        cum_vp = (tp * out['volume']).iloc[:i+1].sum()
        cum_v = out['volume'].iloc[:i+1].sum()
        if cum_v == 0:
            continue
        expected = cum_vp / cum_v
        if pd.isna(out['VWAP'].iloc[i]):
            continue
        assert abs(out['VWAP'].iloc[i] - expected) < 1e-6


def test_volume_spike_boolean():
    df = make_toy_df(30)
    analyzer = StrategyAnalyzer()
    out = analyzer.calculate_advanced_volume_momentum(df.copy(), avg_period=3, spike_factor=1.1)
    # VolumeSpike should be 1 only when volume > AvgVolume * spike_factor and AvgVolume > small threshold
    for i in range(len(out)):
        v = out['volume'].iloc[i]
        avg = out['AvgVolume'].iloc[i]
        if pd.isna(avg) or avg <= 1e-6:
            # expected 0
            assert out['VolumeSpike'].iloc[i] in (0, 0.0, False)
            continue
        expected = 1 if v > avg * 1.1 else 0
        assert int(out['VolumeSpike'].iloc[i]) == expected


if __name__ == '__main__':
    test_avgvolume_shift()
    test_vwap_cumulative_no_lookahead()
    test_volume_spike_boolean()
    print('Lookahead unit tests passed')
