from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from uuid import UUID

from backtesting_backend.schemas.backtest_request import BacktestRequest
from backtesting_backend.schemas.backtest_result import BacktestResult
from backtesting_backend.schemas.strategy_assignment import (
	StrategyAssignmentCreate,
	StrategyAssignmentRead,
	StrategyAssignmentListResponse,
)
from backend.utils.config_loader import MAX_POSITION_USDT
from backtesting_backend.core.strategy_core import run_backtest as core_run_backtest
from backtesting_backend.core.logger import logger
from backtesting_backend.core.strategy_analyzer import StrategyAnalyzer
from backtesting_backend.core.config_manager import config
from backtesting_backend.database.db_manager import BacktestDB
from backtesting_backend.database.repositories.kline_repository import KlineRepository
import time
from typing import Dict
import datetime as dt

router = APIRouter()

# Cache for symbol onboard dates (ms since epoch), populated from Binance exchangeInfo
_symbol_onboard_dates: Dict[str, int] = {}


def get_backtest_service(request: Request):
	svc = getattr(request.app.state, "backtest_service", None)
	if svc is None:
		raise HTTPException(status_code=500, detail="BacktestService not initialized")
	return svc


async def _calculate_days_since_listing_for_backtest(symbol: str, svc) -> int:
	"""상장 후 경과일 계산 (백테스트 백엔드용 단순 버전).

	Behavior:
	- 1차: Binance futures exchangeInfo 의 onboardDate 를 사용 (실제 상장일 기준).
	- 2차: local backtest DB 의 earliest 1m kline timestamp 를 사용.
	- DB 에도 없으면 최근 30일 1m klines 를 로드한 뒤 재조회.
	- On success, compute (현재 UTC - 상장 시점).days 를 반환.
	- 모든 시도가 실패하면 999 를 반환해 "구심볼"로 취급.
	"""
	try:
		# 1) Binance exchangeInfo 기반 onboardDate 캐시 확인
		global _symbol_onboard_dates
		try:
			if symbol not in _symbol_onboard_dates:
				# futures exchangeInfo 호출 (USDT 무기한 선물 기준으로 onboardDate 로드)
				client_holder = getattr(svc, "data_loader", None)
				client = getattr(client_holder, "client", None)
				if client is not None and hasattr(client, "_send_request"):
					resp = await client._send_request("GET", "/fapi/v1/exchangeInfo", params=None, signed=False)
					if isinstance(resp, dict):
						for info in resp.get("symbols", []):
							quote_asset = info.get("quoteAsset", "")
							contract_type = info.get("contractType", "")
							status = info.get("status", "")
							_sym = info.get("symbol", "")
							if (
								quote_asset == "USDT"
								and contract_type == "PERPETUAL"
								and status in ["TRADING", "SETTLING"]
							):
								onboard = int(info.get("onboardDate", 0) or 0)
								if onboard > 0:
									_symbol_onboard_dates[_sym] = onboard
		except Exception as e:
			logger.debug("_calculate_days_since_listing_for_backtest: exchangeInfo load failed for %s: %s", symbol, e)

		onboard_date = _symbol_onboard_dates.get(symbol, 0)
		if onboard_date and onboard_date > 0:
			listing_time = dt.datetime.fromtimestamp(onboard_date / 1000, tz=dt.timezone.utc)
			current_time = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
			return (current_time - listing_time).days

		# 2) Backtest DB 의 earliest 1m kline 기반 fallback
		db = BacktestDB.get_instance()
		await db.init()

		repo = KlineRepository(session_factory=db.get_session)
		earliest = await repo.get_earliest_kline_time(symbol, "1m")
		if earliest:
			listing_time = dt.datetime.fromtimestamp(int(earliest) / 1000, tz=dt.timezone.utc)
			current_time = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
			return (current_time - listing_time).days

		# 3) DB 에도 없으면 최근 30일치 1m 로딩 후 한 번 더 시도
		try:
			now_ms = int(dt.datetime.utcnow().timestamp() * 1000)
			start_ms = int((dt.datetime.utcnow() - dt.timedelta(days=30)).timestamp() * 1000)
			await svc.data_loader.load_historical_klines(symbol, "1m", start_ms, now_ms)
		except Exception as e:
			# 데이터 로딩 실패는 치명적이지 않으므로 로그만 남기고 진행
			logger.debug("_calculate_days_since_listing_for_backtest: load_historical_klines failed for %s: %s", symbol, e)

		# 재조회
		earliest = await repo.get_earliest_kline_time(symbol, "1m")
		if earliest:
			listing_time = dt.datetime.fromtimestamp(int(earliest) / 1000, tz=dt.timezone.utc)
			current_time = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
			return (current_time - listing_time).days

		# 모든 시도 실패: 구심볼로 취급
		return 999
	except Exception as e:
		logger.debug("_calculate_days_since_listing_for_backtest unexpected error for %s: %s", symbol, e)
		return 999


@router.post("/run_backtest")
async def run_backtest(request_model: BacktestRequest, svc=Depends(get_backtest_service)) -> Any:
	# Log incoming request model for runtime parameter tracing
	try:
		# Pydantic model -> dict for readable logging
		req_dict = request_model.dict() if hasattr(request_model, "dict") else str(request_model)
		logger.info("Run backtest request model: %s", req_dict)
	except Exception:
		logger.info("Run backtest request received (unable to dict-serialize request_model)")

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
	"""Run a strategy analysis with multi-scenario backtests.

	For 일반 심볼:
	- S1: 기본 기간(1d/1w) 전체 구간 그리드 서치
	- S2: 최근 24h 전체 구간 그리드 서치
	- S3: 기본 기간 중 고변동(또는 고거래량) 구간 스트레스 테스트
	- S4: 기본 기간 중 저변동(또는 저거래량) 구간 안정성 테스트
	- S5: S1 결과를 이용한 공격적 레버리지 가상 시나리오 (참고용)

	신규 상장 심볼은 별도의 휴리스틱 + Adaptive 리스크 조정 경로를 사용하며,
	이때는 단일 신규 상장 전용 전략 파라미터만 반환한다.
	"""
	svc = get_backtest_service(request)

	# compute base time window (사용자가 선택한 period 기준)
	now_ms = int(time.time() * 1000)
	if period == "1w":
		start_ms = now_ms - 7 * 24 * 60 * 60 * 1000
	elif period == "1d":
		start_ms = now_ms - 24 * 60 * 60 * 1000
	else:
		# default to 1 week
		start_ms = now_ms - 7 * 24 * 60 * 60 * 1000

	end_ms = now_ms

	# ensure data available (분석용 기준 구간)
	try:
		await svc.data_loader.load_historical_klines(symbol, interval, start_ms, end_ms)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to load klines: {e}")

	df = await svc.data_loader.get_klines_for_backtest(symbol, interval, start_ms, end_ms)
	if df is None or df.empty:
		raise HTTPException(status_code=404, detail="No kline data available for symbol/period")

	# simple volatility estimate for information (기본 구간 기준)
	try:
		returns = df["close"].pct_change().fillna(0)
		volatility = float(returns.std() * 100)
	except Exception:
		volatility = 0.0
		returns = None

	# Base scalping strategy parameters (공통 기본 파라미터)
	base_params: Dict[str, Any] = {
		"fast_ema_period": 9,
		"slow_ema_period": 21,
		"enable_trend_filter": True,
		"enable_session_filter": True,
		"enable_volume_momentum": True,
		"enable_sr_detection": False,
		"enable_sr_filter": False,
		"position_size": 0.02,  # 2% of notional by default
		"fee_pct": 0.001,
		"slippage_pct": 0.001,
		"no_compounding": True,
		"direction": "LONG",
	}

	# ------------------------------------------------------------------
	# 신규 상장 여부 판단 (ConfigManager의 NEW_LISTING_CUTOFF_DAYS 사용)
	# ------------------------------------------------------------------
	days_since_listing = await _calculate_days_since_listing_for_backtest(symbol, svc)
	is_new_listing = days_since_listing <= getattr(config, "NEW_LISTING_CUTOFF_DAYS", 7)
	new_listing_strategy_applied = False

	# Candidate grids for TP / SL / trailing-stop (decimal fractions, e.g. 0.006 == 0.6%)
	tp_candidates = [0.004, 0.006, 0.008]
	sl_candidates = [0.002, 0.003, 0.004]
	ts_candidates = [0.0, 0.004, 0.006]

	initial_balance = 1000.0
	leverage = 1

	# 공통: 레버리지 추천 계산 헬퍼
	def _compute_recommended_leverage(metrics: Dict[str, Any]) -> Dict[str, Any]:
		try:
			max_dd_pct_local = float(metrics.get("max_drawdown_pct", 0.0) or 0.0)
			max_dd_frac = max_dd_pct_local / 100.0 if max_dd_pct_local and max_dd_pct_local > 0 else 0.0
			total_trades_local = int(metrics.get("total_trades", 0) or 0)
			insufficient_trades_local = bool(metrics.get("insufficient_trades", False))

			leverage_candidates = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
			max_equity_loss_frac = 0.8  # allow up to ~80% equity loss at historical max DD

			status_local = "insufficient_data"
			recommended_x_local = None
			est_equity_loss_pct_local = None

			if max_dd_frac > 0 and total_trades_local >= 5 and not insufficient_trades_local:
				allowed: list[tuple[int, float]] = []
				for L in leverage_candidates:
					loss_frac = max_dd_frac * L
					if loss_frac <= max_equity_loss_frac:
						allowed.append((L, loss_frac))

				if allowed:
					# pick the highest leverage that still respects the loss limit
					recommended_x_local, loss_frac = allowed[-1]
					status_local = "ok"
					est_equity_loss_pct_local = loss_frac * 100.0
				else:
					# even 5x breaches the limit; still provide a very low recommendation
					recommended_x_local = 5
					status_local = "drawdown_too_high"
					if max_dd_frac > 0:
						est_equity_loss_pct_local = max_dd_frac * recommended_x_local * 100.0
			else:
				status_local = "insufficient_data"

			result: Dict[str, Any] = {
				"recommended_leverage_x": recommended_x_local,
				"status": status_local,
				"max_equity_loss_limit_pct": max_equity_loss_frac * 100.0,
			}
			if est_equity_loss_pct_local is not None:
				result["estimated_equity_loss_pct_at_max_drawdown"] = est_equity_loss_pct_local
			return result
		except Exception:
			# fall back silently; recommendation is optional metadata
			return {"recommended_leverage_x": None, "status": "error"}

	# ------------------------------------------------------------------
	# 신규 상장 심볼: 신규 상장 전용 휴리스틱 + Adaptive 리스크 조정
	# ------------------------------------------------------------------
	new_listing_strategy: Dict[str, Any] | None = None
	if is_new_listing:
		best_metrics_new: Dict[str, Any] | None = None
		best_parameters_new: Dict[str, Any] | None = None
		try:
			analyzer = StrategyAnalyzer()
			# SIM_MIN_CANDLES 를 사용해 캔들 수 대비 신뢰도 계산
			sim_min_candles = getattr(config, "SIM_MIN_CANDLES", 200)
			heur = analyzer.heuristics_for_new_listing(df, engine_key="alpha", sim_min_candles=sim_min_candles)
			base_exec_params = heur.get("executable_parameters", {}) or {}
			if not isinstance(base_exec_params, dict):
				base_exec_params = {}

			confidence = float(heur.get("confidence", 0.0) or 0.0)
			base_params_merged = dict(base_params)
			base_params_merged.update(base_exec_params)

			# 신규 상장 전용 서브 전략 감지 (볼륨 스파이크, 눌림 반등 등)
			triggered_names: list[str] = []
			try:
				strategies = analyzer.generate_new_listing_strategies(df, base_params_merged)
				for eng_key, items in strategies.items():
					for item in items or []:
						if item.get("triggered") and item.get("name"):
							triggered_names.append(str(item.get("name")))
			except Exception:
				pass

			# ----------------------
			# Adaptive Heuristics
			# ----------------------
			# 변동성/거래량/극단 스파이크 기반 risk_factor 계산
			vol_factor = 0.0
			volatility_raw = 0.0
			if returns is not None:
				try:
					volatility_raw = float(returns.std() or 0.0)
					vol_factor = min(1.0, max(0.0, volatility_raw / 0.05))  # ~5% std 이상이면 상단 클램프
				except Exception:
					vol_factor = 0.0

			vol_spike_factor = 0.0
			max_ret_factor = 0.0
			try:
				recent_vol = df.tail(min(len(df), 100))
				if not recent_vol.empty and "volume" in recent_vol.columns:
					vol_mean = float(recent_vol["volume"].mean() or 0.0)
					vol_max = float(recent_vol["volume"].max() or 0.0)
					if vol_mean > 0:
						vol_spike_factor = min(1.0, max(0.0, (vol_max / vol_mean - 1.0) / 4.0))
				if returns is not None:
					max_abs_ret = float(returns.abs().max() or 0.0)
					max_ret_factor = min(1.0, max(0.0, max_abs_ret / 0.05))
			except Exception:
				vol_spike_factor = 0.0
				max_ret_factor = 0.0

			# risk_factor: 시장 상태 기반 위험도 (0~1)
			risk_factor = 0.5 * vol_factor + 0.3 * vol_spike_factor + 0.2 * max_ret_factor
			risk_factor = float(max(0.0, min(1.0, risk_factor)))

			# 최종 risk_score: 데이터 양(confidence) + 시장 상태(risk_factor) 통합
			risk_score = 0.5 * (1.0 - confidence) + 0.5 * risk_factor
			risk_score = float(max(0.0, min(1.0, risk_score)))

			# ----------------------
			# 파라미터 조정 (position_size, leverage, stop_loss_pct, TP/TS)
			# ----------------------
			params_new = dict(base_params_merged)

			# SL 기본값이 없으면 보수적으로 설정
			if "stop_loss_pct" not in params_new:
				params_new["stop_loss_pct"] = 0.02
			# TP/TS 기본값 자동 설정
			if "take_profit_pct" not in params_new:
				params_new["take_profit_pct"] = params_new["stop_loss_pct"] * 2.5
			if "trailing_stop_pct" not in params_new:
				params_new["trailing_stop_pct"] = params_new["stop_loss_pct"] * 1.0

			# position_size: risk_score 높을수록 축소 (최소 0.1%)
			base_pos = float(params_new.get("position_size", base_params.get("position_size", 0.02)) or 0.02)
			pos_adj = base_pos * (1.0 - 0.7 * risk_score)
			pos_adj = float(max(0.001, min(base_pos, pos_adj)))
			params_new["position_size"] = pos_adj

			# leverage: 신규 상장 상한 L_max 내에서 risk_score 높을수록 1x에 가깝게
			L_max = float(getattr(config, "NEW_LISTING_MAX_LEVERAGE", 5) or 5)
			L_max = max(1.0, L_max)
			lev_adj = 1.0 + (L_max - 1.0) * (1.0 - 0.8 * risk_score)
			lev_adj = float(max(1.0, min(L_max, lev_adj)))
			params_new["leverage"] = lev_adj

			# stop_loss_pct: 변동성이 클수록 너무 타이트하지 않게 약간 완화
			base_sl = float(params_new.get("stop_loss_pct", 0.02) or 0.02)
			sl_adj = base_sl * (1.0 + 0.5 * risk_score)
			params_new["stop_loss_pct"] = sl_adj

			# TP/TS 를 SL 조정값 기준으로 재조정 (너무 과격하지 않게 범위 제한)
			tp_base = float(params_new.get("take_profit_pct", sl_adj * 2.5) or sl_adj * 2.5)
			tp_adj = max(sl_adj * 1.5, min(sl_adj * 4.0, tp_base))
			params_new["take_profit_pct"] = tp_adj
			ts_base = float(params_new.get("trailing_stop_pct", sl_adj) or sl_adj)
			ts_adj = max(sl_adj * 0.5, min(sl_adj * 1.5, ts_base))
			params_new["trailing_stop_pct"] = ts_adj

			# 신규 상장 전략 시뮬레이션 (단일 시나리오)
			try:
				sim_res_new = core_run_backtest(
					symbol=symbol,
					interval=interval,
					df=df,
					initial_balance=initial_balance,
					leverage=leverage,
					params=params_new,
				)
				profit_pct_new = float(sim_res_new.get("profit_percentage", 0.0) or 0.0)
				max_dd_new = float(sim_res_new.get("max_drawdown_pct", 0.0) or 0.0)
				total_trades_new = int(sim_res_new.get("total_trades", 0) or 0)
				win_rate_new = float(sim_res_new.get("win_rate", 0.0) or 0.0)
				best_metrics_new = {
					"profit_percentage": profit_pct_new,
					"max_drawdown_pct": max_dd_new,
					"total_trades": total_trades_new,
					"win_rate": win_rate_new,
					"aborted_early": bool(sim_res_new.get("aborted_early", False)),
					"insufficient_trades": bool(sim_res_new.get("insufficient_trades", False)),
				}
				best_parameters_new = dict(params_new)
				new_listing_strategy_applied = True
			except Exception as e:
				# 시뮬레이션 실패 시에도 팝업은 뜨도록 보수적 메트릭 사용
				logger.exception("strategy-analysis new-listing simulation error for %s: %s", symbol, e)
				best_metrics_new = {
					"profit_percentage": 0.0,
					"max_drawdown_pct": 0.0,
					"total_trades": 0,
					"win_rate": 0.0,
					"aborted_early": True,
					"insufficient_trades": True,
				}
				best_parameters_new = dict(params_new)

			# 신규 상장 응답용 메타 정보 구성
			max_dd_pct_new = float(best_metrics_new.get("max_drawdown_pct", 0.0) or 0.0)
			liq_protection_new = max(0.0, min(50.0, max_dd_pct_new * 1.5))
			best_parameters_new["liquidation_protection_pct"] = liq_protection_new
			best_parameters_new["direction"] = "LONG"

			new_listing_strategy = {
				"base_parameters": base_params_merged,
				"adjusted_parameters": best_parameters_new,
				"confidence": confidence,
				"risk_factor": risk_factor,
				"risk_score": risk_score,
				"triggered_strategies": triggered_names,
				"notes": heur.get("notes", []),
			}

			recommended_leverage_new = _compute_recommended_leverage(best_metrics_new)

			response_data_new = {
				"symbol": symbol,
				"period": period,
				"interval": interval,
				"volatility": volatility,
				"best_parameters": best_parameters_new,
				"performance": best_metrics_new,
				"leverage_recommendation": recommended_leverage_new,
				"listing_meta": {
					"days_since_listing": days_since_listing,
					"is_new_listing": True,
					"new_listing_strategy_applied": bool(new_listing_strategy_applied),
				},
				"new_listing_strategy": new_listing_strategy,
			}

			return {"data": response_data_new}
		except Exception as e:
			# 신규 상장 휴리스틱 자체가 실패하면 일반 심볼 경로로 폴백
			logger.exception("strategy-analysis new-listing heuristic error for %s: %s", symbol, e)

	# ------------------------------------------------------------------
	# 일반 심볼: 환경 5 시나리오 (S1~S5)
	# ------------------------------------------------------------------
	best_combo_s1: Dict[str, Any] | None = None
	best_metrics_s1: Dict[str, Any] | None = None
	best_score_s1 = float("-inf")

	def _run_grid_search(df_local) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None, float]:
		best_c: Dict[str, Any] | None = None
		best_m: Dict[str, Any] | None = None
		best_s = float("-inf")
		for tp in tp_candidates:
			for sl in sl_candidates:
				for ts in ts_candidates:
					params_local = dict(base_params)
					params_local.update({
						"take_profit_pct": tp,
						"stop_loss_pct": sl,
						"trailing_stop_pct": ts,
					})
					try:
						sim_res_local = core_run_backtest(
								symbol=symbol,
								interval=interval,
								df=df_local,
								initial_balance=initial_balance,
								leverage=leverage,
								params=params_local,
						)
					except Exception as e:
						logger.exception(
							"strategy-analysis simulation error for %s (tp=%s, sl=%s, ts=%s): %s",
							symbol,
							tp,
							sl,
							ts,
							e,
						)
						continue

					profit_pct_local = float(sim_res_local.get("profit_percentage", 0.0) or 0.0)
					max_dd_local = float(sim_res_local.get("max_drawdown_pct", 0.0) or 0.0)
					total_trades_local = int(sim_res_local.get("total_trades", 0) or 0)
					win_rate_local = float(sim_res_local.get("win_rate", 0.0) or 0.0)

					penalty_local = 0.0
					if total_trades_local < 5:
						penalty_local += 5.0
					score_local = profit_pct_local - 0.5 * max_dd_local - penalty_local

					if score_local > best_s:
						best_s = score_local
						best_c = {"take_profit_pct": tp, "stop_loss_pct": sl, "trailing_stop_pct": ts}
						best_m = {
							"profit_percentage": profit_pct_local,
							"max_drawdown_pct": max_dd_local,
							"total_trades": total_trades_local,
							"win_rate": win_rate_local,
							"aborted_early": bool(sim_res_local.get("aborted_early", False)),
							"insufficient_trades": bool(sim_res_local.get("insufficient_trades", False)),
						}
		return best_c, best_m, best_s

	# S1: 기본 기간 전체
	best_combo_s1, best_metrics_s1, best_score_s1 = _run_grid_search(df)
	if not best_combo_s1 or not best_metrics_s1:
		logger.warning("strategy-analysis: no valid simulation results for %s; using fallback parameters (S1)", symbol)
		best_combo_s1 = {
			"take_profit_pct": tp_candidates[0],
			"stop_loss_pct": sl_candidates[0],
			"trailing_stop_pct": ts_candidates[0],
		}
		best_metrics_s1 = {
			"profit_percentage": 0.0,
			"max_drawdown_pct": 0.0,
			"total_trades": 0,
			"win_rate": 0.0,
			"aborted_early": False,
			"insufficient_trades": True,
		}

	# S2: 최근 24h 전체 (가능한 경우)
	s2_combo: Dict[str, Any] | None = None
	s2_metrics: Dict[str, Any] | None = None
	s2_valid = False
	try:
		start_ms_24h = now_ms - 24 * 60 * 60 * 1000
		await svc.data_loader.load_historical_klines(symbol, interval, start_ms_24h, now_ms)
		df_24h = await svc.data_loader.get_klines_for_backtest(symbol, interval, start_ms_24h, now_ms)
		if df_24h is not None and not df_24h.empty:
			s2_combo, s2_metrics, _ = _run_grid_search(df_24h)
			if s2_combo and s2_metrics:
				s2_valid = True
	except Exception as e:
		logger.exception("strategy-analysis S2 (24h) error for %s: %s", symbol, e)

	# S3/S4: 기본 기간 내 고변동/저변동 구간
	from math import isfinite

	s3_combo: Dict[str, Any] | None = None
	s3_metrics: Dict[str, Any] | None = None
	s3_valid = False
	s4_combo: Dict[str, Any] | None = None
	s4_metrics: Dict[str, Any] | None = None
	s4_valid = False

	try:
		if returns is not None:
			abs_ret = returns.abs().fillna(0)
			if len(abs_ret) >= 10 and abs_ret.max() > 0:
				q_high = float(abs_ret.quantile(0.8))
				q_low = float(abs_ret.quantile(0.2))
				if not isfinite(q_high):
					q_high = 0.0
				if not isfinite(q_low):
					q_low = 0.0

				# S3: 고변동
				mask_high = abs_ret >= q_high if q_high > 0 else abs_ret > 0
				df_high = df.loc[mask_high]
				min_candles = int(getattr(config, "MIN_REQUIRED_CANDLES_FOR_ANALYSIS", 60) or 60)
				if df_high is not None and not df_high.empty and len(df_high) >= min_candles:
					s3_combo, s3_metrics, _ = _run_grid_search(df_high)
					if s3_combo and s3_metrics:
						s3_valid = True

				# S4: 저변동
				mask_low = abs_ret <= q_low
				df_low = df.loc[mask_low]
				if df_low is not None and not df_low.empty and len(df_low) >= min_candles:
					s4_combo, s4_metrics, _ = _run_grid_search(df_low)
					if s4_combo and s4_metrics:
						s4_valid = True
	except Exception as e:
		logger.exception("strategy-analysis S3/S4 (volatility buckets) error for %s: %s", symbol, e)

	# S1 기반 기본 파라미터/레버리지 추천
	max_dd_pct_s1 = float(best_metrics_s1.get("max_drawdown_pct", 0.0) or 0.0)
	liquidation_protection_pct = max(0.0, min(50.0, max_dd_pct_s1 * 1.5))

	best_parameters_s1 = dict(best_combo_s1)
	best_parameters_s1.update({
		"liquidation_protection_pct": liquidation_protection_pct,
		"direction": "LONG",
	})

	recommended_leverage_s1 = _compute_recommended_leverage(best_metrics_s1)

	# S5: 공격적 레버리지 가상 시나리오 (참고용)
	s5_status = "insufficient_data"
	s5_leverage_x = None
	s5_est_loss_pct = None
	try:
		max_dd_frac_s1 = max_dd_pct_s1 / 100.0 if max_dd_pct_s1 and max_dd_pct_s1 > 0 else 0.0
		leverage_candidates = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
		max_equity_loss_frac_aggr = 1.0  # 100% 까지 허용하는 공격적 가정 (참고용)
		if max_dd_frac_s1 > 0:
			allowed_aggr: list[tuple[int, float]] = []
			for L in leverage_candidates:
				loss_frac = max_dd_frac_s1 * L
				if loss_frac <= max_equity_loss_frac_aggr:
					allowed_aggr.append((L, loss_frac))
			if allowed_aggr:
				s5_leverage_x, loss_frac = allowed_aggr[-1]
				s5_status = "ok"
				s5_est_loss_pct = loss_frac * 100.0
			else:
				# 심지어 5x 도 100% 이상 손실이라면, 수치상 의미 없음
				s5_status = "drawdown_too_high"
		else:
			s5_status = "insufficient_data"
	except Exception:
		s5_status = "error"

	scenarios: Dict[str, Any] = {
		"S1": {
			"label": "base_window",
			"period": period,
			"parameters": best_parameters_s1,
			"performance": best_metrics_s1,
		},
		"S2": {
			"label": "last_24h",
			"valid": bool(s2_valid),
			"parameters": s2_combo,
			"performance": s2_metrics,
		},
		"S3": {
			"label": "high_volatility_bucket",
			"valid": bool(s3_valid),
			"parameters": s3_combo,
			"performance": s3_metrics,
		},
		"S4": {
			"label": "low_volatility_bucket",
			"valid": bool(s4_valid),
			"parameters": s4_combo,
			"performance": s4_metrics,
		},
		"S5": {
			"label": "aggressive_leverage_virtual",
			"status": s5_status,
			"aggressive_leverage_x": s5_leverage_x,
			"estimated_equity_loss_pct_at_max_drawdown": s5_est_loss_pct,
			"max_equity_loss_limit_pct": 100.0,
		},
	}

	response_data = {
		"symbol": symbol,
		"period": period,
		"interval": interval,
		"volatility": volatility,
		"best_parameters": best_parameters_s1,
		"performance": best_metrics_s1,
		"leverage_recommendation": recommended_leverage_s1,
		"listing_meta": {
			"days_since_listing": days_since_listing,
			"is_new_listing": False,
			"new_listing_strategy_applied": False,
		},
		"scenarios": scenarios,
	}

	return {"data": response_data}


@router.post("/assign_strategy", response_model=StrategyAssignmentRead)
async def assign_strategy(
	payload: StrategyAssignmentCreate,
	svc=Depends(get_backtest_service),
) -> Any:
	"""Persist selected parameters and assign symbol to an engine.

	This endpoint is intended to be called from the GUI after
	/strategy-analysis, using one engine's executable_parameters as `parameters`.
	"""
	try:
		return await svc.assign_strategy(payload)
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))


@router.delete("/assignments/{symbol}")
async def unassign_strategy(symbol: str, svc=Depends(get_backtest_service)) -> Any:
	await svc.unassign_strategy(symbol)
	return {"message": f"assignment for {symbol} removed (if existed)"}


@router.get("/assignments/by_symbol/{symbol}", response_model=StrategyAssignmentRead)
async def get_assignment_for_symbol(symbol: str, svc=Depends(get_backtest_service)) -> Any:
	assignment = await svc.get_assignment_for_symbol(symbol)
	if assignment is None:
		raise HTTPException(status_code=404, detail="assignment not found")
	return assignment


@router.get("/assignments/by_engine/{engine}", response_model=StrategyAssignmentListResponse)
async def list_assignments_for_engine(engine: str, svc=Depends(get_backtest_service)) -> Any:
	return await svc.list_assignments_for_engine(engine)
