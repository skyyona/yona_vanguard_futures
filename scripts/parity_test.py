"""
Parity test: run legacy core_run_backtest and new BacktestExecutor on identical synthetic candles
and produce a JSON diff report (parity_report.json) plus a short stdout summary.

Read-only: creates no modifications to production code; writes report to workspace.
"""
import os
import sys
import json
from datetime import datetime, timedelta
import pandas as pd
import logging
from dataclasses import asdict
import time

# Ensure repository root is on sys.path for local imports
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# The project packages live under the `yona_vanguard_futures` folder. Add it to path if present.
YVF = os.path.join(WORKSPACE_ROOT, "yona_vanguard_futures")
if os.path.isdir(YVF) and YVF not in sys.path:
    sys.path.insert(0, YVF)
elif WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

# Legacy core runner
from backtesting_backend.core.strategy_core import run_backtest as core_run_backtest
# instrumentation hooks: we'll wrap these at runtime to capture per-step details
from backtesting_backend.core import strategy_conditions

# New orchestrator/backtest executor
from backend.core.new_strategy.orchestrator import StrategyOrchestrator, OrchestratorConfig
from backend.core.new_strategy.backtest_adapter import BacktestExecutor, BacktestConfig

# Set up an in-memory log capture (non-invasive) to collect step-level log messages
captured_logs = []

class ListLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
        except Exception:
            msg = str(record.__dict__.get('msg', ''))
        captured_logs.append({
            "time": getattr(record, "asctime", None) or record.created,
            "level": record.levelname,
            "logger": record.name,
            "message": msg,
        })

log_handler = ListLogHandler()
log_handler.setLevel(logging.DEBUG)
fmt = logging.Formatter("%Y-%m-%d %H:%M:%S - [%(levelname)s] - %(message)s")
log_handler.setFormatter(fmt)
root_logger = logging.getLogger()
root_logger.addHandler(log_handler)


def make_synthetic_df(rows=30, start_price=100.0, spike_at=10):
    ts0 = datetime.utcnow().replace(microsecond=0)
    rows_list = []
    price = start_price
    for i in range(rows):
        # small random-walk deterministic pattern
        if i == spike_at:
            price = price * 1.05
        else:
            price = price * (1.0 + (0.001 if i % 5 != 0 else -0.002))
        rows_list.append({
            "timestamp": ts0 + timedelta(minutes=i),
            "open": price * 0.995,
            "high": price * 1.002,
            "low": price * 0.990,
            "close": price,
            "volume": 100 + i,
            "quote_volume": (100 + i) * price,
            "trades": 5 + (i % 3),
        })
    df = pd.DataFrame(rows_list)
    return df


def run_legacy(df, params):
    # core_run_backtest(symbol, interval, df, initial_balance, leverage, params)
    # Non-invasive instrumentation: wrap generate_signals to capture a compact snapshot
    legacy_signal_snapshots = []

    try:
        import backtesting_backend.core.strategy_simulator as sim_mod
        orig_gen = getattr(sim_mod, "generate_signals", None)

        def wrapped_generate_signals(dfin, p):
            # call the original (may be bound in the module)
            if orig_gen:
                df_out = orig_gen(dfin, p)
            else:
                df_out = strategy_conditions.generate_signals(dfin, p)
            try:
                cols = [c for c in ["close", "buy_signal", "sell_signal", "signal_score"] if c in df_out.columns]
                snap = df_out[cols].tail(50).to_dict(orient="list")
            except Exception:
                snap = {"error": "snapshot_failed"}
            legacy_signal_snapshots.append(snap)
            return df_out

        # patch the symbol used by StrategySimulator to ensure our wrapper is executed
        try:
            sim_mod.generate_signals = wrapped_generate_signals
        except Exception:
            strategy_conditions.generate_signals = wrapped_generate_signals
    except Exception:
        legacy_signal_snapshots = []

    try:
        res = core_run_backtest("TESTSYMBOL", "1m", df.copy(), params.get("initial_balance", 1000.0), params.get("leverage", 1), params)
    finally:
        try:
            # restore original binding where possible
            import backtesting_backend.core.strategy_simulator as sim_mod2
            if orig_gen is not None:
                sim_mod2.generate_signals = orig_gen
        except Exception:
            try:
                strategy_conditions.generate_signals = orig_gen
            except Exception:
                pass

    try:
        if isinstance(res, dict):
            res.setdefault("instrumentation", {})["legacy_signal_snapshots"] = legacy_signal_snapshots
    except Exception:
        pass

    return res


def run_new_adapter(df, params):
    # instantiate orchestrator with no real client (we'll inject candles)
    orch = StrategyOrchestrator(binance_client=None)
    # For parity testing: allow runtime override of thresholds via env vars
    try:
        min_override = os.environ.get('PARITY_MIN_ENTRY_SCORE')
        strong_override = os.environ.get('PARITY_STRONG_ENTRY_SCORE')
        if min_override is not None:
            orch.signal.config.min_entry_score = float(min_override)
        if strong_override is not None:
            orch.signal.config.strong_entry_score = float(strong_override)
    except Exception:
        pass
    # Prevent orchestrator from attempting live/API fetches during tests
    try:
        orch._ensure_fetch = lambda *a, **k: None
        orch._should_update_candle = lambda *a, **k: False
    except Exception:
        pass
    # Use the real MarketDataCache from data_fetcher so the orchestrator
    # sees the exact same API it expects (has_sufficient_data, get_latest_candles, ...)
    try:
        from backend.core.new_strategy.data_fetcher import MarketDataCache
        try:
            if not hasattr(orch, 'fetcher') or orch.fetcher is None:
                class _F:
                    pass
                orch.fetcher = _F()
        except Exception:
            pass
        orch.fetcher.cache = MarketDataCache()
        # Pre-fill cache with at least the required number of candles so
        # orchestrator.step() will not raise InsufficientDataError on startup.
        try:
            from backend.core.new_strategy.data_structures import Candle
            # interval ms mapping
            INTERVAL_MS = {"1m": 60 * 1000, "3m": 3 * 60 * 1000, "15m": 15 * 60 * 1000}
            # use first N rows to prefill (use indicator requirement 200 if available)
            required = getattr(orch.indicator, 'required_candles', 200)
            N = max(200, int(required))
            df_rows = df.copy().reset_index(drop=True)
            # build candle objects for each timeframe
            for interval_key in ["1m", "3m", "15m"]:
                interval_ms = INTERVAL_MS.get(interval_key, 60 * 1000)
                candles_list = []
                for i in range(min(N, len(df_rows))):
                    row = df_rows.iloc[i]
                    if hasattr(row['timestamp'], 'timestamp'):
                        open_time = int(row['timestamp'].timestamp() * 1000)
                    else:
                        open_time = int(row['timestamp'])
                    close_time = open_time + interval_ms - 1
                    c = Candle(
                        symbol=orch.cfg.symbol,
                        interval=interval_key,
                        open_time=open_time,
                        close_time=close_time,
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=float(row.get('volume') or 0.0),
                        quote_volume=float(row.get('quote_volume') or 0.0),
                        trades_count=int(row.get('trades') or 0),
                    )
                    candles_list.append(c)
                try:
                    orch.fetcher.cache.add_candles_bulk(candles_list)
                except Exception:
                    pass
        except Exception:
            pass
        # Prevent prepare_symbol from calling real client methods
        try:
            orch.exec.prepare_symbol = lambda *a, **k: True
        except Exception:
            pass
    except Exception:
        # fallback to no-op if import fails
        pass
    # small config for BacktestExecutor
    cfg = BacktestConfig(symbol="TESTSYMBOL", start_date="2025-01-01", end_date="2025-01-02",
                         initial_balance=params.get("initial_balance", 1000.0), leverage=params.get("leverage", 1),
                         commission_rate=params.get("fee_pct", 0.0004), slippage_rate=params.get("slippage_pct", 0.0001))
    # Use identical df for 1m/3m/15m for parity testing (deterministic)
    kl_1m = df.copy()
    kl_3m = df.copy()
    kl_15m = df.copy()

    # Non-invasive instrumentation: wrap orchestrator.step to capture step payloads
    orch_steps = []
    # Deeper instrumentation: capture indicator outputs, signal internals, risk decisions, and order results
    orch_steps_detailed = []
    try:
        orig_step = orch.step

        def wrapped_step(*a, **k):
            r = orig_step(*a, **k)
            try:
                orch_steps.append(r)
            except Exception:
                pass
            return r

        orch.step = wrapped_step
    except Exception:
        orch_steps = []

    # Wrap _compute_indicators to capture IndicatorSet values per interval
    try:
        orig_compute = orch._compute_indicators

        def wrapped_compute(interval):
            res = orig_compute(interval)
            try:
                from dataclasses import asdict
                ind = asdict(res)
            except Exception:
                try:
                    ind = res.__dict__
                except Exception:
                    ind = str(res)
            try:
                orch_steps_detailed.append({"type": "indicators", "interval": interval, "indicators": ind})
            except Exception:
                pass
            return res

        orch._compute_indicators = wrapped_compute
    except Exception:
        pass

    # Wrap signal.evaluate to capture inputs and outputs
    try:
        orig_signal_eval = orch.signal.evaluate

        def wrapped_signal_eval(*a, **k):
            # snapshot inputs (convert dataclasses where possible)
            def _safe(obj):
                try:
                    from dataclasses import asdict
                    return asdict(obj)
                except Exception:
                    try:
                        return obj.__dict__
                    except Exception:
                        return str(obj)

            input_snapshot = {}
            # positional args -> name them by position
            for i, v in enumerate(a):
                input_snapshot[f"arg_{i}"] = _safe(v)
            for k0, v0 in k.items():
                input_snapshot[k0] = _safe(v0)

            res = orig_signal_eval(*a, **k)
            try:
                from dataclasses import asdict
                out = asdict(res)
            except Exception:
                try:
                    out = res.__dict__
                except Exception:
                    out = str(res)

            try:
                orch_steps_detailed.append({"type": "signal", "input": input_snapshot, "result": out})
            except Exception:
                pass
            return res

        orch.signal.evaluate = wrapped_signal_eval
    except Exception:
        pass

    # Wrap signal._score_entry to capture per-component score breakdown (non-invasive)
    try:
        orig_score_entry = orch.signal._score_entry
        try:
            orig_fn_meta = {
                'repr': repr(orig_score_entry),
                'qualname': getattr(orig_score_entry, '__qualname__', None),
                'module': getattr(orig_score_entry, '__module__', None),
                'id': id(orig_score_entry),
                'bound_id': id(orig_score_entry),
                'func_id': id(getattr(orig_score_entry, '__func__', orig_score_entry)),
                'self_id': id(getattr(orig_score_entry, '__self__', None)),
            }
        except Exception:
            orig_fn_meta = {'repr': str(orig_score_entry)}

        def wrapped_score_entry(*a, **k):
            # best-effort component recomputation to show which checks contributed
            try:
                current_1m = a[0] if len(a) > 0 else k.get('current_1m')
                last_close = a[1] if len(a) > 1 else k.get('last_close')
                prev_1m = a[2] if len(a) > 2 else k.get('prev_1m')
                prev_3m = a[3] if len(a) > 3 else k.get('prev_3m')
                confirm_3m = a[4] if len(a) > 4 else k.get('confirm_3m')
            except Exception:
                current_1m = last_close = prev_1m = prev_3m = confirm_3m = None

            c = getattr(orch.signal, 'config', None)
            comps = {}
            calc_score = 0.0
            try:
                if current_1m is not None:
                    if getattr(current_1m, 'volume_spike', False):
                        comps['volume_spike'] = c.w_volume_spike
                        calc_score += c.w_volume_spike
                    else:
                        comps['volume_spike'] = 0.0

                    if getattr(current_1m, 'vwap', None) is not None and last_close is not None:
                        try:
                            if float(last_close) > float(current_1m.vwap):
                                comps['vwap_breakout'] = c.w_vwap_breakout
                                calc_score += c.w_vwap_breakout
                            else:
                                comps['vwap_breakout'] = 0.0
                        except Exception:
                            comps['vwap_breakout'] = 0.0
                    else:
                        comps['vwap_breakout'] = 0.0

                    # EMA alignment
                    e5 = getattr(current_1m, 'ema_5', None)
                    e10 = getattr(current_1m, 'ema_10', None)
                    e20 = getattr(current_1m, 'ema_20', None)
                    e60 = getattr(current_1m, 'ema_60', None)
                    e120 = getattr(current_1m, 'ema_120', None)
                    if all(v is not None for v in [e5, e10, e20, e60, e120]) and e5 > e10 > e20 > e60 > e120:
                        comps['ema_alignment'] = c.w_ema_alignment
                        calc_score += c.w_ema_alignment
                    else:
                        comps['ema_alignment'] = 0.0

                    # EMA20 rising vs prev_1m
                    if prev_1m is not None and getattr(prev_1m, 'ema_20', None) is not None and e20 is not None:
                        if e20 > prev_1m.ema_20:
                            comps['ema20_rising'] = c.w_consecutive_rise
                            calc_score += c.w_consecutive_rise
                        else:
                            comps['ema20_rising'] = 0.0
                    else:
                        comps['ema20_rising'] = 0.0

                    # 3m trend confirm
                    if confirm_3m is not None and getattr(confirm_3m, 'trend', None) in ('UPTREND', 'STRONG_UPTREND'):
                        comps['3m_trend_confirm'] = c.w_3m_trend_confirm
                        calc_score += c.w_3m_trend_confirm
                    else:
                        comps['3m_trend_confirm'] = 0.0

                    # MACD histogram rising
                    if prev_1m is not None and getattr(current_1m, 'macd_histogram', None) is not None and getattr(prev_1m, 'macd_histogram', None) is not None:
                        if current_1m.macd_histogram > prev_1m.macd_histogram:
                            comps['macd_hist_rising'] = c.w_bear_energy_fade
                            calc_score += c.w_bear_energy_fade
                        else:
                            comps['macd_hist_rising'] = 0.0
                    else:
                        comps['macd_hist_rising'] = 0.0

                    # MACD bullish/golden cross (simplified)
                    if getattr(current_1m, 'macd_line', None) is not None and getattr(current_1m, 'macd_signal', None) is not None:
                        if prev_1m is not None and getattr(prev_1m, 'macd_line', None) is not None and getattr(prev_1m, 'macd_signal', None) is not None:
                            if prev_1m.macd_line <= prev_1m.macd_signal and current_1m.macd_line > current_1m.macd_signal:
                                comps['macd_golden'] = c.w_macd_golden_cross
                                calc_score += c.w_macd_golden_cross
                            else:
                                comps['macd_golden'] = 0.0
                        elif current_1m.macd_line > current_1m.macd_signal:
                            comps['macd_bullish'] = min(c.w_macd_golden_cross, 10.0)
                            calc_score += min(c.w_macd_golden_cross, 10.0)
                        else:
                            comps['macd_bullish'] = 0.0
                    else:
                        comps['macd_bullish'] = 0.0

                    # RSI rebound
                    if prev_1m is not None and getattr(prev_1m, 'rsi_14', None) is not None and getattr(current_1m, 'rsi_14', None) is not None:
                        if prev_1m.rsi_14 < 35.0 and current_1m.rsi_14 > prev_1m.rsi_14:
                            comps['rsi_rebound'] = c.w_rsi_oversold_rebound
                            calc_score += c.w_rsi_oversold_rebound
                        else:
                            comps['rsi_rebound'] = 0.0
                    else:
                        comps['rsi_rebound'] = 0.0

                    # Stoch RSI 1m
                    stoch_ok = False
                    if getattr(current_1m, 'stoch_rsi_k', None) is not None and getattr(current_1m, 'stoch_rsi_d', None) is not None and current_1m.stoch_rsi_k > current_1m.stoch_rsi_d:
                        k = current_1m.stoch_rsi_k
                        if c.stoch_entry_min < k < c.stoch_entry_max:
                            stoch_ok = True
                            comps['stoch_1m'] = c.w_stoch_entry
                            calc_score += c.w_stoch_entry
                        else:
                            comps['stoch_1m'] = 0.0
                    else:
                        comps['stoch_1m'] = 0.0

                    # MTF stoch (best-effort)
                    if c.enable_mtf_stoch and confirm_3m is not None:
                        mtf_ok = False
                        if c.mtf_loose_mode:
                            if getattr(confirm_3m, 'stoch_rsi_k', None) is not None and getattr(confirm_3m, 'stoch_rsi_d', None) is not None and confirm_3m.stoch_rsi_k > confirm_3m.stoch_rsi_d and confirm_3m.stoch_rsi_k <= c.mtf_oversold_threshold:
                                mtf_ok = True
                        else:
                            if prev_1m and prev_3m and getattr(prev_1m, 'stoch_rsi_k', None) is not None and getattr(prev_1m, 'stoch_rsi_d', None) is not None and getattr(prev_3m, 'stoch_rsi_k', None) is not None and getattr(prev_3m, 'stoch_rsi_d', None) is not None:
                                one_min_cross = prev_1m.stoch_rsi_k <= prev_1m.stoch_rsi_d and current_1m.stoch_rsi_k > current_1m.stoch_rsi_d and prev_1m.stoch_rsi_k <= c.mtf_oversold_threshold
                                three_min_cross = prev_3m.stoch_rsi_k <= prev_3m.stoch_rsi_d and confirm_3m.stoch_rsi_k > confirm_3m.stoch_rsi_d and prev_3m.stoch_rsi_k <= c.mtf_oversold_threshold
                                if one_min_cross and three_min_cross:
                                    mtf_ok = True
                        if mtf_ok and stoch_ok:
                            comps['mtf_stoch'] = c.w_mtf_stoch
                            calc_score += c.w_mtf_stoch
                        else:
                            comps['mtf_stoch'] = 0.0

            except Exception as e:
                comps['error'] = str(e)

            # write a small per-invocation pre-call debug file to correlate instance/function ids
            try:
                import time
                pre_dbg = {
                    'ts': int(time.time() * 1000),
                    'orig_fn_meta': orig_fn_meta,
                    'orch_signal_id': id(getattr(orch, 'signal', None)),
                    'call_args_snapshot': {
                        'pos_args_count': len(a),
                        'kwargs_keys': list(k.keys()) if isinstance(k, dict) else None
                    }
                }
                pre_name = f"tmp_score_debug_call_pre_{pre_dbg['ts']}_{orig_fn_meta.get('id')}_{pre_dbg['orch_signal_id']}.json"
                with open(pre_name, 'w', encoding='utf-8') as _pf:
                    _pf.write(json.dumps(pre_dbg, ensure_ascii=False) + '\n')
            except Exception:
                pass

            # call original to get canonical score and triggers
            ret = None
            orig_score = None
            orig_triggers = []
            try:
                # record the exact args/kwargs we'll pass to the bound method
                try:
                    import time
                    orig_call_args = {'args': [], 'kwargs': {'current_1m': current_1m, 'last_close': last_close, 'prev_1m': prev_1m, 'prev_3m': prev_3m, 'confirm_3m': confirm_3m}}
                    orig_args_dbg = {'ts': int(time.time() * 1000), 'orig_fn_meta': orig_fn_meta, 'orch_signal_id': id(getattr(orch, 'signal', None)), 'call': orig_call_args}
                    orig_args_name = f"tmp_score_debug_call_origargs_{orig_args_dbg['ts']}_{orig_fn_meta.get('id')}_{orig_args_dbg['orch_signal_id']}.json"
                    with open(orig_args_name, 'w', encoding='utf-8') as _of:
                        _of.write(json.dumps(orig_args_dbg, default=str, ensure_ascii=False) + '\n')
                except Exception:
                    pass

                ret = orig_score_entry(
                    current_1m=current_1m,
                    last_close=last_close,
                    prev_1m=prev_1m,
                    prev_3m=prev_3m,
                    confirm_3m=confirm_3m,
                )
                # write immediate post-call debug to correlate return
                try:
                    import time
                    post_dbg = {'ts': int(time.time() * 1000), 'ret_repr': repr(ret), 'ret_type': type(ret).__name__, 'orig_fn_meta': orig_fn_meta, 'orch_signal_id': id(getattr(orch, 'signal', None))}
                    post_name = f"tmp_score_debug_call_post_{post_dbg['ts']}_{orig_fn_meta.get('id')}_{post_dbg['orch_signal_id']}.json"
                    with open(post_name, 'w', encoding='utf-8') as _pf:
                        _pf.write(json.dumps(post_dbg, ensure_ascii=False) + '\n')
                except Exception:
                    pass
            except Exception:
                # if the original raises, try to call again safely and capture whatever it returns
                try:
                    ret = orig_score_entry(
                        current_1m=current_1m,
                        last_close=last_close,
                        prev_1m=prev_1m,
                        prev_3m=prev_3m,
                        confirm_3m=confirm_3m,
                    )
                except Exception:
                    ret = None

            # If ret is still None, try calling the unbound function through the instance's class
            if ret is None:
                try:
                    cls = getattr(orch.signal, '__class__', None)
                    if cls is not None and hasattr(cls, '_score_entry'):
                        class_fn = getattr(cls, '_score_entry')
                        try:
                            # record the exact args/kwargs for the class-level call
                            try:
                                import time
                                class_call_dbg = {
                                    'ts': int(time.time() * 1000),
                                    'class_fn_meta': {'repr': repr(class_fn), 'id': id(class_fn)},
                                    'orch_signal_id': id(getattr(orch, 'signal', None)),
                                    'call': {
                                        'positional': [repr(orch.signal), repr(current_1m), repr(last_close), repr(prev_1m), repr(prev_3m), repr(confirm_3m)]
                                    }
                                }
                                class_args_name = f"tmp_score_debug_call_classargs_{class_call_dbg['ts']}_{class_call_dbg['class_fn_meta']['id']}_{class_call_dbg['orch_signal_id']}.json"
                                with open(class_args_name, 'w', encoding='utf-8') as _cf:
                                    _cf.write(json.dumps(class_call_dbg, ensure_ascii=False) + '\n')
                            except Exception:
                                pass

                            ret = class_fn(
                                orch.signal,
                                current_1m,
                                last_close,
                                prev_1m,
                                prev_3m,
                                confirm_3m,
                            )
                        except Exception:
                            # give up if this also fails
                            ret = None
                except Exception:
                    ret = None

            # normalize the canonical return into (orig_score, orig_triggers)
            try:
                if isinstance(ret, tuple) and len(ret) >= 1:
                    orig_score = ret[0]
                    orig_triggers = ret[1] if len(ret) > 1 else []
                elif hasattr(ret, 'score') or hasattr(ret, 'triggers'):
                    # object-like return
                    try:
                        orig_score = getattr(ret, 'score', None)
                    except Exception:
                        orig_score = None
                    try:
                        orig_triggers = getattr(ret, 'triggers', []) or []
                    except Exception:
                        orig_triggers = []
                elif isinstance(ret, (int, float)):
                    orig_score = ret
                    orig_triggers = []
                else:
                    # unknown/missing canonical value
                    orig_score = None
                    orig_triggers = []
            except Exception:
                orig_score = None
                orig_triggers = []

            try:
                # serialize args/kwargs safely for later 1:1 reconstruction
                import inspect

                def safe_serialize(v):
                    try:
                        from dataclasses import asdict
                        if hasattr(v, '__dataclass_fields__'):
                            return asdict(v)
                    except Exception:
                        pass
                    try:
                        # numeric strings -> floats
                        if isinstance(v, str):
                            try:
                                if v.replace('.', '', 1).isdigit():
                                    return float(v)
                            except Exception:
                                pass
                        if hasattr(v, '__dict__'):
                            return v.__dict__
                    except Exception:
                        pass
                    try:
                        # primitives are ok
                        return v
                    except Exception:
                        return str(v)

                # try to map positional args to parameter names when possible
                pos_named = []
                try:
                    sig = inspect.signature(orig_score_entry)
                    params = list(sig.parameters.keys())
                except Exception:
                    params = []

                for i, val in enumerate(a):
                    name = params[i] if i < len(params) else f'arg_{i}'
                    pos_named.append({'name': name, 'value': safe_serialize(val)})

                kwargs_serialized = {str(k0): safe_serialize(v0) for k0, v0 in k.items()} if isinstance(k, dict) else {'raw_kwargs': safe_serialize(k)}

                call_args = {
                    'pos_args_count': len(a),
                    'pos_args': pos_named,
                    'kwargs': kwargs_serialized,
                }

                # Prefer the canonical orig_score when available to make calc_total match engine
                canonical_total = orig_score if orig_score is not None else calc_score

                entry = {
                    "type": "signal_breakdown",
                    "components": comps,
                    "calc_total": canonical_total,
                    "orig_score": orig_score,
                    "orig_triggers": orig_triggers,
                    "call_args": call_args,
                    "_raw_ret": safe_serialize(ret),
                }
                orch_steps_detailed.append(entry)
                # If the canonical return was missing, write a small debug record
                try:
                    if orig_score is None or ret is None:
                        # try to capture class-level fallback info as well
                        class_meta = None
                        try:
                            cls = getattr(orch.signal, '__class__', None)
                            if cls is not None and hasattr(cls, '_score_entry'):
                                cf = getattr(cls, '_score_entry')
                                class_meta = {
                                    'repr': repr(cf),
                                    'qualname': getattr(cf, '__qualname__', None),
                                    'module': getattr(cf, '__module__', None),
                                    'id': id(cf),
                                }
                        except Exception:
                            class_meta = None

                        dbg = {
                            'call_args': call_args,
                            'ret_repr': repr(ret),
                            'ret_type': type(ret).__name__ if ret is not None else 'NoneType',
                            'orig_fn_meta': orig_fn_meta,
                            'class_fn_meta': class_meta,
                        }
                        with open('tmp_score_debug.jsonl', 'a', encoding='utf-8') as _dbgf:
                            _dbgf.write(json.dumps(dbg, ensure_ascii=False) + '\n')
                except Exception:
                    pass
            except Exception:
                pass
            # return original return value if available to preserve behavior
            try:
                return ret if ret is not None else (orig_score, orig_triggers)
            except Exception:
                return (orig_score, orig_triggers)

        orch.signal._score_entry = wrapped_score_entry
    except Exception:
        pass

    # Wrap risk.evaluate to capture risk outputs
    try:
        orig_risk_eval = orch.risk.evaluate

        def wrapped_risk_eval(*a, **k):
            res = orig_risk_eval(*a, **k)
            try:
                from dataclasses import asdict
                out = asdict(res) if res is not None else None
            except Exception:
                try:
                    out = res.__dict__ if res is not None else None
                except Exception:
                    out = str(res)
            try:
                orch_steps_detailed.append({"type": "risk", "input_args_count": len(a), "result": out})
            except Exception:
                pass
            # persist a small per-call debug file for easier offline inspection
            try:
                sig_meta = None
                try:
                    sig_meta = {"repr": repr(getattr(orch, 'signal', None)), "id": id(getattr(orch, 'signal', None))}
                except Exception:
                    sig_meta = repr(getattr(orch, 'signal', None))
                fname = f"tmp_risk_debug_{int(time.time()*1000)}_{sig_meta['id'] if isinstance(sig_meta, dict) else 'noid'}.json"
                with open(fname, 'w', encoding='utf-8') as _rf:
                    json.dump({"ts": int(time.time()*1000), "orch_signal": sig_meta, "args": [str(a), str(k)], "result": out}, _rf, ensure_ascii=False, indent=2)
            except Exception:
                pass
            return res

        orch.risk.evaluate = wrapped_risk_eval
    except Exception:
        pass

    # Wrap risk._energy_is_strong to capture last_signal vs threshold decisions
    try:
        if hasattr(orch.risk, '_energy_is_strong'):
            orig_energy = orch.risk._energy_is_strong

            def wrapped_energy_is_strong(last_signal):
                try:
                    thresh = getattr(orch.risk.config, 'extended_energy_score_threshold', None)
                    last_score = getattr(last_signal, 'score', None) if last_signal is not None else None
                    res = orig_energy(last_signal)
                    orch_steps_detailed.append({
                        'type': 'risk_energy_check',
                        'last_signal_score': last_score,
                        'threshold': thresh,
                        'result': bool(res)
                    })
                    try:
                        # write per-call energy check debug file
                        fname = f"tmp_risk_energy_check_{int(time.time()*1000)}_{id(getattr(orch, 'signal', None))}.json"
                        with open(fname, 'w', encoding='utf-8') as _ef:
                            json.dump({"ts": int(time.time()*1000), "last_signal_score": last_score, "threshold": thresh, "result": bool(res)}, _ef, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    return res
                except Exception as e:
                    orch_steps_detailed.append({'type': 'risk_energy_check', 'error': str(e)})
                    return orig_energy(last_signal)

            orch.risk._energy_is_strong = wrapped_energy_is_strong
    except Exception:
        pass

    # Wrap execution adapter methods to capture order results
    try:
        if hasattr(orch, 'exec') and orch.exec is not None:
            try:
                orig_place = orch.exec.place_market_long

                def wrapped_place_market_long(symbol, quantity):
                    res = orig_place(symbol, quantity)
                    try:
                        from dataclasses import asdict
                        ro = asdict(res)
                    except Exception:
                        try:
                            ro = res.__dict__
                        except Exception:
                            ro = str(res)
                    try:
                        orch_steps_detailed.append({"type": "order", "action": "place_market_long", "symbol": symbol, "requested_qty": quantity, "result": ro})
                    except Exception:
                        pass
                    return res

                orch.exec.place_market_long = wrapped_place_market_long
            except Exception:
                pass

            try:
                orig_close = orch.exec.close_market_long

                def wrapped_close_market_long(symbol):
                    res = orig_close(symbol)
                    try:
                        from dataclasses import asdict
                        ro = asdict(res)
                    except Exception:
                        try:
                            ro = res.__dict__
                        except Exception:
                            ro = str(res)
                    try:
                        orch_steps_detailed.append({"type": "order", "action": "close_market_long", "symbol": symbol, "result": ro})
                    except Exception:
                        pass
                    return res

                orch.exec.close_market_long = wrapped_close_market_long
            except Exception:
                pass
    except Exception:
        pass

    events_captured = []
    try:
        orch.set_event_callback(lambda ev: events_captured.append(ev))
    except Exception:
        pass

    execr = BacktestExecutor(orchestrator=orch, config=cfg, klines_1m=kl_1m, klines_3m=kl_3m, klines_15m=kl_15m)
    res = execr.run()

    try:
        if isinstance(res, dict):
            res.setdefault("instrumentation", {})["orchestrator_steps"] = orch_steps
            res.setdefault("instrumentation", {})["orchestrator_events"] = events_captured
            # include deep per-step instrumentation if collected
            try:
                res.setdefault("instrumentation", {})["orchestrator_steps_detailed"] = orch_steps_detailed
            except Exception:
                pass
    except Exception:
        pass

    return res


def summarize_and_diff(legacy_res, new_res):
    report = {
        "legacy": legacy_res,
        "new": new_res,
        "differences": {},
        "captured_logs": captured_logs,
    }

    # compare top-level metrics
    keys = ["profit", "profit_percentage", "final_balance", "total_trades", "win_rate", "max_drawdown_pct"]
    diffs = {}
    for k in keys:
        lv = legacy_res.get(k)
        nv = new_res.get(k)
        diffs[k] = {"legacy": lv, "new": nv, "diff": None}
        try:
            diffs[k]["diff"] = (nv - lv) if (isinstance(nv, (int, float)) and isinstance(lv, (int, float))) else None
        except Exception:
            diffs[k]["diff"] = None
    report["differences"]["summary_metrics"] = diffs

    # compare number of trades and per-trade net pnl lists when available
    legacy_trades = legacy_res.get("trades") or []
    new_trades = new_res.get("trades") or []
    report["differences"]["trade_counts"] = {"legacy": len(legacy_trades), "new": len(new_trades)}

    # per-trade comparison for first N trades
    N = min(10, len(legacy_trades), len(new_trades))
    trade_diffs = []
    for i in range(N):
        lt = legacy_trades[i]
        nt = new_trades[i]
        td = {"index": i}
        # compare net pnl keys if present
        lt_net = lt.get("net_pnl") or lt.get("pnl") or lt.get("gross_pnl")
        nt_net = nt.get("net_pnl") or nt.get("pnl") or nt.get("gross_pnl")
        td["legacy_net"] = lt_net
        td["new_net"] = nt_net
        try:
            td["diff"] = (nt_net - lt_net) if (lt_net is not None and nt_net is not None) else None
        except Exception:
            td["diff"] = None
        trade_diffs.append(td)
    report["differences"]["trade_sample"] = trade_diffs

    # small human summary
    summary = {
        "legacy_profit": legacy_res.get("profit"),
        "new_profit": new_res.get("profit"),
        "legacy_trades": len(legacy_trades),
        "new_trades": len(new_trades),
    }

    report_path = "parity_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print("Parity report written to", report_path)
    print("Summary:")
    print(json.dumps(summary, indent=2))
    return report_path


def compare_legacy_vs_new_snapshot(legacy_res, new_res, df):
    """Focused comparison: extract legacy entry candlestick (entry_index) and run
    legacy generate_signals on a small df slice and new SignalEngine.evaluate on
    matched IndicatorSet(s). Attach results under report.instrumentation.focused_comparison.
    """
    try:
        # locate entry index from legacy trades
        trades = legacy_res.get('trades') or []
        if not trades:
            return None
        entry_index = trades[0].get('entry_index', 0)

        # build a small df slice around the entry index (ensure bounds)
        start = max(0, entry_index - 5)
        end = min(len(df) - 1, entry_index + 1)
        df_slice = df.iloc[start:end+1].copy().reset_index(drop=True)

        # Run legacy generate_signals on the slice to get legacy output row
        legacy_out = None
        try:
            import backtesting_backend.core.strategy_simulator as sim_mod
            gen = getattr(sim_mod, 'generate_signals', None)
            if gen is None:
                from backtesting_backend.core import strategy_conditions as sc
                gen = sc.generate_signals
            legacy_df_out = gen(df_slice.copy(), {})
            # take the last row (corresponding to entry)
            legacy_out = None
            try:
                legacy_out = legacy_df_out.tail(1).to_dict(orient='records')[0]
            except Exception:
                legacy_out = str(legacy_df_out)
        except Exception as e:
            legacy_out = {'error': str(e)}

        # Prepare new SignalEngine inputs from new_res instrumentation if available
        focused = {
            'entry_index': entry_index,
            'legacy_signal_row': legacy_out,
            'new_evaluate': None,
            'signal_breakdown': None,
            'indicators_used': {},
        }

        try:
            # find indicators and breakdown in new_res instrumentation
            inst = new_res.get('instrumentation', {}) if isinstance(new_res, dict) else {}
            detailed = inst.get('orchestrator_steps_detailed') or []
            # find the last indicator block and breakdown near the start of the run
            # heuristic: pick the first 'signal' or 'signal_breakdown' we encounter
            curr_ind = None
            prev_ind = None
            prev_3m = None
            breakdown = None
            for item in detailed:
                if item.get('type') == 'indicators' and item.get('interval') == '1m':
                    # shift prev->curr
                    prev_ind = curr_ind
                    curr_ind = item.get('indicators')
                if item.get('type') == 'indicators' and item.get('interval') == '3m' and prev_3m is None:
                    prev_3m = item.get('indicators')
                if item.get('type') == 'signal_breakdown' and breakdown is None:
                    breakdown = item
                if item.get('type') == 'signal' and focused.get('new_evaluate') is None:
                    # capture signal result if present
                    focused['new_evaluate'] = item.get('result')
            focused['signal_breakdown'] = breakdown
            focused['indicators_used']['current_1m'] = curr_ind
            focused['indicators_used']['prev_1m'] = prev_ind
            focused['indicators_used']['prev_3m'] = prev_3m

            # construct IndicatorSet dataclasses for calling SignalEngine.evaluate
            try:
                from backend.core.new_strategy.data_structures import IndicatorSet
                from backend.core.new_strategy.signal_engine import SignalEngine
                # helper to convert dict -> IndicatorSet
                def dict_to_indicators(d):
                    if not d:
                        return None
                    kwargs = {k: v for k, v in d.items() if k in IndicatorSet.__annotations__}
                    # ensure symbol & timestamp exist
                    if 'symbol' not in kwargs:
                        kwargs['symbol'] = new_res.get('instrumentation', {}).get('orchestrator_steps', [{}])[0].get('symbol', 'BTCUSDT')
                    return IndicatorSet(**kwargs)

                current_1m = dict_to_indicators(curr_ind)
                prev_1m = dict_to_indicators(prev_ind)
                prev_3m = dict_to_indicators(prev_3m)

                # Prefer the last_close captured in the orchestrator 'signal' input (arg_1)
                # fallback to df_slice last row if not available
                sig_input_last = None
                try:
                    # try to get input arg_1 from the first 'signal' detailed entry we captured
                    for item in detailed:
                        if item.get('type') == 'signal' and isinstance(item.get('input'), dict):
                            sig_input_last = item.get('input').get('arg_1')
                            break
                except Exception:
                    sig_input_last = None

                try:
                    if sig_input_last is not None:
                        last_close = float(sig_input_last)
                    else:
                        last_close = float(df.iloc[entry_index]['close']) if entry_index < len(df) else float(df_slice['close'].iloc[-1])
                except Exception:
                    # final fallback
                    last_close = float(df_slice['close'].iloc[-1])

                se = SignalEngine()
                res = se.evaluate(current_1m=current_1m, last_close=last_close, prev_1m=prev_1m, prev_3m=prev_3m, confirm_3m=prev_3m, filter_15m=None, in_position=False)
                try:
                    focused['new_evaluate'] = asdict(res)
                except Exception:
                    # fallback: try dataclass conversion
                    try:
                        focused['new_evaluate'] = res.__dict__
                    except Exception:
                        focused['new_evaluate'] = str(res)
            except Exception as e:
                focused.setdefault('errors', []).append(str(e))
        except Exception as e:
            focused.setdefault('errors', []).append(str(e))

        # attach into parity_report.json
        try:
            rpt_path = 'parity_report.json'
            with open(rpt_path, 'r', encoding='utf-8') as f:
                rep = json.load(f)
        except Exception:
            rep = {'legacy': legacy_res, 'new': new_res}

        rep.setdefault('instrumentation', {})['focused_comparison'] = focused
        with open('parity_report.json', 'w', encoding='utf-8') as f:
            json.dump(rep, f, indent=2, ensure_ascii=False, default=str)

        return focused
    except Exception as e:
        return {'error': str(e)}


def compare_all_signals_in_report(df_rows=300, start_price=1000.0, spike_at=120):
    """Iterate `orchestrator_steps_detailed` in parity_report.json and for each
    'signal' entry recompute new SignalEngine.evaluate using nearby indicators,
    and compare against legacy generate_signals output (computed on the same synthetic df).
    Results are appended under `instrumentation.window_comparison`.
    """
    try:
        rpt_path = 'parity_report.json'
        with open(rpt_path, 'r', encoding='utf-8') as f:
            rep = json.load(f)
    except Exception as e:
        return {'error': 'cannot open parity_report.json', 'exc': str(e)}

    new_res = rep.get('new', {})
    detailed = new_res.get('instrumentation', {}).get('orchestrator_steps_detailed', []) if isinstance(new_res, dict) else []

    # regenerate the synthetic df deterministicly as main()
    df = make_synthetic_df(rows=df_rows, start_price=start_price, spike_at=spike_at)

    # run legacy generate_signals on full df
    try:
        import backtesting_backend.core.strategy_simulator as sim_mod
        gen = getattr(sim_mod, 'generate_signals', None)
        if gen is None:
            from backtesting_backend.core import strategy_conditions as sc
            gen = sc.generate_signals
        legacy_df_out = gen(df.copy(), {})
    except Exception as e:
        legacy_df_out = None
        legacy_err = str(e)

    results = []
    # helper: convert indicator dict -> IndicatorSet
    try:
        from backend.core.new_strategy.data_structures import IndicatorSet
        from backend.core.new_strategy.signal_engine import SignalEngine
        def dict_to_ind(d):
            if not d:
                return None
            kwargs = {k: v for k, v in d.items() if k in IndicatorSet.__annotations__}
            if 'symbol' not in kwargs:
                kwargs['symbol'] = 'BTCUSDT'
            return IndicatorSet(**kwargs)
    except Exception:
        return {'error': 'cannot import IndicatorSet/SignalEngine'}

    # iterate and find 'signal' entries
    for idx, item in enumerate(detailed):
        # consider both 'signal' and 'signal_breakdown' entries
        if item.get('type') not in ('signal', 'signal_breakdown'):
            continue
        # find nearest previous 1m indicator
        curr_ind = None
        prev_ind = None
        prev_3m = None
        # scan backwards for indicators
        for j in range(idx - 1, -1, -1):
            it = detailed[j]
            if it.get('type') == 'indicators' and it.get('interval') == '1m':
                curr_ind = it.get('indicators')
                # find previous 1m before this
                for k in range(j - 1, -1, -1):
                    kitem = detailed[k]
                    if kitem.get('type') == 'indicators' and kitem.get('interval') == '1m':
                        prev_ind = kitem.get('indicators')
                        break
                break
        # find most recent 3m before idx
        for j in range(idx - 1, -1, -1):
            it = detailed[j]
            if it.get('type') == 'indicators' and it.get('interval') == '3m':
                prev_3m = it.get('indicators')
                break

        # last_close: prefer nearby 'signal' input.arg_1; else match indicator timestamp to df
        last_close = None
        try:
            if item.get('type') == 'signal':
                inp = item.get('input') or {}
                last_close = inp.get('arg_1')
            else:
                # search forward/backward for a nearby 'signal' item to extract input
                for k in range(idx, min(len(detailed), idx + 6)):
                    if detailed[k].get('type') == 'signal':
                        last_close = (detailed[k].get('input') or {}).get('arg_1')
                        break
                if last_close is None:
                    for k in range(idx - 1, max(-1, idx - 6), -1):
                        if detailed[k].get('type') == 'signal':
                            last_close = (detailed[k].get('input') or {}).get('arg_1')
                            break
            if last_close is None:
                ts = None
                # try to get a timestamp from nearest indicator
                if curr_ind and isinstance(curr_ind, dict):
                    ts = curr_ind.get('timestamp')
                if ts is None:
                    ts = item.get('timestamp') or (item.get('result') or {}).get('timestamp')
                if ts is not None:
                    import datetime
                    dt = datetime.datetime.utcfromtimestamp(ts / 1000.0)
                    # find nearest timestamp in df
                    diffs = [(abs((r['timestamp'] - dt).total_seconds()), i) for i, r in df.iterrows()]
                    diffs.sort()
                    last_close = float(df.iloc[diffs[0][1]]['close'])
        except Exception:
            last_close = None

        # recompute new evaluate
        current_1m = dict_to_ind(curr_ind)
        p1 = dict_to_ind(prev_ind)
        p3 = dict_to_ind(prev_3m)
        se = SignalEngine()
        try:
            new_eval = se.evaluate(current_1m=current_1m, last_close=last_close, prev_1m=p1, prev_3m=p3, confirm_3m=p3, filter_15m=None, in_position=False)
            try:
                new_eval_ser = asdict(new_eval)
            except Exception:
                new_eval_ser = getattr(new_eval, '__dict__', str(new_eval))
        except Exception as e:
            new_eval_ser = {'error': str(e)}

        # legacy row: find nearest close in legacy_df_out
        legacy_row = None
        if legacy_df_out is not None and last_close is not None:
            try:
                # look for 'close' column
                closes = legacy_df_out['close'] if 'close' in legacy_df_out else None
                if closes is not None:
                    # find nearest index
                    import numpy as np
                    arr = np.array(closes)
                    idx_closest = int((abs(arr - float(last_close))).argmin())
                    legacy_row = {c: legacy_df_out[c].iloc[idx_closest] for c in legacy_df_out.columns}
            except Exception:
                legacy_row = None

        # find any nearby breakdown (search forward/backward)
        breakdown = None
        for k in range(idx, min(len(detailed), idx + 4)):
            if detailed[k].get('type') == 'signal_breakdown':
                breakdown = detailed[k]
                break
        if not breakdown:
            for k in range(idx - 4, idx):
                if k >= 0 and detailed[k].get('type') == 'signal_breakdown':
                    breakdown = detailed[k]
                    break

        results.append({
            'detail_index': idx,
            'last_close': last_close,
            'legacy_row': legacy_row,
            'new_eval': new_eval_ser,
            'breakdown': breakdown,
        })

    # attach to report and write
    rep.setdefault('new', {}).setdefault('instrumentation', {})['window_comparison'] = results
    with open('parity_report.json', 'w', encoding='utf-8') as f:
        json.dump(rep, f, indent=2, ensure_ascii=False, default=str)

    return {'count': len(results)}


def main():
    df = make_synthetic_df(rows=300, start_price=1000.0, spike_at=120)
    params = {
        "position_size": 0.02,
        "fee_pct": 0.001,
        "slippage_pct": 0.001,
        "initial_balance": 10000.0,
        "leverage": 10,
    }

    try:
        legacy = run_legacy(df, params)
    except Exception as e:
        legacy = {"error": str(e)}

    try:
        new = run_new_adapter(df, params)
    except Exception as e:
        new = {"error": str(e)}

    report = summarize_and_diff(legacy, new)

    # run focused legacy vs new signal comparison for legacy entry index
    try:
        focused = compare_legacy_vs_new_snapshot(legacy, new, df)
        if focused is not None:
            print('Focused comparison saved to parity_report.json under instrumentation.focused_comparison')
    except Exception as e:
        print('Focused comparison failed:', e)
    try:
        wc = compare_all_signals_in_report(df_rows=300, start_price=1000.0, spike_at=120)
        print('Window comparison done, items:', wc.get('count') if isinstance(wc, dict) else wc)
    except Exception as e:
        print('Window comparison failed:', e)


if __name__ == "__main__":
    main()
