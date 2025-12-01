import sys
import os
import pandas as pd
import numpy as np
import time

# ensure repository root is on PYTHONPATH for local imports
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer

# Create synthetic 1m klines for 200 minutes
now = int(time.time() * 1000)
minutes = 200
open_times = [now - (minutes - i) * 60 * 1000 for i in range(minutes)]

# base price ascending slightly
prices = np.linspace(1.0, 1.2, minutes) + np.random.normal(0, 0.002, minutes)
opens = prices + np.random.normal(0, 0.001, minutes)
closes = prices + np.random.normal(0, 0.001, minutes)
highs = np.maximum(opens, closes) + 0.001
lows = np.minimum(opens, closes) - 0.001
volumes = np.ones(minutes) * 100.0

# insert a volume spike at the end
volumes[-1] = volumes[-2] * 10
closes[-1] = closes[-2] * 1.01

df = pd.DataFrame({
    'open_time': open_times,
    'open': opens,
    'high': highs,
    'low': lows,
    'close': closes,
    'volume': volumes,
})

sa = StrategyAnalyzer()

# base params (will be supplemented by analyzer defaults)
base = {
    'volume_spike_lookback_period': 20,
    'volume_spike_multiplier': 3.0,
    'spike_ema_short_period': 5,
    'spike_ema_long_period': 21,
    'stoch_rsi_periods_short': 8,

    'ema_short_period_for_gc': 3,
    'ema_mid_period_for_gc': 5,
    'gc_volume_filter_multiplier': 1.5,
    'gc_stoch_rsi_oversold_threshold': 35,

    'pullback_swing_high_lookback': 12,
    'pullback_depth_pct': 0.03,
    'pullback_ema_period': 9,
    'rebound_stoch_rsi_oversold_threshold': 30,
    'rebound_volume_confirmation_multiplier': 1.5,

    'breakout_min_distance_pct': 0.01,
    'breakout_volume_multiplier': 2.0,
    'min_breakout_candle_body_pct': 0.003,
    'breakout_confirmation_candles': 1,
}

print('Running new-listing strategy generators on synthetic data...')
strategies = sa.generate_new_listing_strategies(df, base)

for engine, lst in strategies.items():
    print(f'Engine: {engine} -> {len(lst)} detected strategies')
    for s in lst:
        print('  -', s.get('name'), s.get('triggered'), s.get('executable_parameters'))

# Quick assertions
assert isinstance(strategies, dict)
# at least one strategy should detect the volume spike (alpha)
alpha_list = strategies.get('alpha', [])
if not any(s.get('name') == 'volume_spike_scalping' and s.get('triggered') for s in alpha_list):
    print('WARNING: volume_spike_scalping not detected - inspect thresholds')
else:
    print('PASS: volume_spike_scalping detected')

print('Test script finished')

# --- Additional crafted tests ---
def make_df_from_arrays(open_times, opens, highs, lows, closes, volumes):
    return pd.DataFrame({
        'open_time': open_times,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes,
    })

def test_short_ema_gc():
    # create data where short EMA crosses above mid EMA at last candle
    mins = 30
    now_ms = int(time.time() * 1000)
    ots = [now_ms - (mins - i) * 60 * 1000 for i in range(mins)]
    # build prices: flat then small ramp to cause short EMA to cross
    prices = np.ones(mins) * 1.0
    # force a short-term cross: set previous bar low, last bar very high
    prices[-3] = 1.0
    prices[-2] = 0.8
    prices[-1] = 2.0
    opens = prices + np.random.normal(0, 0.0005, mins)
    closes = prices + np.random.normal(0, 0.0005, mins)
    highs = np.maximum(opens, closes) + 0.001
    lows = np.minimum(opens, closes) - 0.001
    vols = np.ones(mins) * 50
    vols[-1] = vols[-2] * 3.0  # volume spike at GC

    df_gc = make_df_from_arrays(ots, opens, highs, lows, closes, vols)
    params_gc = base.copy()
    params_gc.update({'ema_short_period_for_gc': 3, 'ema_mid_period_for_gc': 5, 'gc_volume_filter_multiplier': 1.5, 'gc_stoch_rsi_oversold_threshold': 0})
    res = sa.generate_short_ema_gc_scalping(df_gc, params_gc)
    print('Short EMA GC test -> triggered:', res.get('triggered'))
    if not res.get('triggered'):
        # diagnostic: compute EMAs
        l_s = int(params_gc.get('ema_short_period_for_gc', 3))
        l_m = int(params_gc.get('ema_mid_period_for_gc', 5))
        ema_s = df_gc['close'].ewm(span=l_s, adjust=False).mean()
        ema_m = df_gc['close'].ewm(span=l_m, adjust=False).mean()
        print('EMA short last2:', ema_s.iloc[-2], ema_s.iloc[-1])
        print('EMA mid   last2:', ema_m.iloc[-2], ema_m.iloc[-1])
        print('last volumes:', df_gc['volume'].iloc[-3:].tolist())
    assert res.get('triggered') is True, 'Short EMA GC should have been triggered'

def test_pullback_rebound():
    # create data with a prior swing high, pullback, then rebound above EMA with volume
    mins = 50
    now_ms = int(time.time() * 1000)
    ots = [now_ms - (mins - i) * 60 * 1000 for i in range(mins)]
    prices = np.linspace(1.0, 1.05, mins)
    # insert swing high within the lookback window (near the tail)
    swing_idx = mins - 12
    prices[swing_idx] = prices[swing_idx] + 0.3
    # create pullback at tail
    for i in range(mins-6, mins-3):
        prices[i] = prices[i] - 0.05
    # make a stronger pullback and a clear rebound at final candle
    prices[-6] = prices[-6] - 0.08
    prices[-5] = prices[-5] - 0.06
    prices[-4] = prices[-4] - 0.04
    prices[-3] = prices[-3] - 0.02
    prices[-2] = prices[-2] * 1.02
    prices[-1] = prices[-2] * 1.08

    opens = prices + np.random.normal(0, 0.0005, mins)
    closes = prices + np.random.normal(0, 0.0005, mins)
    highs = np.maximum(opens, closes) + 0.001
    lows = np.minimum(opens, closes) - 0.001
    vols = np.ones(mins) * 80
    vols[-1] = vols[-2] * 3.0

    df_pb = make_df_from_arrays(ots, opens, highs, lows, closes, vols)
    params_pb = base.copy()
    params_pb.update({'pullback_swing_high_lookback': 12, 'pullback_depth_pct': 0.02, 'pullback_ema_period': 9, 'rebound_volume_confirmation_multiplier': 1.5, 'rebound_stoch_rsi_oversold_threshold': 100})
    res = sa.generate_initial_pullback_rebound(df_pb, params_pb)
    print('Pullback rebound test -> triggered:', res.get('triggered'))
    if not res.get('triggered'):
        swing_high = df_pb.tail(int(params_pb.get('pullback_swing_high_lookback', 12)))['high'].max()
        last_close = float(df_pb.iloc[-1]['close'])
        pullback_pct = (swing_high - last_close) / swing_high if swing_high>0 else 0.0
        l_p = int(params_pb.get('pullback_ema_period', 9))
        ema_val = df_pb['close'].ewm(span=l_p, adjust=False).mean().iloc[-1]
        vol_last = float(df_pb.iloc[-1]['volume'])
        vol_mean = float(df_pb.tail(min(len(df_pb), 20))['volume'].mean())
        print('swing_high, last_close, pullback_pct:', swing_high, last_close, pullback_pct)
        print('ema_val:', ema_val)
        print('vol_last, vol_mean:', vol_last, vol_mean)
    assert res.get('triggered') is True, 'Pullback rebound should have been triggered'

def test_round_number_breakout():
    # create data where previous close below round level and last close breaks above with volume/body
    mins = 40
    now_ms = int(time.time() * 1000)
    ots = [now_ms - (mins - i) * 60 * 1000 for i in range(mins)]
    base_price = 99.0
    prices = np.ones(mins) * base_price
    # previous close below round level (100)
    prices[-2] = 99.5
    # breakout: last close above 100 + 1% distance
    prices[-1] = 100.0 * 1.02

    # ensure a bullish body on the last candle (open significantly lower than close)
    opens = prices + np.random.normal(0, 0.001, mins)
    opens[-1] = prices[-1] * 0.98
    closes = prices + np.random.normal(0, 0.001, mins)
    highs = np.maximum(opens, closes) + 0.002
    lows = np.minimum(opens, closes) - 0.002
    vols = np.ones(mins) * 60
    vols[-1] = vols[-2] * 3.0

    df_rb = make_df_from_arrays(ots, opens, highs, lows, closes, vols)
    params_rb = base.copy()
    params_rb.update({'breakout_min_distance_pct': 0.01, 'breakout_volume_multiplier': 2.0, 'min_breakout_candle_body_pct': 0.001})
    res = sa.generate_round_number_breakout(df_rb, params_rb)
    print('Round number breakout test -> triggered:', res.get('triggered'))
    assert res.get('triggered') is True, 'Round number breakout should have been triggered'


print('\nRunning additional crafted unit tests...')
try:
    test_short_ema_gc()
    print('PASS: Short EMA Golden Cross test')
except AssertionError as e:
    print('FAIL: Short EMA GC test:', e)

try:
    test_pullback_rebound()
    print('PASS: Pullback Rebound test')
except AssertionError as e:
    print('FAIL: Pullback Rebound test:', e)

try:
    test_round_number_breakout()
    print('PASS: Round Number Breakout test')
except AssertionError as e:
    print('FAIL: Round Number Breakout test:', e)

print('All crafted tests finished')
