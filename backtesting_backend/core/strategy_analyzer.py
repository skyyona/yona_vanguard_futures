from typing import Dict, Any
import pandas as pd
from typing import Dict, Any
import pandas as pd
try:
    import pandas_ta as ta
except Exception:
    import numpy as np

    # Lightweight fallback implementations so the backtesting backend can start
    def ema(series: pd.Series, length: int = 9) -> pd.Series:
        return series.ewm(span=length, adjust=False).mean()

    def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        fast_ema = series.ewm(span=fast, adjust=False).mean()
        slow_ema = series.ewm(span=slow, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        df = pd.DataFrame({
            f"MACD_{fast}_{slow}_{signal}": macd_line,
            f"MACDs_{fast}_{slow}_{signal}": signal_line,
            f"MACDh_{fast}_{slow}_{signal}": hist,
        })
        return df

    def stochrsi(series: pd.Series, length: int = 14) -> pd.DataFrame:
        delta = series.diff()
        up = delta.clip(lower=0.0)
        down = -1 * delta.clip(upper=0.0)
        ma_up = up.rolling(window=length, min_periods=1).mean()
        ma_down = down.rolling(window=length, min_periods=1).mean()
        rs = ma_up / (ma_down.replace(0, np.nan))
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.fillna(0)
        min_rsi = rsi.rolling(window=length, min_periods=1).min()
        max_rsi = rsi.rolling(window=length, min_periods=1).max()
        denom = (max_rsi - min_rsi).replace(0, np.nan)
        stochrsi_k = ((rsi - min_rsi) / denom) * 100
        df = pd.DataFrame({f"STOCHRSIk_{length}_{length}_3_3": stochrsi_k})
        return df

    # expose a minimal shim object so later code can call `ta.ema` / `ta.macd` / `ta.stochrsi`
    class _TaShim:
        pass

    ta = _TaShim()
    ta.ema = ema
    ta.macd = macd
    ta.stochrsi = stochrsi


class StrategyAnalyzer:
    """Calculate indicators and generate basic signals for strategies."""

    def __init__(self):
        pass

    def calculate_indicators(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Add indicators to DataFrame using pandas-ta or fallback implementations.

        Expected params may include EMA periods, Stoch RSI params, MACD params, etc.
        """
        df = df.copy()
        fast = int(params.get("fast_ema_period", 9))
        slow = int(params.get("slow_ema_period", 21))

        # EMA
        df[f"ema_fast_{fast}"] = ta.ema(df["close"], length=fast)
        df[f"ema_slow_{slow}"] = ta.ema(df["close"], length=slow)

        # Stoch RSI
        try:
            stoch = ta.stochrsi(df["close"], length=int(params.get("stoch_length", 14)))
            if isinstance(stoch, pd.DataFrame):
                df["stochrsi_k"] = stoch["STOCHRSIk_14_14_3_3"] if "STOCHRSIk_14_14_3_3" in stoch else stoch.iloc[:, 0]
        except Exception:
            df["stochrsi_k"] = None

        # MACD
        try:
            macd = ta.macd(df["close"])
            if isinstance(macd, pd.DataFrame):
                df["macd"] = macd.iloc[:, 0]
        except Exception:
            df["macd"] = None

        # Optional multi-timeframe trend filter (e.g., 15min EMA alignment)
        try:
            if params.get("enable_trend_filter"):
                trend_tf = params.get("trend_tf", "15T")
                long_fast = int(params.get("trend_fast", 50))
                long_slow = int(params.get("trend_slow", 100))

                # try to obtain a datetime index
                df_t = df.copy()
                if not pd.api.types.is_datetime64_any_dtype(df_t.index):
                    if "timestamp" in df_t.columns:
                        df_t.index = pd.to_datetime(df_t["timestamp"], unit="ms", errors="coerce")
                    else:
                        # cannot compute multi-TF trend without datetime index
                        df["trend_ok"] = True
                        return df

                # resample to requested timeframe and compute EMAs
                res = df_t["close"].resample(trend_tf).last().dropna()
                if len(res) >= max(long_fast, long_slow):
                    ema_fast_long = res.ewm(span=long_fast, adjust=False).mean()
                    ema_slow_long = res.ewm(span=long_slow, adjust=False).mean()
                    trend_df = pd.DataFrame({"ema_fast_long": ema_fast_long, "ema_slow_long": ema_slow_long})
                    # map trend info back to original rows by forward-fill
                    trend_df = trend_df.reindex(df_t.index, method="ffill")
                    df["trend_ok"] = trend_df["ema_fast_long"] > trend_df["ema_slow_long"]
                else:
                    df["trend_ok"] = True
        except Exception:
            df["trend_ok"] = True

        # Optional global session labeling/filtering: simple UTC-based sessions
        try:
            if params.get("enable_session_filter"):
                # ensure datetime index
                df_s = df.copy()
                if not pd.api.types.is_datetime64_any_dtype(df_s.index):
                    if "timestamp" in df_s.columns:
                        df_s.index = pd.to_datetime(df_s["timestamp"], unit="ms", errors="coerce")
                    else:
                        df["session"] = None
                        df["session_ok"] = True
                        return df

                # define simple session buckets (UTC hours)
                def _session_of_hour(h: int):
                    if 0 <= h < 8:
                        return "asia"
                    if 8 <= h < 16:
                        return "europe"
                    return "us"

                sessions = df_s.index.hour.map(_session_of_hour)
                df["session"] = sessions.values
                allowed = params.get("allowed_sessions", ["asia", "europe", "us"]) or ["asia", "europe", "us"]
                df["session_ok"] = df["session"].isin(allowed)
        except Exception:
            df["session"] = None
            df["session_ok"] = True
        
        # Advanced Volume Momentum features (optional)
        try:
            if params.get("enable_volume_momentum"):
                avg_period = int(params.get("volume_avg_period", 20))
                spike_factor = float(params.get("volume_spike_factor", 1.8))
                df = self.calculate_advanced_volume_momentum(df, avg_period=avg_period, spike_factor=spike_factor)
        except Exception:
            # if volume features fail, continue without them
            df["AvgVolume"] = None
            df["VolumeSpike"] = 0
            df["VWAP"] = None
            df["AboveVWAP"] = None

        # Support/Resistance level identification (optional)
        try:
            if params.get("enable_sr_detection"):
                # prefer higher timeframe input via params or default to 15m
                lookback = int(params.get("sr_lookback_period", 100))
                num_levels = int(params.get("sr_num_levels", 3))
                supports, resistances = self.identify_support_resistance(df, lookback_period=lookback, num_levels=num_levels)
                # store flattened lists in dataframe-level columns for downstream use
                df.attrs["supports"] = supports
                df.attrs["resistances"] = resistances
        except Exception:
            df.attrs["supports"] = []
            df.attrs["resistances"] = []
        return df

    def calculate_advanced_volume_momentum(self, df: pd.DataFrame, avg_period: int = 20, spike_factor: float = 1.5) -> pd.DataFrame:
        """
        Add AvgVolume, VolumeSpike, VWAP, AboveVWAP to df. Uses past-only rolling averages to avoid lookahead.
        """
        df = df.copy()
        # Ensure volume column exists; prefer NaN to avoid false positives
        if "volume" not in df.columns:
            df["volume"] = pd.NA

        # ensure volume is numeric float (coerce NaN/NA) so rolling works
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").astype(float)

        # rolling mean excluding current bar (shifted) - preserves lookback safety
        df["AvgVolume"] = df["volume"].rolling(window=avg_period, min_periods=1).mean().shift(1)

        # Volume spike flag on current bar (compare raw volume to past avg)
        # require both volume and AvgVolume present and a small min threshold to avoid false positives
        min_avg_vol = 1e-6
        df["VolumeSpike"] = (
            df["volume"].notna()
            & df["AvgVolume"].notna()
            & (df["AvgVolume"] > min_avg_vol)
            & (df["volume"] > df["AvgVolume"] * spike_factor)
        ).astype(int)

        # VWAP cumulative calculation using Typical Price * Volume divided by cumulative volume
        # define typical price
        tp = None
        if all(c in df.columns for c in ("high", "low", "close")):
            tp = (df["high"] + df["low"] + df["close"]) / 3.0
        elif "close" in df.columns:
            tp = df["close"]
        else:
            tp = pd.Series([0] * len(df), index=df.index)

        # compute cumulative sums with optional session-reset to avoid session bleed
        # determine grouping key for session resets
        groups = None
        if pd.api.types.is_datetime64_any_dtype(df.index):
            groups = df.index.normalize()
        else:
            if "timestamp" in df.columns:
                ts = pd.to_datetime(df["timestamp"], unit="ms", errors="coerce")
                groups = ts.dt.normalize()
            elif "open_time" in df.columns:
                ts = pd.to_datetime(df["open_time"], unit="ms", errors="coerce")
                groups = ts.dt.normalize()

        if groups is not None:
            cum_vp = (tp * df["volume"]).groupby(groups).cumsum()
            cum_v = df["volume"].groupby(groups).cumsum().replace(0, pd.NA)
            df["VWAP"] = (cum_vp / cum_v).ffill()
        else:
            cum_vp = (tp * df["volume"]).cumsum()
            cum_v = df["volume"].cumsum().replace(0, pd.NA)
            df["VWAP"] = (cum_vp / cum_v).ffill()

        # AboveVWAP boolean
        try:
            df["AboveVWAP"] = (df["close"] > df["VWAP"]).astype(int)
        except Exception:
            df["AboveVWAP"] = 0

        return df

    def identify_support_resistance(self, df: pd.DataFrame, lookback_period: int = 50, num_levels: int = 3):
        """
        Identify candidate support and resistance levels from recent data.
        Returns (supports_list, resistances_list) sorted (supports descending, resistances ascending).
        """
        try:
            if len(df) < 3:
                return [], []

            df_temp = df.tail(lookback_period)
            highs = df_temp.get("high") if "high" in df_temp.columns else df_temp.get("close")
            lows = df_temp.get("low") if "low" in df_temp.columns else df_temp.get("close")

            supports = []
            resistances = []

            # detect pivot-like levels using only past information (no lookahead)
            # require short rising/falling sequences in past bars to mark local extrema
            for i in range(2, len(df_temp)):
                try:
                    # use only historical bars up to i (no i+1 usage)
                    if highs.iloc[i] > highs.iloc[i - 1] and highs.iloc[i - 1] > highs.iloc[i - 2]:
                        resistances.append(float(highs.iloc[i]))
                    if lows.iloc[i] < lows.iloc[i - 1] and lows.iloc[i - 1] < lows.iloc[i - 2]:
                        supports.append(float(lows.iloc[i]))
                except Exception:
                    continue

            # dedupe + round
            supports = sorted(list(set([round(s, 6) for s in supports])), reverse=True)
            resistances = sorted(list(set([round(r, 6) for r in resistances])))

            # pivot-based extras
            try:
                close = float(df_temp["close"].iloc[-1])
                high = float(df_temp["high"].iloc[-1]) if "high" in df_temp.columns else close
                low = float(df_temp["low"].iloc[-1]) if "low" in df_temp.columns else close
                pivot = (high + low + close) / 3.0
                r1 = (2 * pivot) - low
                s1 = (2 * pivot) - high
                r2 = pivot + (high - low)
                s2 = pivot - (high - low)
                supports_final = [s for s in supports if s < close]
                resistances_final = [r for r in resistances if r > close]
                supports_final = supports_final[:num_levels] + [round(s1, 6), round(s2, 6)]
                resistances_final = resistances_final[:num_levels] + [round(r1, 6), round(r2, 6)]
            except Exception:
                supports_final = supports[:num_levels]
                resistances_final = resistances[:num_levels]

            # final dedupe and size limit
            supports_set = sorted(list(set([round(s, 6) for s in supports_final])), reverse=True)[: (num_levels + 2)]
            resistances_set = sorted(list(set([round(r, 6) for r in resistances_final])))[: (num_levels + 2)]
            return supports_set, resistances_set
        except Exception:
            return [], []

    def generate_signals(self, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Generate buy/sell signals based on indicators and params."""
        df = df.copy()
        fast = int(params.get("fast_ema_period", 9))
        slow = int(params.get("slow_ema_period", 21))
        ema_fast_col = f"ema_fast_{fast}"
        ema_slow_col = f"ema_slow_{slow}"

        df["buy_signal"] = False
        df["sell_signal"] = False

        for i in range(1, len(df)):
            try:
                prev_fast = df.iloc[i - 1][ema_fast_col]
                prev_slow = df.iloc[i - 1][ema_slow_col]
                cur_fast = df.iloc[i][ema_fast_col]
                cur_slow = df.iloc[i][ema_slow_col]
            except Exception:
                continue

            # simple crossover rule for long entries
            if prev_fast is not None and prev_slow is not None and cur_fast is not None and cur_slow is not None:
                # respect trend filter and session filter if present
                trend_ok = True
                session_ok = True
                if "trend_ok" in df.columns:
                    try:
                        trend_ok = bool(df.iloc[i]["trend_ok"])
                    except Exception:
                        trend_ok = True
                if "session_ok" in df.columns:
                    try:
                        session_ok = bool(df.iloc[i]["session_ok"])
                    except Exception:
                        session_ok = True

                if trend_ok and session_ok:
                    # base EMA crossover
                    ema_gc = prev_fast <= prev_slow and cur_fast > cur_slow
                    ema_dc = prev_fast >= prev_slow and cur_fast < cur_slow

                    # optional volume momentum filter
                    vol_ok = True
                    try:
                        if params.get("enable_volume_momentum"):
                            # require VolumeSpike on current bar and VWAP confirmation for buys
                            vol_spike = bool(df.iloc[i].get("VolumeSpike", 0))
                            above_vwap = bool(df.iloc[i].get("AboveVWAP", 0))
                            # for buy require spike and above VWAP; for sell require spike and below VWAP
                            if ema_gc:
                                vol_ok = vol_spike and above_vwap
                            elif ema_dc:
                                # consider down-volume: price below VWAP and volume spike
                                vol_ok = vol_spike and (not above_vwap)
                    except Exception:
                        vol_ok = True

                    # optional support/resistance proximity filter
                    sr_ok = True
                    try:
                        if params.get("enable_sr_filter"):
                            # proximity threshold as relative fraction
                            prox = float(params.get("sr_proximity_threshold", 0.001))
                            # compute S/R using only historical bars up to current index to avoid lookahead
                            lookback = int(params.get("sr_lookback_period", 100))
                            num_levels = int(params.get("sr_num_levels", 3))
                            hist_df = df.iloc[: i + 1]
                            supports, resistances = self.identify_support_resistance(hist_df, lookback_period=lookback, num_levels=num_levels)
                            price = float(df.iloc[i]["close"]) if "close" in df.columns else None
                            if price is not None:
                                near_support = any((s is not None) and (abs(price - s) / max(1e-9, abs(s)) <= prox) for s in supports)
                                near_resistance = any((r is not None) and (abs(price - r) / max(1e-9, abs(r)) <= prox) for r in resistances)
                                # if near resistance, avoid new long entries; if near support, favor long
                                if ema_gc and near_resistance:
                                    sr_ok = False
                                if ema_gc and near_support:
                                    sr_ok = True
                                if ema_dc and near_support:
                                    sr_ok = False
                    except Exception:
                        sr_ok = True

                    if ema_gc and vol_ok and sr_ok:
                        df.at[df.index[i], "buy_signal"] = True
                    if ema_dc and vol_ok and sr_ok:
                        df.at[df.index[i], "sell_signal"] = True

        return df

    # --- New-listing heuristics helpers ---
    def _confidence_from_candles(self, num_candles: int, sim_min_candles: int = 200) -> float:
        """Return a confidence [0.0-1.0] proportional to available candle count.

        This simple linear scaling gives 0 for 0 candles and 1.0 when
        `num_candles >= sim_min_candles`.
        """
        try:
            if num_candles <= 0:
                return 0.0
            return min(1.0, float(num_candles) / float(sim_min_candles))
        except Exception:
            return 0.0

    def heuristics_for_new_listing(self, df: pd.DataFrame, engine_key: str = "alpha", sim_min_candles: int = 200) -> Dict[str, Any]:
        """Create lightweight executable parameters and a confidence score for newly-listed coins.

        Returns a dict with keys: `executable_parameters` (dict), `confidence` (0..1),
        and optional `notes` explaining the heuristic rationale.
        """
        num_candles = 0 if df is None else len(df)
        conf = self._confidence_from_candles(num_candles, sim_min_candles)

        # baseline defaults
        params = {
            "symbol": None,
            "interval": None,
            "leverage": 1,
            "position_size": 0.02,
            "stop_loss_pct": 0.01,
            "take_profit_pct": 0.0,
            "trailing_stop_pct": 0.0,
            "fee_pct": 0.001,
            "slippage_pct": 0.001,
            "no_compounding": True,
        }

        notes = []

        # if no data, return conservative defaults
        if num_candles == 0:
            notes.append("no candles available - returning conservative defaults")
            return {"executable_parameters": params, "confidence": conf, "notes": notes}

        # compute simple recent stats
        try:
            recent = df.tail(min(len(df), 20))
            vol_mean = float(recent["volume"].mean()) if "volume" in recent.columns else 0.0
            vol_last = float(recent.iloc[-1]["volume"]) if "volume" in recent.columns else 0.0
            price_last = float(recent.iloc[-1]["close"]) if "close" in recent.columns else None
        except Exception:
            vol_mean = 0.0
            vol_last = 0.0
            price_last = None

        # choose heuristic by engine_key
        if engine_key == "alpha":
            # volume spike strategy
            params.update({"fast_ema_period": 5, "slow_ema_period": 21, "stop_loss_pct": 0.02})
            if vol_mean > 0 and vol_last > vol_mean * 3:
                notes.append("recent volume spike detected - favor breakout/momentum sizing")
                params["position_size"] = 0.03
                conf = min(1.0, conf + 0.15)
            else:
                notes.append("no clear volume spike - conservative sizing")
        elif engine_key == "beta":
            # short EMA golden-cross
            params.update({"fast_ema_period": 3, "slow_ema_period": 8, "stop_loss_pct": 0.015})
            notes.append("short-period EMA cross setup for fast-reacting entry")
            if num_candles < 10:
                params["position_size"] = 0.01
                conf = conf * 0.7
        elif engine_key == "gamma":
            # pullback rebound
            params.update({"fast_ema_period": 9, "slow_ema_period": 21, "stop_loss_pct": 0.02})
            # detect simple pullback in last 10 bars
            try:
                look = df.tail(min(len(df), 10))["close"]
                if len(look) >= 3 and look.iloc[-1] > look.min() and (look.min() < look.iloc[-3]):
                    notes.append("recent shallow pullback followed by small rebound")
                    conf = min(1.0, conf + 0.1)
            except Exception:
                pass
        else:
            # fallback: keep baseline params
            notes.append("unknown engine key - using baseline heuristic")

        # round-number breakout modifier: if last price near integer/k-round, slightly increase sizing
        try:
            if price_last is not None:
                # check if price close to round number (e.g., 100, 1000) relative to magnitude
                magnitude = 10 ** (int(len(str(int(price_last))) - 1) if price_last >= 10 else 1)
                round_nearest = round(price_last / magnitude) * magnitude
                if abs(price_last - round_nearest) / max(1.0, price_last) < 0.005:
                    notes.append("price near round-number level - apply breakout bias")
                    params["position_size"] = min(0.05, params.get("position_size", 0.02) * 1.5)
                    conf = min(1.0, conf + 0.05)
        except Exception:
            pass

        return {"executable_parameters": params, "confidence": conf, "notes": notes}

    # --- New-listing specialized strategy generators ---
    def generate_volume_spike_scalping(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        """Volume spike scalping for new listings. Returns dict with name and executable_parameters."""
        out = {"name": "volume_spike_scalping", "executable_parameters": {}, "triggered": False}
        try:
            lookback = int(params.get("volume_spike_lookback_period", 20))
            mult = float(params.get("volume_spike_multiplier", 3.0))
            short_ema = int(params.get("spike_ema_short_period", 5))
            long_ema = int(params.get("spike_ema_long_period", 21))

            recent = df.tail(min(len(df), lookback))
            if recent.empty:
                return out

            vol_mean = float(recent["volume"].mean())
            vol_last = float(recent.iloc[-1]["volume"])
            close_last = float(recent.iloc[-1]["close"])
            open_last = float(recent.iloc[-1]["open"])

            # EMAs
            ema_short = ta.ema(df["close"], length=short_ema).iloc[-1]
            ema_short_prev = ta.ema(df["close"], length=short_ema).iloc[-2] if len(df) > 1 else ema_short
            ema_long = ta.ema(df["close"], length=long_ema).iloc[-1]

            # stoch rsi quick check
            stoch = None
            try:
                st = ta.stochrsi(df["close"], length=int(params.get("stoch_rsi_periods_short", 14)))
                if isinstance(st, pd.DataFrame):
                    stoch = st.iloc[:, 0].iloc[-1]
            except Exception:
                stoch = None

            # require multi-timeframe trend confirmation (15min) when available
            trend_ok = True
            try:
                trend_ok = self._multi_tf_trend_ok(df, tf=params.get("trend_tf", "15T"), long_fast=params.get("trend_fast", 50), long_slow=params.get("trend_slow", 100))
            except Exception:
                trend_ok = True

            if trend_ok and vol_last >= vol_mean * mult and close_last > open_last and close_last > ema_short and ema_short > ema_short_prev and close_last > ema_long:
                out["triggered"] = True
                out["executable_parameters"] = {
                    "enable_volume_spike_scalping": True,
                    "volume_spike_lookback_period": lookback,
                    "volume_spike_multiplier": mult,
                    "spike_ema_short_period": short_ema,
                    "spike_ema_long_period": long_ema,
                    "stoch_rsi_periods_short": int(params.get("stoch_rsi_periods_short", 14)),
                }
        except Exception:
            pass
        return out

    def generate_short_ema_gc_scalping(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        out = {"name": "short_ema_gc_scalping", "executable_parameters": {}, "triggered": False}
        try:
            short = int(params.get("ema_short_period_for_gc", 3))
            mid = int(params.get("ema_mid_period_for_gc", 5))
            mult = float(params.get("gc_volume_filter_multiplier", 1.5))
            stoch_thresh = float(params.get("gc_stoch_rsi_oversold_threshold", 30))

            if len(df) < max(short, mid) + 1:
                return out

            ema_short = ta.ema(df["close"], length=short)
            ema_mid = ta.ema(df["close"], length=mid)
            # check golden cross at last candle
            prev_s = ema_short.iloc[-2]
            prev_m = ema_mid.iloc[-2]
            cur_s = ema_short.iloc[-1]
            cur_m = ema_mid.iloc[-1]

            vol_last = float(df.iloc[-1]["volume"])
            vol_mean = float(df.tail(min(len(df), 20))["volume"].mean())

            st = None
            try:
                stf = ta.stochrsi(df["close"], length=int(params.get("stoch_rsi_periods_short", 14)))
                if isinstance(stf, pd.DataFrame):
                    st = stf.iloc[:, 0].iloc[-1]
            except Exception:
                st = None

            # require trend_ok (short-term) to avoid counter-trend GCs
            try:
                trend_ok = self._multi_tf_trend_ok(df, tf=params.get("trend_tf", "15T"), long_fast=params.get("trend_fast", 50), long_slow=params.get("trend_slow", 100))
            except Exception:
                trend_ok = True

            if trend_ok and prev_s <= prev_m and cur_s > cur_m and vol_last >= vol_mean * mult and (st is None or st > stoch_thresh):
                out["triggered"] = True
                out["executable_parameters"] = {
                    "enable_short_ema_gc_scalping": True,
                    "ema_short_period_for_gc": short,
                    "ema_mid_period_for_gc": mid,
                    "gc_volume_filter_multiplier": mult,
                    "gc_stoch_rsi_oversold_threshold": stoch_thresh,
                }
        except Exception:
            pass
        return out

    def generate_initial_pullback_rebound(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        out = {"name": "initial_pullback_rebound", "executable_parameters": {}, "triggered": False}
        try:
            lookback = int(params.get("pullback_swing_high_lookback", 10))
            depth = float(params.get("pullback_depth_pct", 0.03))
            ema_p = int(params.get("pullback_ema_period", 9))
            stoch_thresh = float(params.get("rebound_stoch_rsi_oversold_threshold", 30))
            vol_mult = float(params.get("rebound_volume_confirmation_multiplier", 1.5))

            if len(df) < lookback + 2:
                return out

            recent = df.tail(lookback)
            swing_high = recent["high"].max()
            last_close = float(df.iloc[-1]["close"])
            pullback_pct = (swing_high - last_close) / swing_high if swing_high > 0 else 0.0

            ema_val = ta.ema(df["close"], length=ema_p).iloc[-1]
            vol_last = float(df.iloc[-1]["volume"])
            vol_mean = float(df.tail(min(len(df), 20))["volume"].mean())

            st = None
            try:
                stf = ta.stochrsi(df["close"], length=int(params.get("stoch_rsi_periods_short", 14)))
                if isinstance(stf, pd.DataFrame):
                    st = stf.iloc[:, 0].iloc[-1]
            except Exception:
                st = None

            # require trend confirmation and detect pullback then rebound above EMA
            try:
                trend_ok = self._multi_tf_trend_ok(df, tf=params.get("trend_tf", "15T"), long_fast=params.get("trend_fast", 50), long_slow=params.get("trend_slow", 100))
            except Exception:
                trend_ok = True

            if trend_ok and pullback_pct >= depth and last_close > ema_val and (st is None or st <= stoch_thresh) and vol_last >= vol_mean * vol_mult:
                out["triggered"] = True
                out["executable_parameters"] = {
                    "enable_initial_pullback_rebound": True,
                    "pullback_swing_high_lookback": lookback,
                    "pullback_depth_pct": depth,
                    "pullback_ema_period": ema_p,
                    "rebound_stoch_rsi_oversold_threshold": stoch_thresh,
                    "rebound_volume_confirmation_multiplier": vol_mult,
                }
        except Exception:
            pass
        return out

    def generate_round_number_breakout(self, df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
        out = {"name": "round_number_breakout", "executable_parameters": {}, "triggered": False}
        try:
            min_dist = float(params.get("breakout_min_distance_pct", 0.01))
            vol_mult = float(params.get("breakout_volume_multiplier", 2.0))
            min_body = float(params.get("min_breakout_candle_body_pct", 0.005))
            confirm_candles = int(params.get("breakout_confirmation_candles", 1))

            last_close = float(df.iloc[-1]["close"])
            # derive round numbers by magnitude
            mag = 10 ** (len(str(int(last_close))) - 1 if last_close >= 10 else 1)
            round_level = round(last_close / mag) * mag
            prev_close = float(df.iloc[-2]["close"]) if len(df) > 1 else last_close
            # breakout if previously below and now above by min_dist
            pct_move = (last_close - round_level) / max(1.0, round_level)
            vol_last = float(df.iloc[-1]["volume"])
            vol_mean = float(df.tail(min(len(df), 20))["volume"].mean())
            body = abs(last_close - float(df.iloc[-1]["open"])) / max(1.0, last_close)

            try:
                trend_ok = self._multi_tf_trend_ok(df, tf=params.get("trend_tf", "15T"), long_fast=params.get("trend_fast", 50), long_slow=params.get("trend_slow", 100))
            except Exception:
                trend_ok = True

            if trend_ok and prev_close < round_level and last_close >= round_level * (1.0 + min_dist) and vol_last >= vol_mean * vol_mult and body >= min_body:
                out["triggered"] = True
                out["executable_parameters"] = {
                    "enable_round_number_breakout": True,
                    "round_number_levels": [round_level],
                    "breakout_min_distance_pct": min_dist,
                    "breakout_volume_multiplier": vol_mult,
                    "min_breakout_candle_body_pct": min_body,
                    "breakout_confirmation_candles": confirm_candles,
                }
        except Exception:
            pass
        return out

    def generate_new_listing_strategies(self, df: pd.DataFrame, base_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Return a dict mapping engine_key -> list of strategy dicts detected for this df."""
        base = base_params or {}
        res = {"alpha": [], "beta": [], "gamma": [], "delta": []}
        try:
            # volume spike
            vs = self.generate_volume_spike_scalping(df, base)
            if vs.get("triggered"):
                res.setdefault("alpha", []).append(vs)

            # short ema gc
            gc = self.generate_short_ema_gc_scalping(df, base)
            if gc.get("triggered"):
                res.setdefault("beta", []).append(gc)

            # pullback rebound
            pr = self.generate_initial_pullback_rebound(df, base)
            if pr.get("triggered"):
                res.setdefault("gamma", []).append(pr)

            # round number breakout
            rb = self.generate_round_number_breakout(df, base)
            if rb.get("triggered"):
                res.setdefault("delta", []).append(rb)
        except Exception:
            pass
        return res

    def _multi_tf_trend_ok(self, df: pd.DataFrame, tf: str = "15T", long_fast: int = 50, long_slow: int = 100) -> bool:
        """Return True if higher-timeframe EMA trend indicates bullishness.

        Resamples `close` to timeframe `tf`, computes EMAs of lengths `long_fast` and `long_slow` and
        returns True if ema_fast > ema_slow on the latest resampled candle.
        """
        try:
            if 'open_time' not in df.columns:
                return True
            df_t = df.copy()
            # convert open_time (ms) to datetime index
            df_t.index = pd.to_datetime(df_t['open_time'], unit='ms', utc=True)
            # resample
            res = df_t['close'].resample(tf).last().dropna()
            if len(res) < max(3, int(long_fast/2)):
                return True
            ema_fast = res.ewm(span=long_fast, adjust=False).mean()
            ema_slow = res.ewm(span=long_slow, adjust=False).mean()
            return ema_fast.iloc[-1] > ema_slow.iloc[-1]
        except Exception:
            return True
