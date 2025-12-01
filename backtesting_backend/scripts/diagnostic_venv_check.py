import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
out = {}

# pandas_ta
try:
    import pandas_ta as pta
    out['pandas_ta_version'] = getattr(pta, '__version__', 'unknown')
except Exception as e:
    out['pandas_ta_error'] = str(e)

# calculate_indicators
try:
    import pandas as pd
    from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
    df = pd.DataFrame({'open_time': range(240), 'close':[100 + i*0.2 for i in range(240)]})
    an = StrategyAnalyzer()
    try:
        df_ind = an.calculate_indicators(df, {'fast_ema_period':9,'slow_ema_period':21,'stoch_length':14})
        out['indicator_columns'] = df_ind.columns.tolist()
        out['indicator_sample_tail'] = df_ind.tail(3).fillna('NaN').to_dict(orient='records')
    except Exception as e:
        out['calculate_error'] = str(e)
except Exception as e:
    out['indicator_setup_error'] = str(e)

print(json.dumps(out, ensure_ascii=False, indent=2))
