import pandas as pd
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer


def make_toy_df(n=50):
    idx = pd.date_range('2025-01-01', periods=n, freq='5T')
    df = pd.DataFrame({
        'open': [100 + (i%10)*0.2 for i in range(n)],
        'high': [100 + (i%10)*0.2 + 0.1 for i in range(n)],
        'low': [100 + (i%10)*0.2 - 0.1 for i in range(n)],
        'close': [100 + (i%10)*0.2 for i in range(n)],
        'volume': [100 + (i%5)*5 for i in range(n)],
    }, index=idx)
    return df


def test_generate_signals_deterministic_cached_vs_runtime():
    df = make_toy_df()
    analyzer = StrategyAnalyzer()
    params = {'fast_ema_period':3,'slow_ema_period':5,'enable_volume_momentum':True,'volume_avg_period':5,'volume_spike_factor':1.4,'enable_sr_filter':True}
    # runtime: calculate indicators inside generate path
    df_runtime_ind = analyzer.calculate_indicators(df.copy(), params)
    sig_runtime = analyzer.generate_signals(df_runtime_ind.copy(), params)

    # cached path: precompute and then call generate_signals on cached frame
    df_cached = analyzer.calculate_indicators(df.copy(), params)
    sig_cached = analyzer.generate_signals(df_cached.copy(), params)

    # compare buy/sell signals equality
    assert sig_runtime['buy_signal'].equals(sig_cached['buy_signal'])
    assert sig_runtime['sell_signal'].equals(sig_cached['sell_signal'])


def test_generate_signals_reproducible_on_repeats():
    df = make_toy_df()
    analyzer = StrategyAnalyzer()
    params = {'fast_ema_period':3,'slow_ema_period':5,'enable_volume_momentum':True,'volume_avg_period':5,'volume_spike_factor':1.4,'enable_sr_filter':True}
    df_a = analyzer.calculate_indicators(df.copy(), params)
    s1 = analyzer.generate_signals(df_a.copy(), params)
    s2 = analyzer.generate_signals(df_a.copy(), params)
    assert s1['buy_signal'].equals(s2['buy_signal'])
    assert s1['sell_signal'].equals(s2['sell_signal'])


if __name__ == '__main__':
    test_generate_signals_deterministic_cached_vs_runtime()
    test_generate_signals_reproducible_on_repeats()
    print('Signal determinism tests passed')
