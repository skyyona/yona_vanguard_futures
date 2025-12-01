import pandas as pd
import matplotlib.pyplot as plt
import os

os.makedirs('results/traces/pippinusdt/plots', exist_ok=True)

p='data/PIPPINUSDT_5m.csv'
df=pd.read_csv(p, parse_dates=[0], index_col=0)
start='2025-11-21 12:00:00'
end='2025-11-21 13:00:00'
win=df[(df.index>=start)&(df.index<=end)].copy()
print('Window rows:', len(win))
print(win.to_string())

# compute rolling avg vol (past only)
df['AvgVolume'] = df['volume'].rolling(window=20, min_periods=1).mean().shift(1)
win = win.assign(AvgVolume=df['AvgVolume'].reindex(win.index))
win['vol_mult'] = win['volume'] / win['AvgVolume']

print('\nVolume multipliers:')
print(win[['volume','AvgVolume','vol_mult']].to_string())

# plot close
plt.figure(figsize=(10,4))
plt.plot(win.index, win['close'], marker='o', label='close')
plt.title('PIPPINUSDT 5m 2025-11-21 12:00-13:00')
plt.axvline(pd.to_datetime('2025-11-21 12:30:00'), color='red', linestyle='--', label='12:30')
plt.legend()
plt.tight_layout()
plt.savefig('results/traces/pippinusdt/plots/event_2025-11-21_12-00_13-00_close.png')

# plot volume
plt.figure(figsize=(10,2))
plt.bar(win.index, win['volume'], width=0.02)
plt.axvline(pd.to_datetime('2025-11-21 12:30:00'), color='red', linestyle='--')
plt.tight_layout()
plt.savefig('results/traces/pippinusdt/plots/event_2025-11-21_12-00_13-00_vol.png')

print('\nSaved plots to results/traces/pippinusdt/plots/')
