import os, sys
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer

symbol = 'PIPPINUSDT'
df_path = os.path.join('data', f"{symbol}_5m.csv")
if not os.path.exists(df_path):
    print('data file missing', df_path)
    sys.exit(1)

df = pd.read_csv(df_path, parse_dates=[0], index_col=0)
# target time from image (approx)
target = pd.to_datetime('2025-11-30 17:31:00')
# find nearest index
if target in df.index:
    idx = target
else:
    # find nearest by absolute difference
    diffs = abs(df.index - target)
    idx = df.index[diffs.argmin()]
print('Using index:', idx)

# load analyzer and compute indicators
analyzer = StrategyAnalyzer()
params = {'fast_ema_period':3, 'slow_ema_period':5, 'enable_volume_momentum': True, 'volume_avg_period':20, 'volume_spike_factor':1.6}

df2 = analyzer.calculate_indicators(df, params)
df2 = analyzer.generate_signals(df2, params)

# compute vol_med_10 and vol_mult like simulator
lookback = 10
med_col = f"vol_med_{lookback}"
if med_col not in df2.columns:
    df2[med_col] = df2['volume'].rolling(window=lookback, min_periods=1).median()
if 'vol_mult' not in df2.columns:
    df2['vol_mult'] = df2.apply(lambda r: (float(r['volume'])/float(r[med_col])) if pd.notna(r.get(med_col)) and float(r[med_col])>0 else 0.0, axis=1)

row = df2.loc[idx]
print(row[['open','high','low','close','volume']])
print('ema_fast', row.get('ema_fast_3'), 'ema_slow', row.get('ema_slow_5'))
print('VolumeSpike', row.get('VolumeSpike'), 'AboveVWAP', row.get('AboveVWAP'))
print('vol_mult', row.get('vol_mult'))
print('buy_signal', row.get('buy_signal'))

# Also show next bars to see price movement
print('\nNext 5 bars:')
print(df2[['open','high','low','close','volume']].iloc[list(df2.index.get_indexer([idx]))[0]: list(df2.index.get_indexer([idx]))[0]+5])
