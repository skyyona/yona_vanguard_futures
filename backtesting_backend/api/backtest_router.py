from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from uuid import UUID

from backtesting_backend.schemas.backtest_request import BacktestRequest
from backtesting_backend.schemas.backtest_result import BacktestResult
import time
from typing import Dict

router = APIRouter()


def get_backtest_service(request: Request):
	svc = getattr(request.app.state, "backtest_service", None)
	if svc is None:
		raise HTTPException(status_code=500, detail="BacktestService not initialized")
	return svc


@router.post("/run_backtest")
async def run_backtest(request_model: BacktestRequest, svc=Depends(get_backtest_service)) -> Any:
	run_id = await svc.run_backtest_task(request_model)
	return {"run_id": run_id, "message": "backtest started"}


@router.get("/backtest_status/{run_id}")
async def backtest_status(run_id: str, svc=Depends(get_backtest_service)) -> Any:
	return svc.get_backtest_status(run_id)


@router.get("/backtest_result/{run_id}")
async def backtest_result(run_id: str, svc=Depends(get_backtest_service)) -> Any:
	res = await svc.get_backtest_result(run_id)
	if res is None:
		raise HTTPException(status_code=404, detail="result not found")
	# Let FastAPI/Pydantic validate when possible
	return res


@router.post("/data/collect_historical_klines")
async def collect_historical_klines(symbol: str, interval: str, start_time: int, end_time: int, request: Request = None, background: BackgroundTasks = None):
	svc = get_backtest_service(request)
	# schedule background collection
	# use asyncio.create_task inside service if preferred
	background.add_task(svc.collect_historical_klines, symbol, interval, start_time, end_time)
	return {"message": "historical data collection scheduled"}


@router.get("/strategy-analysis")
async def strategy_analysis(symbol: str, period: str = "1w", interval: str = "1m", request: Request = None):
	"""Run a lightweight strategy analysis for Alpha/Beta/Gamma engines and return recommended engine.

	This endpoint is intentionally lightweight: it ensures KLine data is present, computes
	simple indicator-driven simulations for three preset parameterizations, and returns
	a summary including the best engine and per-engine metrics.
	"""
	svc = get_backtest_service(request)

	# compute time window in ms
	now_ms = int(time.time() * 1000)
	if period == "1w":
		start_ms = now_ms - 7 * 24 * 60 * 60 * 1000
	elif period == "1d":
		start_ms = now_ms - 24 * 60 * 60 * 1000
	else:
		# default to 1 week
		start_ms = now_ms - 7 * 24 * 60 * 60 * 1000

	end_ms = now_ms

	# ensure data available
	try:
		await svc.data_loader.load_historical_klines(symbol, interval, start_ms, end_ms)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to load klines: {e}")

	df = await svc.data_loader.get_klines_for_backtest(symbol, interval, start_ms, end_ms)
	if df is None or df.empty:
		raise HTTPException(status_code=404, detail="No kline data available for symbol/period")

	# determine if this symbol should be treated as "newly listed" based on available candles
	num_candles = len(df) if df is not None else 0

	# read runtime settings from app config
	cfg = getattr(request.app.state, 'config', None)
	if cfg is None:
		# fallback defaults
		new_listing_cutoff_days = 7
		min_required_candles = 60
		sim_min_candles = 200
	else:
		new_listing_cutoff_days = getattr(cfg, 'NEW_LISTING_CUTOFF_DAYS', 7)
		min_required_candles = getattr(cfg, 'MIN_REQUIRED_CANDLES_FOR_ANALYSIS', 60)
		sim_min_candles = getattr(cfg, 'SIM_MIN_CANDLES', 200)

	# is_new_listing: based on the oldest kline timestamp relative to cutoff days
	try:
		oldest = int(df['open_time'].min()) if 'open_time' in df.columns else None
		if oldest:
			now_ms = int(time.time() * 1000)
			days_since_listing = (now_ms - oldest) / (1000 * 60 * 60 * 24)
			is_new_listing = days_since_listing <= float(new_listing_cutoff_days)
		else:
			# fallback to candle-count heuristic
			is_new_listing = num_candles < sim_min_candles
	except Exception:
		is_new_listing = num_candles < sim_min_candles

	# whether we have sufficient candles to run a reliable simulation for new listings
	has_min_candles = num_candles >= int(min_required_candles)

	# engine parameter presets
	presets: Dict[str, dict] = {
		"alpha": {"fast_ema_period": 9, "slow_ema_period": 21, "stop_loss_pct": 0.005},
		"beta": {"fast_ema_period": 12, "slow_ema_period": 26, "stop_loss_pct": 0.01},
		"gamma": {"fast_ema_period": 5, "slow_ema_period": 34, "stop_loss_pct": 0.002},
	}

	engine_results = {}
	best_engine = None
	best_profit = float("-inf")

	# load new-listing presets file for Case A (data missing)
	import os, yaml
	presets_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'new_listing_presets.yaml')
	try:
		with open(presets_file, 'r', encoding='utf-8') as f:
			file_presets = yaml.safe_load(f)
			if isinstance(file_presets, dict):
				# merge with code defaults - file presets take precedence
				for k, v in file_presets.items():
					if k in presets and isinstance(v, dict):
						presets[k].update(v)
					else:
						presets[k] = v
	except Exception:
		# ignore file errors and continue with built-in presets
		file_presets = {}

	for name, params in presets.items():
		try:
			if is_new_listing:
				# New-listing handling: split into 2 cases based on available candles
				try:
					analyzer = getattr(svc.simulator, "analyzer", None)
					if analyzer is None:
						# fallback to constructing a local analyzer
						from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
						analyzer = StrategyAnalyzer()

					# Case A: new listing but insufficient candles
					if not has_min_candles:
						# provide data_missing response using conservative presets from YAML
						heur = analyzer.heuristics_for_new_listing(df, engine_key=name, sim_min_candles=sim_min_candles)
						executable_parameters = dict(heur.get("executable_parameters", {}))
						# override with file preset if present
						if name in file_presets and isinstance(file_presets[name], dict):
							executable_parameters.update(file_presets[name])

						# enforce conservative risk management for new listings
						executable_parameters.update({
							"leverage": 1,
							"position_size": 0.005,
							"no_compounding": True,
							"stop_loss_pct": 0.002,
						})

						engine_entry = {
							"params": params,
							"metrics": {},
							"heuristic": {
								"confidence": float(heur.get("confidence", 0.0)),
								"notes": heur.get("notes", []),
							},
							"is_new_listing": True,
							"data_missing": True,
							"executable_parameters": executable_parameters,
						}

						engine_results[name] = engine_entry
						continue

					# Case B: new listing with sufficient candles -> run specialized new-listing strategies
					# analyzer should expose generators for new-listing strategies
					try:
						strategies = analyzer.generate_new_listing_strategies(df, base_params=params)
					except Exception:
						strategies = {}

					# run simulator per returned strategy if available (merge results)
					# strategies is expected to be dict of engine_name -> list of strategy dicts
					merged_entry = {"params": params, "metrics": {}, "is_new_listing": True, "data_missing": False, "executions": []}
					best_local_profit = float("-inf")
					for strat in strategies.get(name, []) if isinstance(strategies.get(name, []), list) else []:
						exec_params = dict(strat.get("executable_parameters", {}))
						# enforce risk overrides for new listings
						exec_params.update({
							"leverage": 1,
							"position_size": 0.005,
							"no_compounding": True,
							"stop_loss_pct": 0.002,
						})
						try:
							sim_res = svc.simulator.run_simulation(symbol, interval, df, initial_balance=1000.0, leverage=1, strategy_parameters=exec_params)
							profit_pct = float(sim_res.get("profit_percentage", 0.0))
							total_trades = int(sim_res.get("total_trades", 0) or 0)
							win_rate = float(sim_res.get("win_rate", 0.0) or 0.0)
							merged_entry["executions"].append({"strategy": strat.get("name"), "params": exec_params, "metrics": {"profit_percentage": profit_pct, "total_trades": total_trades, "win_rate": win_rate}})
							if profit_pct is not None and profit_pct > best_local_profit:
								best_local_profit = profit_pct
								merged_entry["metrics"] = {"profit_percentage": profit_pct, "total_trades": total_trades, "win_rate": win_rate}
								merged_entry["executable_parameters"] = exec_params
						except Exception:
							continue

					engine_results[name] = merged_entry
					# pick best_engine update
					if merged_entry.get("metrics") and merged_entry["metrics"].get("profit_percentage", float("-inf")) > best_profit:
						best_profit = merged_entry["metrics"]["profit_percentage"]
						best_engine = name
					continue
				except Exception as e:
					engine_results[name] = {"error": str(e)}
					continue
				try:
					analyzer = getattr(svc.simulator, "analyzer", None)
					if analyzer is None:
						# fallback to constructing a local analyzer
						from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
						analyzer = StrategyAnalyzer()

					heur = analyzer.heuristics_for_new_listing(df, engine_key=name, sim_min_candles=SIM_MIN_CANDLES)
					executable_parameters = dict(heur.get("executable_parameters", {}))
					# ensure runtime fields are set
					executable_parameters.update({
						"symbol": symbol,
						"interval": interval,
						"leverage": executable_parameters.get("leverage", 1),
					})

					engine_entry = {
						"params": params,
						"metrics": {},
						"heuristic": {
							"confidence": float(heur.get("confidence", 0.0)),
							"notes": heur.get("notes", []),
						},
						"is_new_listing": True,
						"executable_parameters": executable_parameters,
					}

					# If enough candles to run a useful simulation, run it and attach metrics (but keep heuristic params)
					if num_candles >= SIM_MIN_CANDLES:
						try:
							sim_res = svc.simulator.run_simulation(symbol, interval, df, initial_balance=1000.0, leverage=1, strategy_parameters=params)
							profit_pct = float(sim_res.get("profit_percentage", 0.0))
							total_trades = int(sim_res.get("total_trades", 0) or 0)
							win_rate = float(sim_res.get("win_rate", 0.0) or 0.0)
							engine_entry["metrics"] = {"profit_percentage": profit_pct, "total_trades": total_trades, "win_rate": win_rate}
							engine_entry["max_target_profit"] = profit_pct
							if profit_pct is not None and profit_pct > best_profit:
								best_profit = profit_pct
								best_engine = name
						except Exception:
							pass

					engine_results[name] = engine_entry
				except Exception as e:
					engine_results[name] = {"error": str(e)}
					continue
			else:
				# run lightweight simulation for preset
				sim_res = svc.simulator.run_simulation(symbol, interval, df, initial_balance=1000.0, leverage=1, strategy_parameters=params)

				profit_pct = float(sim_res.get("profit_percentage", 0.0))
				total_trades = int(sim_res.get("total_trades", 0) or 0)
				win_rate = float(sim_res.get("win_rate", 0.0) or 0.0)

				# map simulator metrics to GUI-friendly fields
				expected_profit = profit_pct
				score = profit_pct  # simple scoring - can be refined
				suitability = "적합" if profit_pct > 0 else "부적합"

				# build executable parameters to be applied to live engine on Assign
				executable_parameters = dict(params) if isinstance(params, dict) else {}
				# include runtime defaults / execution-level params
				executable_parameters.update({
					"symbol": symbol,
					"interval": interval,
					"leverage": 1,
					"position_size": params.get("position_size", 0.02),
					"stop_loss_pct": params.get("stop_loss_pct", 0.005),
					"take_profit_pct": params.get("take_profit_pct", 0.0),
					"trailing_stop_pct": params.get("trailing_stop_pct", 0.0),
					"fee_pct": params.get("fee_pct", 0.001),
					"slippage_pct": params.get("slippage_pct", 0.001),
					"no_compounding": params.get("no_compounding", True)
				})

				engine_entry = {
					"params": params,
					"metrics": {
						"profit_percentage": profit_pct,
						"total_trades": total_trades,
						"win_rate": win_rate,
					},
					# GUI display fields
					"suitability": suitability,
					"score": score,
					"expected_profit": expected_profit,
					"win_rate": win_rate,
					"max_target_profit": profit_pct,
					# executable parameters for engine assignment
					"executable_parameters": executable_parameters,
				}

				engine_results[name] = engine_entry

				if expected_profit is not None and expected_profit > best_profit:
					best_profit = expected_profit
					best_engine = name
				best_engine = name
		except Exception as e:
			engine_results[name] = {"error": str(e)}

	# simple volatility estimate
	try:
		returns = df["close"].pct_change().fillna(0)
		volatility = float(returns.std() * 100)
	except Exception:
		volatility = 0.0

	# build risk management summary: prefer best_engine's stop loss / trailing stop as a simple summary
	try:
		best_params = presets.get(best_engine, {}) if best_engine else presets.get("alpha", {})
		risk_summary = {
			"stop_loss": best_params.get("stop_loss_pct", 0.005),
			"trailing_stop": best_params.get("trailing_stop_pct", 0.0)
		}
	except Exception:
		risk_summary = {"stop_loss": 0.005, "trailing_stop": 0.0}

	response_data = {
		"best_engine": best_engine or "alpha",
		"volatility": volatility,
		"max_target_profit": {k: engine_results.get(k, {}).get("metrics", {}).get("profit_percentage", 0.0) for k in ["alpha", "beta", "gamma"]},
		# keep per-engine risk details as well
		"risk_management": risk_summary,
		"engine_results": engine_results,
		"symbol": symbol,
		"period": period,
	}

	return {"data": response_data}
