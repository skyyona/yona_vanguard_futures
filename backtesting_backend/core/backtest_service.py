import asyncio
import uuid
import time
from typing import Dict, Any, Optional

from backtesting_backend.schemas.backtest_request import BacktestRequest
from backtesting_backend.schemas.backtest_result import BacktestResult
from backtesting_backend.core.data_loader import DataLoader
from backtesting_backend.core.strategy_simulator import StrategySimulator
from backtesting_backend.core.parameter_optimizer import ParameterOptimizer
from backtesting_backend.optimizers.grid_search import GridSearch
from backtesting_backend.database.repositories.backtest_result_repository import BacktestResultRepository
from backtesting_backend.core.logger import logger


class BacktestService:
    def __init__(self, data_loader: Optional[DataLoader] = None,
                 simulator: Optional[StrategySimulator] = None,
                 optimizer: Optional[ParameterOptimizer] = None,
                 result_repo: Optional[BacktestResultRepository] = None):
        self.data_loader = data_loader or DataLoader()
        self.simulator = simulator or StrategySimulator()
        self.optimizer = optimizer or ParameterOptimizer(self.simulator)
        self.result_repo = result_repo or BacktestResultRepository()

        # in-memory status store: {run_id: {status, progress, result}}
        self._statuses: Dict[str, Dict[str, Any]] = {}

    def _create_run_id(self) -> str:
        return str(uuid.uuid4())

    async def run_backtest_task(self, request: BacktestRequest) -> str:
        run_id = self._create_run_id()
        self._statuses[run_id] = {"status": "queued", "progress": 0}

        # schedule actual work
        asyncio.create_task(self._run_background(run_id, request))
        return run_id

    async def _run_background(self, run_id: str, request: BacktestRequest) -> None:
        try:
            self._statuses[run_id]["status"] = "running"
            self._statuses[run_id]["progress"] = 10

            # Ensure data available
            await self.data_loader.load_historical_klines(request.symbol, request.interval, request.start_time, request.end_time)
            self._statuses[run_id]["progress"] = 30

            df = await self.data_loader.get_klines_for_backtest(request.symbol, request.interval, request.start_time, request.end_time)
            self._statuses[run_id]["progress"] = 50

            if request.optimization_mode and request.optimization_ranges:
                # run optimization using GridSearch for parallel evaluation
                param_grid = request.optimization_ranges

                def objective(p: Dict[str, Any]) -> float:
                    # merge base parameters and the tested params
                    merged = dict(request.parameters or {})
                    merged.update(p)
                    # include global execution params from request
                    merged["fee_pct"] = request.fee_pct
                    merged["slippage_pct"] = request.slippage_pct
                    merged["position_size"] = request.position_size
                    merged["take_profit_pct"] = request.take_profit_pct
                    merged["trailing_stop_pct"] = request.trailing_stop_pct

                    # run simulation (synchronous) and return score (profit as objective)
                    try:
                        sim_res = self.simulator.run_simulation(request.symbol, request.interval, df, request.initial_balance, request.leverage, merged)
                        # objective: prefer higher net profit but penalize large drawdown
                        profit = float(sim_res.get("profit", 0.0))
                        max_dd = float(sim_res.get("max_drawdown_pct", 0.0))
                        # simple scoring: profit - k * drawdown (k=0.5)
                        score = profit - 0.5 * max_dd
                        return score
                    except Exception:
                        return float("-inf")

                gs = GridSearch(param_grid)
                # allow modest parallelism
                best_params, best_score, all_results = gs.search(objective, max_workers=4)

                # run final simulation with best params to get full result
                merged_best = dict(request.parameters or {})
                merged_best.update(best_params or {})
                merged_best["fee_pct"] = request.fee_pct
                merged_best["slippage_pct"] = request.slippage_pct
                merged_best["position_size"] = request.position_size
                merged_best["take_profit_pct"] = request.take_profit_pct
                merged_best["trailing_stop_pct"] = request.trailing_stop_pct

                result = self.simulator.run_simulation(request.symbol, request.interval, df, request.initial_balance, request.leverage, merged_best)
                best_params = merged_best
            else:
                result = self.simulator.run_simulation(request.symbol, request.interval, df, request.initial_balance, request.leverage, request.parameters)
                best_params = request.parameters

            self._statuses[run_id]["progress"] = 90

            # persist result
            now_ms = int(time.time() * 1000)
            self._statuses[run_id]["progress"] = 90

            # determine max drawdown: prefer simulator-provided value, else compute from trades
            def _compute_max_drawdown_pct_from_trades(initial_balance, trades):
                try:
                    b = float(initial_balance)
                except Exception:
                    b = 0.0
                balances = [b]
                for t in trades or []:
                    pnl = t.get('net_pnl', 0.0) or 0.0
                    try:
                        pnl = float(pnl)
                    except Exception:
                        pnl = 0.0
                    b = b + pnl
                    balances.append(b)
                peak = -1e18
                max_dd = 0.0
                for val in balances:
                    if val > peak:
                        peak = val
                    if peak > 0:
                        dd = (peak - val) / peak
                        if dd > max_dd:
                            max_dd = dd
                return max_dd * 100

            # pick candidate from simulator output
            md = None
            try:
                md_cand = result.get('max_drawdown_pct', None)
                if md_cand is None:
                    md_cand = result.get('max_drawdown', None)
                if md_cand is not None:
                    md = float(md_cand)
            except Exception:
                md = None

            # if missing or zero, attempt to compute from trades
            if not md or md == 0.0:
                trades = result.get('trades') or []
                initial_balance = result.get('initial_balance') or request.initial_balance
                if trades:
                    try:
                        md = _compute_max_drawdown_pct_from_trades(float(initial_balance), trades)
                    except Exception:
                        md = 0.0
                else:
                    md = 0.0

            # map simulator result fields to DB columns (ensure max_drawdown persisted)
            result_record = {
                "run_id": run_id,
                "strategy_name": request.strategy_name,
                "symbol": request.symbol,
                "interval": request.interval,
                "start_time": request.start_time,
                "end_time": request.end_time,
                "final_balance": result.get("final_balance"),
                "profit_percentage": result.get("profit_percentage"),
                # persist computed/derived max drawdown (percent)
                "max_drawdown": md or 0.0,
                "total_trades": result.get("total_trades"),
                "win_rate": result.get("win_rate"),
                # Do NOT persist or expose user capital/leverage in stored parameters.
                "parameters": str(best_params),
                "created_at": now_ms,
            }

            await self.result_repo.create_backtest_result(result_record)

            # Sanitize in-memory result before exposing: remove any fields that contain
            # user-specific capital or leverage information. The simulator may accept
            # these for simulation accuracy, but outputs returned by the service must
            # not include them per product policy.
            sanitized = dict(result)
            for s_key in ("initial_balance", "leverage"):
                if s_key in sanitized:
                    sanitized.pop(s_key, None)

            self._statuses[run_id]["status"] = "completed"
            self._statuses[run_id]["progress"] = 100
            self._statuses[run_id]["result"] = sanitized
        except Exception as e:
            logger.exception("Backtest run %s failed: %s", run_id, e)
            self._statuses[run_id]["status"] = "failed"
            self._statuses[run_id]["error"] = str(e)

    def get_backtest_status(self, run_id: str) -> Dict[str, Any]:
        return self._statuses.get(run_id, {"status": "not_found"})

    async def get_backtest_result(self, run_id: str) -> Optional[Dict[str, Any]]:
        rec = await self.result_repo.get_backtest_result_by_run_id(run_id)
        if not rec:
            return None
        # convert ORM to dict
        if hasattr(rec, "__dict__"):
            out = {k: getattr(rec, k) for k in rec.__dict__ if not k.startswith("_")}
            # provide a clear, consistent field name: simulator uses 'max_drawdown_pct' (percent)
            # DB column is 'max_drawdown' which stores a percent value. Expose both keys for clarity.
            try:
                md = out.get('max_drawdown', None)
                if md is not None:
                    out['max_drawdown_pct'] = float(md)
            except Exception:
                out['max_drawdown_pct'] = out.get('max_drawdown')
            return out
        return dict(rec)

    async def collect_historical_klines(self, symbol: str, interval: str, start_time: int, end_time: int) -> None:
        await self.data_loader.load_historical_klines(symbol, interval, start_time, end_time)
