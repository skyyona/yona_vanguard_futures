import json
import os
import sqlite3
import pandas as pd
import datetime as dt
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer

OUT = 'C:/Users/User/new/instrument_jelly_out.txt'

def load_klines(db_path, symbol, interval, start_ms=None, end_ms=None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if start_ms is None or end_ms is None:
        cur.execute("SELECT MIN(open_time), MAX(open_time) FROM klines WHERE symbol=? AND interval=?", (symbol, interval))
        r = cur.fetchone()
        if not r or r[0] is None:
            conn.close()
            return None
        start_ms, end_ms = r[0], r[1]
    cur.execute(
        "SELECT open_time, open, high, low, close, volume, close_time FROM klines WHERE symbol=? AND interval=? AND open_time BETWEEN ? AND ? ORDER BY open_time",
        (symbol, interval, start_ms, end_ms),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["open_time","open","high","low","close","volume","close_time"])
    return df


def iso(ts_ms):
    try:
        return dt.datetime.fromtimestamp(ts_ms/1000, tz=dt.timezone.utc).isoformat()
    except Exception:
        return str(ts_ms)


def main():
    with open('..\\api_jelly.json','r',encoding='utf8') as f:
        api = json.load(f)
    data = api.get('data',{})
    symbol = data.get('symbol')
    interval = data.get('interval')
    params = data.get('best_parameters',{})

    # load klines (fallback to full range)
    # resolve to project-level backtest DB used by the backend service
    db = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'yona_backtest.db'))
    df = load_klines(db, symbol, interval)
    if df is None or df.empty:
        print('No klines for symbol')
        return

    analyzer = StrategyAnalyzer()
    # ensure timestamp index for session/trend logic
    if 'open_time' in df.columns:
        df.index = pd.to_datetime(df['open_time'], unit='ms', utc=True)

    # compute indicators
    df_ind = analyzer.calculate_indicators(df, params)
    df_sig = analyzer.generate_signals(df_ind, params)

    # Compute vol avg (20) and vol_mult per simulate code
    avg_period = int(params.get('volume_avg_period',20))
    df_sig['AvgVolume'] = df_sig['volume'].rolling(window=avg_period, min_periods=1).mean().shift(1)
    df_sig['vol_mult'] = df_sig.apply(lambda r: (float(r['volume']) / float(r['AvgVolume'])) if (r.get('AvgVolume') and r['AvgVolume']>0) else 0.0, axis=1)

    # Write detailed per-candle trace
    with open(OUT,'w',encoding='utf8') as out:
        out.write(f'Instrumenting {symbol} {interval} rows={len(df_sig)}\n')
        out.write('index,timestamp,open,high,low,close,volume,ema_fast,ema_slow,stochrsi_k,VolumeSpike,AvgVolume,vol_mult,VWAP,AboveVWAP,trend_ok,session_ok,ema_gc,ema_dc,buy_signal,sell_signal,vol_ok,sr_ok\n')
        for i in range(1, len(df_sig)):
            row = df_sig.iloc[i]
            prev = df_sig.iloc[i-1]
            ema_fast_col = f"ema_fast_{int(params.get('fast_ema_period',9))}"
            ema_slow_col = f"ema_slow_{int(params.get('slow_ema_period',21))}"
            prev_fast = prev.get(ema_fast_col)
            prev_slow = prev.get(ema_slow_col)
            cur_fast = row.get(ema_fast_col)
            cur_slow = row.get(ema_slow_col)

            trend_ok = bool(row.get('trend_ok', True))
            session_ok = bool(row.get('session_ok', True))
            stoch = row.get('stochrsi_k', None)
            vol_spike = bool(row.get('VolumeSpike', 0))
            avg_vol = row.get('AvgVolume')
            vol_mult = row.get('vol_mult')
            vwap = row.get('VWAP') if 'VWAP' in row else None
            above_vwap = bool(row.get('AboveVWAP', 0))
            buy_signal = bool(row.get('buy_signal', False))
            sell_signal = bool(row.get('sell_signal', False))

            ema_gc = False
            ema_dc = False
            if prev_fast is not None and prev_slow is not None and cur_fast is not None and cur_slow is not None:
                ema_gc = (prev_fast <= prev_slow and cur_fast > cur_slow)
                ema_dc = (prev_fast >= prev_slow and cur_fast < cur_slow)

            # volume ok logic
            vol_ok = True
            if params.get('enable_volume_momentum'):
                if ema_gc:
                    vol_ok = vol_spike and above_vwap
                elif ema_dc:
                    vol_ok = vol_spike and (not above_vwap)

            # sr_ok logic
            sr_ok = True
            if params.get('enable_sr_filter'):
                prox = float(params.get('sr_proximity_threshold', 0.001))
                lookback = int(params.get('sr_lookback_period',100))
                num_levels = int(params.get('sr_num_levels',3))
                hist_df = df_sig.iloc[:i+1]
                supports, resistances = analyzer.identify_support_resistance(hist_df, lookback_period=lookback, num_levels=num_levels)
                price = float(row['close']) if 'close' in row else None
                near_support = any((s is not None) and (abs(price - s) / max(1e-9, abs(s)) <= prox) for s in supports)
                near_resistance = any((r is not None) and (abs(price - r) / max(1e-9, abs(r)) <= prox) for r in resistances)
                if ema_gc and near_resistance:
                    sr_ok = False
                if ema_gc and near_support:
                    sr_ok = True
                if ema_dc and near_support:
                    sr_ok = False

            # write
            idx = df_sig.index[i]
            ts = iso(int(row['open_time']) if 'open_time' in row else int(idx.timestamp()*1000))
            out.write(','.join([str(i), ts, str(row.get('open')), str(row.get('high')), str(row.get('low')), str(row.get('close')), str(row.get('volume')), str(cur_fast), str(cur_slow), str(stoch), str(int(vol_spike)), str(avg_vol), str(vol_mult), str(vwap), str(int(above_vwap)), str(int(trend_ok)), str(int(session_ok)), str(int(ema_gc)), str(int(ema_dc)), str(int(buy_signal)), str(int(sell_signal)), str(int(vol_ok)), str(int(sr_ok))]) + '\n')

    print('Instrumented run complete, output ->', OUT)

if __name__ == '__main__':
    main()
