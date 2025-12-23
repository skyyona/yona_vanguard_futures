import sys, os, asyncio, time, json

# Ensure project package path is available
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
YVF = os.path.join(WORKSPACE_ROOT, "yona_vanguard_futures")
if os.path.isdir(YVF) and YVF not in sys.path:
    sys.path.insert(0, YVF)
elif WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from backtesting_backend.core.data_loader import DataLoader
from backtesting_backend.database.db_manager import BacktestDB
# local client adapter
from backtesting_backend.api_client.binance_client import BinanceClient
from backtesting_backend.database.repositories.kline_repository import KlineRepository
# Defer importing BacktestAdapter and orchestrator until runtime to avoid import-order cycles

from scripts.output_config import backtest_mtf_dir

OUT_DIR = backtest_mtf_dir()

SYMBOLS = os.environ.get('SYMBOLS')
if SYMBOLS:
    SYMBOLS = [s.strip() for s in SYMBOLS.split(',') if s.strip()]
else:
    SYMBOLS = ['XPINUSDT']
INTERVAL = '1m'
DAYS = 1
# Limit number of candles kept in-memory per interval to speed up backtest loops
MAX_CANDLES = 500

async def run_for(symbol, interval=INTERVAL, days=DAYS, params=None):
    now_ms = int(time.time() * 1000)
    # Compute per-interval warmup start times so each interval has enough candles
    REQUIRED_CANDLES = 200
    MARGIN = 1.2
    needed_candles = int(REQUIRED_CANDLES * MARGIN)
    interval_minutes_map = {"1m": 1, "3m": 3, "15m": 15}
    # start_ms_map contains per-interval earliest ms to request so we get `needed_candles`
    start_ms_map = {}
    # Prefer DB latest kline time as the anchor for warmup end time to avoid 'future' windows
    repo = KlineRepository()
    end_ms_map = {}
    for iv, mins in interval_minutes_map.items():
        interval_ms = mins * 60 * 1000
        try:
            latest = await repo.get_latest_kline_time(symbol, iv)
        except Exception:
            latest = None
        try:
            earliest = await repo.get_earliest_kline_time(symbol, iv)
        except Exception:
            earliest = None

        # If DB has no data for this interval, fall back to now_ms
        if latest is None:
            end_ms = now_ms
        else:
            end_ms = int(latest)

        # compute start based on latest available and needed candles
        start_ms = end_ms - needed_candles * interval_ms

        # clamp to DB earliest if available
        if earliest is not None and start_ms < int(earliest):
            start_ms = int(earliest)

        # ensure non-negative
        if start_ms < 0:
            start_ms = 0

        start_ms_map[iv] = start_ms
        end_ms_map[iv] = end_ms
        # store the end for this interval too to be explicit
        # if other code needs end_ms per-interval, could be returned; for now use end_ms variable
    # Initialize a lightweight local client that reads klines from the Backtest DB
    # to avoid external HTTP requests during deterministic backtests.

    class LocalBinanceClient:
        def __init__(self):
            self.repo = KlineRepository()

        async def get_klines(self, symbol, interval, start_time=None, end_time=None, limit=1000):
            # Query repository for rows and convert to Binance-like list format
            rows = await self.repo.get_klines_in_range(symbol, interval, start_time or 0, end_time or 2**63-1)
            out = []
            for r in rows:
                # repository returns model objects with attributes matching DB columns
                out.append([
                    int(r.open_time),
                    str(r.open),
                    str(r.high),
                    str(r.low),
                    str(r.close),
                    str(r.volume),
                    int(r.close_time),
                    str(getattr(r, 'quote_asset_volume', None) or 0),
                    int(getattr(r, 'number_of_trades', 0)),
                    str(getattr(r, 'taker_buy_base_asset_volume', 0) or 0),
                    str(getattr(r, 'taker_buy_quote_asset_volume', 0) or 0),
                    str(getattr(r, 'ignore', 0) or 0),
                ])
            return out

    client = LocalBinanceClient()
    try:
        # Build backtest config using date strings expected by BacktestConfig
        from datetime import datetime
        # Use earliest start among intervals for BacktestConfig start_date
        config_start_ms = min(start_ms_map.values())
        # Use latest end among intervals for end_date so backtest covers available DB range
        config_end_ms = max(end_ms_map.values()) if len(end_ms_map) > 0 else now_ms
        start_date = datetime.utcfromtimestamp(config_start_ms / 1000).strftime("%Y-%m-%d")
        end_date = datetime.utcfromtimestamp(config_end_ms / 1000).strftime("%Y-%m-%d")

        # Load klines into DB and retrieve DataFrames for 1m, 3m, 15m
        loader = DataLoader(binance_client=client)
        # Create a single BinanceDataFetcher instance and share it across orchestrator/executor
        try:
            from backend.core.new_strategy.singletons import get_shared_fetcher
            fetcher = get_shared_fetcher(client)
            print(f"[DEBUG] Obtained shared BinanceDataFetcher id={id(fetcher)} fetcher.cache id={id(getattr(fetcher, 'cache', None))}")
        except Exception:
            fetcher = None
        # Debug: log DataLoader instance id and repo id to verify shared instances
        try:
            print(f"[DEBUG] DataLoader id={id(loader)} kline_repo id={id(getattr(loader, 'kline_repo', None))}")
        except Exception:
            pass
        print(f"Loading klines for {symbol} {interval} {days} day(s)")
        # request per-interval windows computed above so each interval has >= required candles
        await loader.load_historical_klines(symbol, "1m", start_ms_map['1m'], end_ms_map.get('1m', now_ms))
        df1 = await loader.get_klines_for_backtest(symbol, "1m", start_ms_map['1m'], end_ms_map.get('1m', now_ms))
        # BacktestExecutor expects a 'timestamp' datetime column used by executor loop
        if 'timestamp' not in df1.columns:
            df1 = df1.copy()
            df1['timestamp'] = df1.index
        # keep only recent rows to reduce processing time
        if len(df1) > MAX_CANDLES:
            df1 = df1.tail(MAX_CANDLES)
        await loader.load_historical_klines(symbol, "3m", start_ms_map['3m'], end_ms_map.get('3m', now_ms))
        df3 = await loader.get_klines_for_backtest(symbol, "3m", start_ms_map['3m'], end_ms_map.get('3m', now_ms))
        if 'timestamp' not in df3.columns:
            df3 = df3.copy()
            df3['timestamp'] = df3.index
        if len(df3) > MAX_CANDLES:
            df3 = df3.tail(MAX_CANDLES)
        await loader.load_historical_klines(symbol, "15m", start_ms_map['15m'], end_ms_map.get('15m', now_ms))
        df15 = await loader.get_klines_for_backtest(symbol, "15m", start_ms_map['15m'], end_ms_map.get('15m', now_ms))
        if 'timestamp' not in df15.columns:
            df15 = df15.copy()
            df15['timestamp'] = df15.index
        if len(df15) > MAX_CANDLES:
            df15 = df15.tail(MAX_CANDLES)

        from backend.core.new_strategy.backtest_adapter import BacktestExecutor, BacktestConfig
        from backend.core.new_strategy.orchestrator import StrategyOrchestrator, OrchestratorConfig

        config = BacktestConfig(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_balance=1000.0,
            leverage=1,
        )

        # For deterministic backtest use the orchestrator's built-in dummy client
        # and allow adapter to exercise `position_size` sizing by not providing
        # a fixed `order_quantity` (set to None).
        orch_cfg = OrchestratorConfig(symbol=symbol, leverage=1, enable_trading=False, order_quantity=None)
        # pass the same BinanceClient instance into the orchestrator so
        # internal fetchers/clients are not None during backtest
        # Pass the shared fetcher into the orchestrator so warmup uses same cache instance
        if fetcher is not None:
            orchestrator = StrategyOrchestrator(binance_client=client, fetcher=fetcher, config=orch_cfg)
        else:
            orchestrator = StrategyOrchestrator(binance_client=client, config=orch_cfg)
        # Debug: log orchestrator fetcher/cache identity to verify it's the same instance
        try:
            f_cache = getattr(orchestrator.fetcher, 'cache', None)
            print(f"[DEBUG] Orchestrator.fetcher id={id(getattr(orchestrator, 'fetcher', None))} fetcher.cache id={id(f_cache)}")
        except Exception:
            pass

        # --- EXPLICIT WARMUP: ensure orchestrator/data loader cache contains >=200 candles ---
        try:
            import logging
            # temporarily raise backtest_adapter logger to INFO so adapter entry logs are visible
            logging.getLogger('backend.core.new_strategy.backtest_adapter').setLevel(logging.INFO)

            required_candles = 200
            intervals = ['1m', '3m', '15m']
            # Prefer DataLoader's repository access to fetch explicit historical rows
            # (some DataLoader implementations expose `get_historical_candles_from_repo`)
            for iv in intervals:
                try:
                    # request more than required to ensure buffer
                    if hasattr(loader, 'get_historical_candles_from_repo'):
                        klines_df = await loader.get_historical_candles_from_repo(
                            symbol=symbol,
                            interval=iv,
                            num_candles=required_candles * 2,
                        )
                    else:
                        # fall back to using already-loaded frames (df1/df3/df15)
                        klines_df = {'1m': df1, '3m': df3, '15m': df15}.get(iv, None)

                    if klines_df is None or len(klines_df) == 0:
                        print(f"[WARNING] No DB candles returned for {symbol}/{iv}; cache may remain insufficient.")
                    else:
                        print(f"Loaded {len(klines_df)} {iv} candles from DB for {symbol}")

                    # Ensure orchestractor cache contains these candles; convert & inject if necessary
                    try:
                        from backend.core.new_strategy.data_structures import Candle

                        def _df_to_candles(df, symbol, interval):
                            interval_ms_map = {"1m": 60 * 1000, "3m": 3 * 60 * 1000, "15m": 15 * 60 * 1000}
                            interval_ms = interval_ms_map.get(interval, 60 * 1000)
                            out = []
                            for _, row in df.iterrows():
                                ts = row.get('timestamp', None)
                                if ts is None:
                                    ts = row.name
                                if hasattr(ts, 'timestamp'):
                                    open_time = int(ts.timestamp() * 1000)
                                else:
                                    open_time = int(open_time if (open_time:=ts) is not None else 0)
                                close_time = open_time + interval_ms - 1
                                out.append(Candle(
                                    symbol=symbol,
                                    interval=interval,
                                    open_time=open_time,
                                    close_time=close_time,
                                    open=float(row.get('open', 0)),
                                    high=float(row.get('high', 0)),
                                    low=float(row.get('low', 0)),
                                    close=float(row.get('close', 0)),
                                    volume=float(row.get('volume', 0)),
                                    quote_volume=float(row.get('quote_volume', 0) or 0),
                                    trades_count=int(row.get('trades', 0) or 0),
                                ))
                            return out

                        # clear cache for symbol interval and bulk-add (operate on shared fetcher)
                        try:
                            # if we have a shared fetcher variable, prefer using it
                            target_cache = None
                            if fetcher is not None and getattr(fetcher, 'cache', None) is not None:
                                target_cache = fetcher.cache
                            else:
                                target_cache = getattr(orchestrator, 'fetcher', None).cache
                            # Diagnostics: report published pointer (no clear performed)
                            try:
                                try:
                                    pub_before = target_cache.get_published_count(symbol, iv)
                                except Exception:
                                    pub_before = None
                                print(f"[WARMUP DIAG] (no clear) Using existing cache for {symbol}. Target Cache ID: {id(target_cache)}. Published(before): {pub_before}")
                            except Exception:
                                pass
                        except Exception:
                            pass

                        if klines_df is not None and len(klines_df) > 0:
                            candles = _df_to_candles(klines_df.tail(required_candles * 2), symbol, iv)
                            # add to cache (some caches allow interval-agnostic bulk add)
                            try:
                                try:
                                    before_pub = None
                                    try:
                                        before_pub = target_cache.get_published_count(symbol, iv)
                                    except Exception:
                                        before_pub = None
                                    print(f"[WARMUP DIAG] About to bulk-add {len(candles)} candles for {symbol}/{iv}. Cache ID: {id(target_cache)}. Published(before): {before_pub}")
                                except Exception:
                                    pass
                                target_cache.add_candles_bulk(candles)
                                try:
                                    after_pub = None
                                    try:
                                        after_pub = target_cache.get_published_count(symbol, iv)
                                    except Exception:
                                        after_pub = None
                                    print(f"[WARMUP DIAG] Completed bulk-add for {symbol}/{iv}. Cache ID: {id(target_cache)}. Published(after): {after_pub}")
                                except Exception:
                                    pass
                            except Exception:
                                # fallback: add one-by-one
                                for c in candles:
                                    try:
                                        target_cache.add_candle(c)
                                    except Exception:
                                        pass

                    except Exception as ie:
                        print(f"[ERROR] Failed to convert/inject candles for {symbol}/{iv}: {ie}")

                    # Query actual cache size for clarity
                    actual_cache_size = 'n/a'
                    try:
                        # prefer shared fetcher cache when available
                        cache_for_check = None
                        if fetcher is not None and getattr(fetcher, 'cache', None) is not None:
                            cache_for_check = fetcher.cache
                        else:
                            cache_for_check = orchestrator.fetcher.cache
                        if hasattr(cache_for_check, 'get_cache_size'):
                            actual_cache_size = cache_for_check.get_cache_size(symbol, iv)
                        else:
                            # fallback to get_latest_candles
                            latest = cache_for_check.get_latest_candles(symbol, iv, required_candles)
                            actual_cache_size = len(latest)
                    except Exception:
                        actual_cache_size = 'n/a'

                    if isinstance(actual_cache_size, int) and actual_cache_size < required_candles:
                        print(f"[WARNING] Cache for {symbol}/{iv} is {actual_cache_size}, required {required_candles}.")
                    print(f"Actual cache size for {symbol}/{iv}: {actual_cache_size}")

                except Exception as e:
                    print(f"[ERROR] Failed to warmup {iv} data for {symbol}: {e}")
                    raise

            print("--- Explicit Data Warmup Finished ---")
        except Exception as e:
            print(f"Warmup failed: {e}")

        executor = BacktestExecutor(
            orchestrator=orchestrator,
            config=config,
            klines_1m=df1,
            klines_3m=df3,
            klines_15m=df15,
        )
        print(f"Running BacktestExecutor for {symbol} {interval} {days}d")
        res = executor.run()
        return res
    except Exception as e:
        print(f"BacktestAdapter run failed for {symbol}: {e}")
        return None

async def main():
    await BacktestDB.get_instance().init()
    summary = []
    
    def _sanitize(obj):
        """Recursively replace non-JSON-finite floats (NaN, +/-inf) with None.

        Handles Python floats, numpy numeric types (via float coercion), and
        string tokens like 'Infinity' that sometimes appear from serialization.
        """
        import math
        # dict/list recursion
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]

        # strings that represent invalid numeric tokens
        if isinstance(obj, str):
            low = obj.strip().lower()
            if low in ("nan", "none", "null"):
                return None
            if low in ("inf", "infinity", "-inf", "+inf"):
                return None
            return obj

        # numeric-ish objects: try to coerce to float and check finiteness
        try:
            if isinstance(obj, (int, float)):
                if math.isfinite(obj):
                    return obj
                return None
            # support numpy numeric types and other numeric-like objects
            if hasattr(obj, "__float__"):
                try:
                    val = float(obj)
                    if math.isfinite(val):
                        return val
                    return None
                except Exception:
                    pass
        except Exception:
            pass

        return obj
    for s in SYMBOLS:
        base_params = {"enable_mtf_stoch": False}
        print(f"Running baseline for {s}")
        res_base = await run_for(s, INTERVAL, DAYS, params=base_params)
        if res_base:
            out_path = os.path.join(OUT_DIR, f"baseline_{s}_{INTERVAL}_{DAYS}d.json")
            try:
                clean_base = _sanitize(res_base)
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(clean_base, f, ensure_ascii=False, indent=2)
                print(f"Saved {out_path}")
            except Exception:
                # Fallback to previous behavior if sanitization/dump fails
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(res_base, f, default=str, ensure_ascii=False, indent=2)
                print(f"Saved {out_path} (fallback serialization)")
        mtf_params = {"enable_mtf_stoch": True, "mtf_loose_mode": False, "mtf_oversold_threshold": 20.0}
        print(f"Running MTF-enabled for {s}")
        res_mtf = await run_for(s, INTERVAL, DAYS, params=mtf_params)
        if res_mtf:
            out_path = os.path.join(OUT_DIR, f"mtf_{s}_{INTERVAL}_{DAYS}d.json")
            try:
                clean_mtf = _sanitize(res_mtf)
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(clean_mtf, f, ensure_ascii=False, indent=2)
                print(f"Saved {out_path}")
            except Exception:
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(res_mtf, f, default=str, ensure_ascii=False, indent=2)
                print(f"Saved {out_path} (fallback serialization)")

        summary.append({
            'symbol': s,
            'baseline': res_base,
            'mtf': res_mtf
        })

    summary_path = os.path.join(OUT_DIR, 'comparison_summary.json')
    # Sanitize summary (ensure no NaN/Infinity floats) before writing
    try:
        clean_summary = _sanitize(summary)
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(clean_summary, f, ensure_ascii=False, indent=2)
    except Exception:
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, default=str, ensure_ascii=False, indent=2)
    print('Done. Summary written to', summary_path)

if __name__ == '__main__':
    import asyncio
    import sys
    import traceback
    try:
        asyncio.run(main())
        sys.exit(0)
    except SystemExit as se:
        try:
            import traceback
            print(f"SystemExit raised with code: {se.code}")
        except Exception:
            pass
        raise
    except Exception:
        traceback.print_exc()
        sys.exit(1)
