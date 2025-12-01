"""Strategy Orchestrator - 메인 루프(단일 심볼) 통합"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable
import logging
import time
import asyncio
import threading

from .data_structures import (
    Candle,
    PositionState,
    PositionSide,
    SignalResult,
)
from .data_fetcher import BinanceDataFetcher
from .indicator_engine import IndicatorEngine
from .signal_engine import SignalEngine
from .risk_manager import RiskManager, RiskManagerConfig
from .execution_adapter import ExecutionAdapter

# 전략 전용 로거 사용
from backend.utils.strategy_logger import (
    setup_strategy_logger,
    log_trade_event,
    log_risk_event,
    log_signal_event,
)

logger = setup_strategy_logger("Orchestrator")


@dataclass
class OrchestratorConfig:
    symbol: str
    leverage: int = 50
    interval_entry: str = "1m"
    interval_confirm: str = "3m"
    interval_filter: str = "15m"
    candles_required: int = 200
    order_quantity: float = 0.001  # 고정 수량 (테스트용)
    isolated_margin: bool = True
    loop_interval_sec: float = 1.0  # 루프 주기
    enable_trading: bool = True  # False면 신호만 생성 (주문 실행 안함)
    adaptive_enabled: bool = False  # 동적 임계치 사용 여부
    protective_pause_enabled: bool = False
    failure_threshold: int = 10  # 보호 모드 진입 실패 횟수 (window 내)
    failure_window_sec: int = 60
    protective_pause_duration_sec: int = 60


class StrategyOrchestrator:
    """
    DataFetcher → IndicatorEngine → SignalEngine → RiskManager → ExecutionAdapter
    단일 심볼에 대해 1 스텝씩 실행하는 오케스트레이션 레이어.
    """

    def __init__(
        self,
        binance_client,
        fetcher: Optional[BinanceDataFetcher] = None,
        indicator: Optional[IndicatorEngine] = None,
        signal: Optional[SignalEngine] = None,
        risk: Optional[RiskManager] = None,
        executor: Optional[ExecutionAdapter] = None,
        config: Optional[OrchestratorConfig] = None,
        auto_prepare_symbol: bool = False,
    ):
        self.client = binance_client
        self.fetcher = fetcher or BinanceDataFetcher(self.client)
        self.indicator = indicator or IndicatorEngine()
        self.signal = signal or SignalEngine()
        self.risk = risk or RiskManager(RiskManagerConfig())
        self.exec = executor or ExecutionAdapter(self.client)
        self.cfg = config or OrchestratorConfig(symbol="BTCUSDT")

        # 상태
        self.position: Optional[PositionState] = None
        self.prev_ind_1m: Optional[Any] = None
        self.last_signal: Optional[SignalResult] = None
        self._protective_active_until: Optional[float] = None
        self._recent_failures = []  # 타임스탬프(ms)
        self._risk_events = []  # 리스크 이벤트 수집용

        # Adaptive thresholds
        from .adaptive_thresholds import AdaptiveThresholdManager
        self._adaptive = AdaptiveThresholdManager() if self.cfg.adaptive_enabled else None
        
        # Risk event callback 설정
        self.risk.set_risk_event_callback(self._on_risk_event)
        
        # 마지막 캔들 업데이트 시간 추적 (타임스탬프 기반 스마트 업데이트용)
        self._last_candle_times = {
            self.cfg.interval_entry: 0,    # 1m
            self.cfg.interval_confirm: 0,  # 3m
            self.cfg.interval_filter: 0,   # 15m
        }
        
        # 연속 실행 제어
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._thread: Optional[threading.Thread] = None
        self._event_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        # 심볼 준비 (마진/레버리지) - 옵션으로 변경
        # "설정 적용" 버튼에서 명시적으로 prepare_symbol() 호출하도록 변경
        if auto_prepare_symbol:
            ok = self.exec.prepare_symbol(self.cfg.symbol, leverage=self.cfg.leverage, isolated=self.cfg.isolated_margin)
            if not ok:
                logger.warning("심볼 준비 실패 (마진/레버리지). 진행은 계속하지만 주문 시 실패할 수 있습니다.")
        else:
            logger.debug(f"[Orchestrator] 심볼 자동 준비 비활성화 - 수동으로 prepare_symbol() 호출 필요")

    def _compute_indicators(self, interval: str):
        candles = self.fetcher.cache.get_latest_candles(self.cfg.symbol, interval, self.indicator.required_candles)
        return self.indicator.calculate(candles)

    def _emit_event(self, payload: Dict[str, Any]):
        if self._event_callback:
            try:
                self._event_callback({"events": [payload]})
            except Exception as e:
                logger.error(f"[Orchestrator] 이벤트 콜백 오류: {e}")

    def _on_risk_event(self, event: Dict[str, Any]):
        """리스크 매니저로부터 이벤트 수신"""
        self._risk_events.append(event)
        self._emit_event(event)

    def _symbol_support_check(self) -> bool:
        info = self.client.is_symbol_supported(self.cfg.symbol)
        if not info.get("supported"):
            self._emit_event({
                "type": "SYMBOL_UNSUPPORTED",
                "symbol": self.cfg.symbol,
                "reason": info.get("reason")
            })
            return False
        return True

    def _maybe_emit_data_progress(self):
        req = self.indicator.required_candles
        intervals = []
        for itv in [self.cfg.interval_entry, self.cfg.interval_confirm, self.cfg.interval_filter]:
            cache = self.fetcher.cache._cache[self.cfg.symbol][itv]
            have = len(cache)
            intervals.append({"interval": itv, "have": have, "required": req, "ready": have >= req})
        # Ready 여부 중 하나라도 False면 진행률 이벤트 전송
        if not all(x["ready"] for x in intervals):
            self._emit_event({
                "type": "DATA_PROGRESS",
                "symbol": self.cfg.symbol,
                "intervals": intervals
            })

    def _register_failure(self):
        if not self.cfg.protective_pause_enabled:
            return
        now = time.time()
        self._recent_failures.append(now)
        # window 유지
        window_start = now - self.cfg.failure_window_sec
        self._recent_failures = [t for t in self._recent_failures if t >= window_start]
        if self._protective_active_until and now < self._protective_active_until:
            return
        if len(self._recent_failures) >= self.cfg.failure_threshold:
            self._protective_active_until = now + self.cfg.protective_pause_duration_sec
            self._emit_event({
                "type": "PROTECTIVE_PAUSE",
                "symbol": self.cfg.symbol,
                "failures_last_window": len(self._recent_failures),
                "window_sec": self.cfg.failure_window_sec
            })
            logger.warning("보호 모드 진입: API 실패 빈도 초과")

    def _protective_active(self) -> bool:
        return bool(self._protective_active_until and time.time() < self._protective_active_until)
    
    def _should_update_candle(self, interval: str) -> bool:
        """
        캔들이 종료되었는지 확인 (타임스탬프 기반)
        
        Args:
            interval: 타임프레임 ("1m", "3m", "15m")
        
        Returns:
            True: 새 캔들 생성 (API 호출 필요)
            False: 아직 진행 중 (캐시 사용)
        """
        # 현재 시간 (밀리초)
        now_ms = int(time.time() * 1000)
        
        # 타임프레임별 간격 (밀리초)
        intervals_ms = {
            "1m": 60 * 1000,
            "3m": 3 * 60 * 1000,
            "15m": 15 * 60 * 1000,
        }
        
        interval_ms = intervals_ms.get(interval, 60000)
        
        # 현재 캔들의 시작 시간 계산
        # 예: 현재 14:32:45 → 1m 캔들은 14:32:00 시작
        current_candle_start = (now_ms // interval_ms) * interval_ms
        
        # 마지막 업데이트 시간과 비교
        last_update = self._last_candle_times.get(interval, 0)
        
        if current_candle_start > last_update:
            # 새 캔들 시작 → 이전 캔들 종료
            self._last_candle_times[interval] = current_candle_start
            logger.debug(f"[Orchestrator] 새 캔들 감지: {interval} @ {current_candle_start}")
            return True
        
        return False

    async def warmup(self):
        # 심볼 지원 검사
        if not self._symbol_support_check():
            raise RuntimeError("Unsupported symbol")
        # 필요한 캔들 캐시에 적재
        await self.fetcher.fetch_historical_candles(self.cfg.symbol, self.cfg.interval_entry, limit=max(self.indicator.required_candles, self.cfg.candles_required))
        await self.fetcher.fetch_historical_candles(self.cfg.symbol, self.cfg.interval_confirm, limit=max(self.indicator.required_candles, self.cfg.candles_required))
        await self.fetcher.fetch_historical_candles(self.cfg.symbol, self.cfg.interval_filter, limit=max(self.indicator.required_candles, self.cfg.candles_required))
        self._maybe_emit_data_progress()

    def step(self) -> Dict[str, Any]:
        """한 스텝 실행 (동기). 사전 warmup 이후 사용 권장."""
        symbol = self.cfg.symbol

        # 타임스탬프 기반 스마트 캔들 업데이트
        # 캔들 종료 시점에만 최신 캔들 1개 API 호출 (API 호출 최소화)
        
        # 1분봉 체크 (매 1분마다 업데이트)
        if self._should_update_candle(self.cfg.interval_entry):
            asyncio.run(self.fetcher.fetch_historical_candles(
                symbol, self.cfg.interval_entry, limit=1
            ))
        
        # 3분봉 체크 (매 3분마다 업데이트)
        if self._should_update_candle(self.cfg.interval_confirm):
            asyncio.run(self.fetcher.fetch_historical_candles(
                symbol, self.cfg.interval_confirm, limit=1
            ))
        
        # 15분봉 체크 (매 15분마다 업데이트)
        if self._should_update_candle(self.cfg.interval_filter):
            asyncio.run(self.fetcher.fetch_historical_candles(
                symbol, self.cfg.interval_filter, limit=1
            ))
        
        # 캐시 부족 시 fallback (안전장치 - Warmup 실패 시 대비)
        if not self.fetcher.cache.has_sufficient_data(symbol, self.cfg.interval_entry, self.indicator.required_candles):
            asyncio.run(self.fetcher.fetch_historical_candles(symbol, self.cfg.interval_entry, limit=self.indicator.required_candles))
        if not self.fetcher.cache.has_sufficient_data(symbol, self.cfg.interval_confirm, self.indicator.required_candles):
            asyncio.run(self.fetcher.fetch_historical_candles(symbol, self.cfg.interval_confirm, limit=self.indicator.required_candles))
        if not self.fetcher.cache.has_sufficient_data(symbol, self.cfg.interval_filter, self.indicator.required_candles):
            asyncio.run(self.fetcher.fetch_historical_candles(symbol, self.cfg.interval_filter, limit=self.indicator.required_candles))

        ind_1m = self._compute_indicators(self.cfg.interval_entry)
        ind_3m = self._compute_indicators(self.cfg.interval_confirm)
        ind_15m = self._compute_indicators(self.cfg.interval_filter)

        # Adaptive thresholds 적용
        if self._adaptive:
            self._adaptive.add_score(self.last_signal.score if self.last_signal else 0.0)
            min_t, strong_t, instant_t = self._adaptive.get_thresholds(
                self.signal.config.min_entry_score,
                self.signal.config.strong_entry_score,
                self.signal.config.instant_entry_score
            )
            self.signal.config.min_entry_score = min_t
            self.signal.config.strong_entry_score = strong_t
            self.signal.config.instant_entry_score = instant_t
            self._emit_event({
                "type": "THRESHOLD_UPDATE",
                "symbol": self.cfg.symbol,
                "min": min_t,
                "strong": strong_t,
                "instant": instant_t
            })

        last_close = self.fetcher.cache.get_latest_candle(symbol, self.cfg.interval_entry).close

        # 진입/유지 평가
        sig = self.signal.evaluate(
            current_1m=ind_1m,
            last_close=last_close,
            prev_1m=self.prev_ind_1m,
            confirm_3m=ind_3m,
            filter_15m=ind_15m,
            in_position=self.position is not None,
        )

        events = []

        if self.position is None and not self._protective_active():
            # 진입 시도
            if sig.action.name == "BUY_LONG":
                order = self.exec.place_market_long(symbol, self.cfg.order_quantity)
                if order.ok:
                    entry = order.avg_price or last_close
                    ts = ind_1m.timestamp
                    self.position = PositionState(
                        symbol=symbol,
                        side=PositionSide.LONG,
                        entry_price=entry,
                        quantity=order.executed_qty or self.cfg.order_quantity,
                        leverage=self.cfg.leverage,
                        opened_at=ts,
                        highest_price=entry,
                        lowest_price=entry,
                        unrealized_pnl=0.0,
                        unrealized_pnl_pct=0.0,
                        stop_loss_price=entry * (1.0 - self.risk.config.stop_loss_pct),
                        take_profit_price=entry * (1.0 + self.risk.config.tp_extended_pct),
                        trailing_activated=False,
                    )
                    events.append({"type": "ENTRY", "order_id": order.order_id, "price": entry})
                else:
                    events.append({"type": "ENTRY_FAIL", "error": order.error_message})
            else:
                events.append({"type": "HOLD"})
                # Watchlist 이벤트 (점수 기준)
                if sig.action.name == "HOLD" and sig.score >= self.signal.config.min_entry_score and sig.score < self.signal.config.strong_entry_score:
                    events.append({
                        "type": "WATCHLIST",
                        "score": sig.score,
                        "triggers": sig.triggers
                    })
        elif self.position is None and self._protective_active():
            events.append({"type": "PAUSE"})
        else:
            # 리스크 이벤트 초기화
            self._risk_events.clear()
            
            # 리스크 관리 평가
            exit_sig = self.risk.evaluate(
                position=self.position,
                current_price=last_close,
                indicators_1m=ind_1m,
                last_signal=self.last_signal,
                now_ms=ind_1m.timestamp,
            )
            
            # 리스크 이벤트 병합 (TRAILING_ACTIVATED 등)
            events.extend(self._risk_events)
            
            if exit_sig:
                order = self.exec.close_market_long(symbol)
                if order.ok:
                    events.append({"type": "EXIT", "reason": exit_sig.reason.value, "price": order.avg_price})
                else:
                    events.append({"type": "EXIT_FAIL", "reason": exit_sig.reason.value, "error": order.error_message})
                self.position = None
            else:
                events.append({"type": "HOLD_IN_POSITION", "pnl_pct": self.position.unrealized_pnl_pct})

        self.prev_ind_1m = ind_1m
        self.last_signal = sig

        return {
            "signal_action": sig.action.value,
            "signal_score": sig.score,
            "events": events,
            "position": None if self.position is None else {
                "entry": self.position.entry_price,
                "stop": self.position.stop_loss_price,
                "tp": self.position.take_profit_price,
                "pnl_pct": self.position.unrealized_pnl_pct,
            }
        }

    def set_event_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """이벤트 발생 시 호출할 콜백 함수 설정"""
        self._event_callback = callback

    async def run_forever(self):
        """
        1초 간격 무한 루프 (비동기)
        Ctrl+C 또는 stop() 호출 시 종료
        """
        logger.info(f"[Orchestrator] 연속 실행 시작: {self.cfg.symbol}, {self.cfg.loop_interval_sec}초 간격")
        
        # Warmup: 초기 데이터 로드
        try:
            await self.warmup()
            logger.info("[Orchestrator] Warmup 완료")
        except Exception as e:
            logger.error(f"[Orchestrator] Warmup 실패: {e}", exc_info=True)
            self._running = False  # 상태 명시적 설정
            
            # 에러 이벤트 콜백 전송
            if self._event_callback:
                try:
                    self._event_callback({
                        "events": [{
                            "type": "WARMUP_FAIL",
                            "error": str(e),
                            "symbol": self.cfg.symbol
                        }]
                    })
                except Exception as cb_err:
                    logger.error(f"[Orchestrator] 콜백 전송 실패: {cb_err}")
            
            return

        self._running = True
        step_count = 0

        try:
            while self._running:
                step_count += 1
                start_time = time.time()

                try:
                    result = self.step()
                    
                    # 이벤트 콜백 호출
                    if self._event_callback:
                        try:
                            self._event_callback(result)
                        except Exception as e:
                            logger.error(f"[Orchestrator] 이벤트 콜백 오류: {e}")
                    
                    # 주요 이벤트 로깅
                    for event in result.get("events", []):
                        event_type = event.get("type")
                        if event_type == "ENTRY":
                            log_trade_event(
                                logger, "ENTRY", self.cfg.symbol,
                                price=event.get('price'),
                                order_id=event.get('order_id')
                            )
                        elif event_type == "EXIT":
                            log_trade_event(
                                logger, "EXIT", self.cfg.symbol,
                                price=event.get('price'),
                                reason=event.get('reason')
                            )
                        elif event_type == "ENTRY_FAIL":
                            logger.error(f"❌ 진입 실패: {event.get('error')}")
                        elif event_type == "EXIT_FAIL":
                            logger.error(f"❌ 청산 실패: {event.get('error')}")
                
                except Exception as e:
                    logger.error(f"[Orchestrator] Step 실행 오류 (#{step_count}): {e}", exc_info=True)

                # 주기 유지
                elapsed = time.time() - start_time
                sleep_time = max(0, self.cfg.loop_interval_sec - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"[Orchestrator] Step 처리 시간 초과: {elapsed:.2f}초 > {self.cfg.loop_interval_sec}초")

        except asyncio.CancelledError:
            logger.info("[Orchestrator] 비동기 태스크 취소됨")
        except KeyboardInterrupt:
            logger.info("[Orchestrator] 사용자 중단 (Ctrl+C)")
        finally:
            self._running = False
            logger.info(f"[Orchestrator] 연속 실행 종료 (총 {step_count} 스텝)")

    def start(self):
        """
        백그라운드 스레드에서 run_forever() 실행
        
        GUI/Backend와 분리하여 비동기 루프 실행
        """
        if self._running:
            logger.warning("[Orchestrator] 이미 실행 중입니다")
            return

        def _run_async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.run_forever())
            except Exception as e:
                logger.error(f"[Orchestrator] 비동기 루프 오류: {e}", exc_info=True)
            finally:
                loop.close()

        self._thread = threading.Thread(target=_run_async_loop, name="OrchestratorThread", daemon=True)
        self._thread.start()
        logger.info("[Orchestrator] 백그라운드 스레드 시작")

    def stop(self, force_close_position: bool = True):
        """
        안전 종료: 실행 중인 루프 중지 및 포지션 청산
        
        Args:
            force_close_position: True면 포지션 자동 청산, False면 경고만 출력
        """
        if not self._running:
            logger.warning("[Orchestrator] 실행 중이 아닙니다")
            return

        logger.info("[Orchestrator] 종료 신호 전송...")
        
        # 포지션 자동 청산 (사용자 의도: 거래 정지 시 포지션 즉시 시장가 청산)
        if self.position and force_close_position:
            logger.info(f"[Orchestrator] 포지션 보유 중 - 자동 청산 시작: {self.cfg.symbol}")
            logger.info(f"  진입가: {self.position.entry_price}, 수량: {self.position.quantity}")
            
            try:
                # 시장가 청산 실행
                result = self.exec.close_market_long(self.cfg.symbol)
                
                if result.ok:
                    logger.info(f"✅ 포지션 청산 성공: {self.cfg.symbol}")
                    logger.info(f"  청산가: {result.avg_price}, 체결량: {result.executed_qty}")
                    
                    # 포지션 정리
                    self.position = None
                    
                    # 이벤트 콜백 전송
                    if self._event_callback:
                        try:
                            self._event_callback({
                                "events": [{
                                    "type": "EXIT",
                                    "reason": "FORCE_STOP",
                                    "price": result.avg_price,
                                    "quantity": result.executed_qty,
                                    "symbol": self.cfg.symbol
                                }]
                            })
                        except Exception as cb_err:
                            logger.error(f"[Orchestrator] 콜백 전송 실패: {cb_err}")
                else:
                    logger.error(f"❌ 포지션 청산 실패: {result.error_message}")
                    logger.warning("⚠️  수동으로 Binance에서 청산하세요!")
                    
            except Exception as e:
                logger.error(f"❌ 포지션 청산 중 예외 발생: {e}", exc_info=True)
                logger.warning("⚠️  수동으로 Binance에서 청산하세요!")
        
        elif self.position and not force_close_position:
            logger.warning(f"⚠️  포지션 보유 중 종료: {self.cfg.symbol} @ {self.position.entry_price}")
            logger.warning("⚠️  수동으로 포지션을 청산하거나, 다음 재시작 시 자동 관리됩니다")
        
        # 엔진 정지
        self._running = False

        # 스레드 종료 대기 (최대 5초)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("[Orchestrator] 스레드 종료 타임아웃 (5초)")
            else:
                logger.info("[Orchestrator] 스레드 정상 종료")

    def is_running(self) -> bool:
        """실행 상태 확인"""
        return self._running

    def get_status(self) -> Dict[str, Any]:
        """현재 상태 조회 (API/GUI용)"""
        return {
            "running": self._running,
            "symbol": self.cfg.symbol,
            "position": None if self.position is None else {
                "side": self.position.side.value,
                "entry_price": self.position.entry_price,
                "quantity": self.position.quantity,
                "unrealized_pnl_pct": self.position.unrealized_pnl_pct,
                "stop_loss": self.position.stop_loss_price,
                "take_profit": self.position.take_profit_price,
                "trailing_activated": self.position.trailing_activated,
            },
            "last_signal": None if self.last_signal is None else {
                "action": self.last_signal.action.value,
                "score": self.last_signal.score,
                "confidence_pct": self.last_signal.confidence_pct,
                "triggers": self.last_signal.triggers,
            }
        }
