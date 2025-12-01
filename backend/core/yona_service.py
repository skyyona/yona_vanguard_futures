import asyncio
import datetime as dt
import aiosqlite
import os
from typing import Optional, Callable, Awaitable, Dict, Any, List
from backend.core.account_manager import AccountManager
from backend.core.session_manager import SessionManager
from backend.api_client.binance_client import BinanceClient
from backend.database.db_manager import DatabaseManager

class YonaService:
    """
    YONA Vanguard Futures의 핵심 백엔드 서비스.
    - 실시간 데이터 수집 및 분석
    - 자동 매매 엔진 관리 및 실행
    - GUI와의 WebSocket 통신
    """
    def __init__(self, logger):
        self.logger = logger
        self._broadcaster: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
        
        self._running = False
        self._main_task: Optional[asyncio.Task] = None
        self._analysis_active = False  # GUI의 START/STOP 버튼으로 제어
        
        # 계좌 관리자 및 세션 관리자
        self.account_manager = AccountManager()
        self.session_manager = SessionManager()
        
        # 바이낸스 클라이언트
        self.binance_client = BinanceClient()
        
        # 헤더 데이터 업데이트 간격 (초)
        self._header_update_interval = 3.0
        self._last_header_update = 0.0
        
        # 랭킹 데이터 업데이트 간격 (초)
        self._ranking_update_interval = 10.0
        self._last_ranking_update = 0.0
        
        # 심볼 상장일 정보 캐시 (symbol -> onboardDate timestamp)
        self._symbol_onboard_dates: Dict[str, int] = {}
        
        # 거래 가능 심볼 캐시 (TRADING/SETTLING 상태)
        self._cached_symbols: Optional[List[str]] = None
        
        # 시간 고정 기능 (누적 계산용)
        self._fixed_time: Optional[dt.datetime] = None
        self._fixed_change_percent_cache: Dict[str, float] = {}
        self._current_items: List[Dict[str, Any]] = []
        
        # 블랙리스트 기능
        self._blacklist: Dict[str, str] = {}  # symbol -> added_at_utc (ISO)
        self._db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "yona_vanguard.db")

        # 가용 자금 추적
        self._cash_balance: float = 0.0
        self._cash_balance_initialized: bool = False

        self.logger.info("YonaService 초기화 완료.")
        # 긴급 청산 동시 실행 방지 락
        import asyncio as _asyncio
        self._emergency_lock = _asyncio.Lock()

    def set_broadcaster(self, broadcaster: Callable[[Dict[str, Any]], Awaitable[None]]):
        self._broadcaster = broadcaster

    async def _broadcast(self, message: Dict[str, Any]):
        if self._broadcaster:
            await self._broadcaster(message)

    async def initialize(self):
        self.logger.info("YonaService 비동기 초기화 시작...")
        self._running = True
        
        # 마이그레이션 시스템 초기화 및 실행 (먼저 실행)
        db_manager = DatabaseManager(self._db_path)
        await db_manager.initialize()
        await db_manager.ensure_tables()
        
        # DB 초기화 및 블랙리스트 로드
        await self._init_database()
        await self._load_blacklist_cache()
        
        # 저장된 설정 로드
        await self._load_engine_settings()
        await self._load_app_settings()
        
        # 초기 상태를 connected_inactive로 브로드캐스트 (타이틀 주황색 설정)
        await self._broadcast({"type": "APP_STATUS_UPDATE", "data": {"status": "connected_inactive"}})
        
        self.logger.info("YonaService 비동기 초기화 완료.")

    def run_main_loop(self):
        if not self._main_task or self._main_task.done():
            self._main_task = asyncio.create_task(self._main_loop())
            self.logger.info("YonaService 메인 루프 시작.")

    async def _main_loop(self):
        import time
        while self._running:
            try:
                current_time = time.time()
                
                # 헤더 데이터는 항상 업데이트 (초기 실행 시에도 상단 헤더 작동)
                if current_time - self._last_header_update >= self._header_update_interval:
                    await self._update_header_data()
                    self._last_header_update = current_time
                
                # _analysis_active가 True일 때만 랭킹/SETTLING 업데이트 (START 버튼 클릭 후)
                if self._analysis_active:
                    # 랭킹 데이터 업데이트
                    if current_time - self._last_ranking_update >= self._ranking_update_interval:
                        await self._update_ranking_data()
                        self._last_ranking_update = current_time
                        
                        # SETTLING 코인 자동 검색 및 전송
                        try:
                            settling_data = await self._compute_settling_update()
                            if settling_data:
                                await self._broadcast({
                                    "type": "SETTLING_UPDATE",
                                    "data": settling_data
                                })
                        except Exception as e:
                            self.logger.warning(f"SETTLING_UPDATE 생성 실패: {e}")
                
                # Heartbeat는 항상 전송
                await self._broadcast({"type": "HEARTBEAT", "status": "running"})

            except Exception as e:
                self.logger.error(f"메인 루프 실행 중 오류 발생: {e}", exc_info=True)
            
            await asyncio.sleep(3)
    
    async def _update_header_data(self):
        """헤더 데이터를 업데이트하고 WebSocket으로 전송합니다."""
        try:
            # 이전 초기 자본 값 저장 (자동 설정 감지용)
            previous_initial_capital = self.account_manager.initial_capital
            previous_initial_capital_set = self.account_manager._initial_capital_set
            
            # 계좌 정보 업데이트
            account_updated = self.account_manager.update_account_info()
            
            # 초기 자본이 자동 설정되었으면 DB에 저장
            if not previous_initial_capital_set and self.account_manager._initial_capital_set:
                new_initial_capital = self.account_manager.initial_capital
                if new_initial_capital > 0:
                    await self._save_app_setting("initial_capital", new_initial_capital, "float")
                    self.logger.info(f"초기 자본 DB 저장 완료: {new_initial_capital:,.2f} USDT")
            
            if not account_updated:
                # API 조회 실패 시에도 기존 데이터로 전송 (에러 표시 안 함)
                pass
            
            # 헤더 데이터 가져오기
            header_data = self.account_manager.get_header_data()
            portfolio_metrics = self._compute_portfolio_metrics()
            header_data.update({
                "available_funds": portfolio_metrics["available_funds"],
                "total_trading_value": portfolio_metrics["total_trading_value"],
                "cumulative_return_percent": portfolio_metrics["cumulative_return_percent"],
                # 기존 필드 호환
                "total_balance": portfolio_metrics["available_funds"],
                "pnl_percent": portfolio_metrics["cumulative_return_percent"],
            })
            
            # 글로벌 세션 정보 추가
            global_session = self.session_manager.get_global_session()
            header_data["global_session"] = global_session
            
            # WebSocket으로 전송
            await self._broadcast({
                "type": "HEADER_UPDATE",
                "data": header_data
            })
            
        except Exception as e:
            self.logger.error(f"헤더 데이터 업데이트 중 오류 발생: {e}", exc_info=True)
    
    async def _update_ranking_data(self):
        """실시간 랭킹 데이터를 업데이트하고 WebSocket으로 전송합니다."""
        try:
            # TRADING/SETTLING 심볼 목록 확보 (status 필터링 포함)
            symbols = await self._ensure_trading_symbols()
            if not symbols:
                self.logger.warning("거래 가능한 심볼이 없습니다.")
                return
            
            # 블랙리스트 제외
            active_symbols = [s for s in symbols if s not in self._blacklist]
            self.logger.debug(f"활성 심볼: {len(active_symbols)}개 (전체: {len(symbols)}개, 블랙리스트: {len(self._blacklist)}개)")
            
            # 바이낸스에서 24시간 티커 데이터 조회
            ticker_data = self.binance_client.get_24hr_ticker()
            
            if isinstance(ticker_data, dict) and "error" in ticker_data:
                self.logger.warning(f"24시간 티커 조회 실패: {ticker_data.get('error')}")
                return
            
            if not isinstance(ticker_data, list):
                self.logger.warning(f"24시간 티커 데이터 형식 오류: {type(ticker_data)}")
                return
            
            # 티커 데이터를 딕셔너리로 변환 (빠른 조회)
            ticker_dict = {t.get("symbol"): t for t in ticker_data if t.get("symbol")}
            
            # 활성 심볼에 대해서만 랭킹 데이터 생성
            ranking_items = []
            for symbol in active_symbols:
                ticker = ticker_dict.get(symbol)
                if not ticker:
                    continue
                
                try:
                    # 실시간 상승률 (항상 계산)
                    real_time_change_percent = float(ticker.get("priceChangePercent", 0.0))
                    
                    # 시간고정 시 표시용 상승률 결정
                    if self._fixed_time and symbol in self._fixed_change_percent_cache:
                        display_change_percent = self._fixed_change_percent_cache[symbol]
                    else:
                        display_change_percent = real_time_change_percent
                    
                    # 신규 상장 정보 계산 (may perform DB/candle fallback)
                    days_since_listing = await self._calculate_days_since_listing(symbol)
                    listing_signal_status = self._determine_listing_signal_status(
                        display_change_percent, display_change_percent
                    )
                    
                    # 데이터 생성
                    item = {
                        "symbol": symbol,
                        "change_percent": display_change_percent,           # 표시용
                        "real_time_change_percent": real_time_change_percent,  # 계산용 (실시간)
                        "days_since_listing": days_since_listing,
                        "listing_signal_status": listing_signal_status,
                        "rank_change": 0,
                        "url": f"https://www.binance.com/en/futures/{symbol}"
                    }
                    ranking_items.append(item)
                    
                except (ValueError, TypeError) as e:
                    self.logger.debug(f"심볼 {symbol} 데이터 파싱 오류: {e}")
                    continue
            
            # 현재 items 저장 (시간고정 시 사용)
            self._current_items = ranking_items
            
            # 누적 및 상승유형 분석
            if self._fixed_time:
                # 시간고정 상태: 누적 = 실시간 - 고정시점
                for item in ranking_items:
                    symbol = item.get("symbol", "")
                    real_time_change = float(item.get("real_time_change_percent", 0.0))
                    fixed_change = self._fixed_change_percent_cache.get(symbol, 0.0)
                    
                    # 누적 계산: 시간고정 이후 순수 변동량
                    cumulative_percent = real_time_change - fixed_change
                    energy_type = self._analyze_energy_type(cumulative_percent)
                    
                    item["cumulative_percent"] = cumulative_percent
                    item["energy_type"] = energy_type
            else:
                # 시간고정 없을 때: 누적 "+000.00", 상승유형 "데이터 분석 중"
                for item in ranking_items:
                    item["cumulative_percent"] = "+000.00"
                    item["energy_type"] = "데이터 분석 중"
            
            # 정렬: 상승률 내림차순, 동률 시 심볼명 오름차순 (Binance Live vs1 방식)
            try:
                ranking_items.sort(key=lambda x: (-float(x.get("change_percent", 0.0)), str(x.get("symbol", ""))))
            except Exception as e:
                self.logger.warning(f"랭킹 정렬 실패: {e}")
                ranking_items.sort(key=lambda x: x.get("change_percent", 0.0), reverse=True)
            
            # WebSocket으로 전송
            await self._broadcast({
                "type": "RANKING_UPDATE",
                "data": ranking_items
            })
            
            self.logger.info(f"랭킹 데이터 업데이트 완료: {len(ranking_items)}개 심볼 (블랙리스트 제외)")
            
        except Exception as e:
            self.logger.error(f"랭킹 데이터 업데이트 중 오류 발생: {e}", exc_info=True)
    
    def _ensure_cash_balance_initialized(self) -> None:
        """초기 자본과 기존 배정 내역을 반영해 가용 자금 잔액 초기화"""
        if self._cash_balance_initialized:
            return
        initial_capital = float(self.account_manager.initial_capital or 0.0)
        if initial_capital <= 0:
            return
        total_allocated = self.account_manager.funds_allocation_manager.get_total_allocated()
        available = initial_capital - total_allocated
        self._cash_balance = max(available, 0.0)
        self._cash_balance_initialized = True
    
    async def _save_cash_balance(self) -> None:
        """가용 자금 잔액을 DB에 저장"""
        try:
            await self._save_app_setting("cash_balance", self._cash_balance, "float")
        except Exception as e:
            self.logger.warning(f"가용 자금 저장 실패: {e}")
    
    def _compute_portfolio_metrics(self) -> Dict[str, float]:
        """
        엔진 배분 상태를 기반으로 Available Funds / Total Trading Value 계산
        """
        from backend.core.engine_manager import get_engine_manager
        
        engine_manager = get_engine_manager()
        engine_allocations: Dict[str, float] = {}
        total_designated = 0.0
        
        if engine_manager:
            for name, engine in engine_manager.engines.items():
                funds = float(getattr(engine, "designated_funds", 0.0) or 0.0)
                funds = max(funds, 0.0)
                engine_allocations[name] = funds
                total_designated += funds
        
        initial_capital = float(self.account_manager.initial_capital or 0.0)
        self._ensure_cash_balance_initialized()
        available_funds = self._cash_balance
        total_trading_value = available_funds + total_designated
        cumulative_return_percent = 0.0
        if initial_capital > 0:
            cumulative_return_percent = ((total_trading_value / initial_capital) - 1.0) * 100.0
        
        return {
            "available_funds": available_funds,
            "total_trading_value": total_trading_value,
            "cumulative_return_percent": cumulative_return_percent
        }
    
    def _analyze_energy_type(self, cumulative_percent: float) -> str:
        """누적 상승률을 기반으로 상승유형을 분석"""
        if cumulative_percent > 0.8:
            return "급등"
        elif cumulative_percent > 0.3:
            return "지속 상승"
        elif cumulative_percent < -0.8:
            return "급락"
        elif cumulative_percent < -0.3:
            return "지속 하락"
        else:
            return "횡보"
    
    async def set_fixed_time(self, fixed_time_str: Optional[str]) -> None:
        """시간 고정/해제 설정"""
        if fixed_time_str:
            try:
                self._fixed_time = dt.datetime.fromisoformat(fixed_time_str)
                # 시간고정 시점의 현재 상승률을 캐시
                await self._cache_current_prices_for_fixed_time()
                self.logger.info(f"시간고정 설정: {self._fixed_time}")
            except Exception as e:
                self.logger.error(f"시간고정 파싱 실패: {e}")
                self._fixed_time = None
                self._fixed_change_percent_cache.clear()
        else:
            self._fixed_time = None
            self._fixed_change_percent_cache.clear()
            self.logger.info("시간고정 해제")
    
    async def _cache_current_prices_for_fixed_time(self) -> None:
        """시간고정 버튼 클릭 시점의 현재 상승률을 캐시"""
        if hasattr(self, '_current_items') and self._current_items:
            self._fixed_change_percent_cache.clear()
            for item in self._current_items:
                symbol = item.get("symbol", "")
                real_time_change = float(item.get("real_time_change_percent", 0.0))
                self._fixed_change_percent_cache[symbol] = real_time_change
                self.logger.debug(f"시간고정: {symbol} = {real_time_change:.3f}%")
        else:
            # 폴백: 직접 API 호출
            await self._cache_fixed_prices()
    
    async def _cache_fixed_prices(self) -> None:
        """시간고정 시 사용할 상승률 캐시 (폴백)"""
        ticker_data = self.binance_client.get_24hr_ticker()
        
        if isinstance(ticker_data, list):
            self._fixed_change_percent_cache.clear()
            for ticker in ticker_data:
                symbol = ticker.get("symbol", "")
                if symbol.endswith("USDT"):
                    try:
                        change_percent = float(ticker.get("priceChangePercent", 0.0))
                        self._fixed_change_percent_cache[symbol] = change_percent
                    except Exception:
                        self._fixed_change_percent_cache[symbol] = 0.0
    
    async def _load_symbol_onboard_dates(self):
        """바이낸스 exchangeInfo에서 심볼 상장일 정보를 로드합니다. (레거시 메서드 - 호환성 유지)"""
        try:
            # exchangeInfo API 호출
            response = self.binance_client._send_public_request(
                "GET", 
                "/fapi/v1/exchangeInfo",
                weight_category="general",
                weight=1
            )
            
            if isinstance(response, dict) and "error" in response:
                self.logger.warning(f"exchangeInfo 조회 실패: {response.get('error')}")
                return
            
            symbols_data = response.get("symbols", [])
            
            # 각 심볼의 onboardDate 저장
            count = 0
            for symbol_info in symbols_data:
                symbol = symbol_info.get("symbol", "")
                onboard_date = symbol_info.get("onboardDate", 0)
                
                # USDT 선물이고 onboardDate가 있는 경우만 저장
                if symbol.endswith("USDT") and onboard_date > 0:
                    self._symbol_onboard_dates[symbol] = onboard_date
                    count += 1
            
            self.logger.info(f"심볼 상장일 정보 로드 완료: {count}개 심볼")
            
        except Exception as e:
            self.logger.error(f"심볼 상장일 정보 로드 실패: {e}", exc_info=True)
    
    async def _ensure_trading_symbols(self) -> List[str]:
        """TRADING 또는 SETTLING 상태인 USDT 무기한 선물 심볼 목록 확보 (Binance Live vs1 방식)"""
        if hasattr(self, '_cached_symbols') and self._cached_symbols:
            return self._cached_symbols
        
        try:
            # exchangeInfo API 호출
            response = self.binance_client._send_public_request(
                "GET",
                "/fapi/v1/exchangeInfo",
                weight_category="general",
                weight=1
            )
            
            if isinstance(response, dict) and "error" in response:
                self.logger.warning(f"exchangeInfo 조회 실패: {response.get('error')}")
                return []
            
            symbols_data = response.get("symbols", [])
            symbols = []
            
            # onboardDate도 함께 저장
            self._symbol_onboard_dates = {}
            
            for symbol_info in symbols_data:
                quote_asset = symbol_info.get("quoteAsset", "")
                contract_type = symbol_info.get("contractType", "")
                status = symbol_info.get("status", "")
                symbol = symbol_info.get("symbol", "")
                
                # USDT 무기한 선물이면서 TRADING 또는 SETTLING 상태인 심볼만 포함
                if (
                    quote_asset == "USDT"
                    and contract_type == "PERPETUAL"
                    and status in ["TRADING", "SETTLING"]
                ):
                    symbols.append(symbol)
                    
                    # 상장일 정보 저장
                    onboard_date = symbol_info.get("onboardDate", 0)
                    if onboard_date > 0:
                        self._symbol_onboard_dates[symbol] = onboard_date
            
            # 심볼 목록 정렬 및 캐싱
            symbols.sort()
            self._cached_symbols = symbols
            
            self.logger.info(f"거래 가능 심볼 로드 완료: {len(symbols)}개 (TRADING/SETTLING)")
            
            return symbols
            
        except Exception as e:
            self.logger.error(f"거래 가능 심볼 로드 실패: {e}", exc_info=True)
            return []
    
    async def _calculate_days_since_listing(self, symbol: str) -> int:
        """상장 후 경과일 계산.

        Behavior:
        - If `exchangeInfo.onboardDate` is cached, use it.
        - Otherwise try local backtest DB (`backtesting_backend`) for earliest kline (1m) and use that timestamp.
        - If DB has no data, attempt to load recent klines into backtest DB (async) and retry.
        - On success, cache the resolved onboard timestamp in `_symbol_onboard_dates`.
        - If all fallbacks fail, return 999.
        """
        try:
            onboard_date = self._symbol_onboard_dates.get(symbol, 0)
            if onboard_date and onboard_date > 0:
                listing_time = dt.datetime.fromtimestamp(onboard_date / 1000)
                current_time = dt.datetime.utcnow()
                return (current_time - listing_time).days

            # Attempt local backtesting DB fallback
            try:
                # Import here to avoid hard dependency at module import time
                from backtesting_backend.database.db_manager import BacktestDB
                from backtesting_backend.database.repositories.kline_repository import KlineRepository
                from backtesting_backend.core.data_loader import DataLoader

                # ensure backtest DB initialized
                db = BacktestDB.get_instance()
                await db.init()

                repo = KlineRepository(session_factory=db.get_session)
                earliest = await repo.get_earliest_kline_time(symbol, '1m')
                if earliest:
                    # cache and compute
                    self._symbol_onboard_dates[symbol] = int(earliest)
                    listing_time = dt.datetime.fromtimestamp(int(earliest) / 1000)
                    return (dt.datetime.utcnow() - listing_time).days

                # If DB had no klines, attempt to fetch a recent window (non-blocking but awaited here)
                now_ms = int(dt.datetime.utcnow().timestamp() * 1000)
                # try to load up to the last 30 days as a reasonable fallback (reduced from 180)
                start_ms = int((dt.datetime.utcnow() - dt.timedelta(days=30)).timestamp() * 1000)
                loader = DataLoader()
                try:
                    await loader.load_historical_klines(symbol, '1m', start_ms, now_ms)
                except Exception as e:
                    self.logger.debug(f"Kline load fallback failed for {symbol}: {e}")

                # retry earliest kline lookup
                earliest = await repo.get_earliest_kline_time(symbol, '1m')
                if earliest:
                    self._symbol_onboard_dates[symbol] = int(earliest)
                    listing_time = dt.datetime.fromtimestamp(int(earliest) / 1000)
                    return (dt.datetime.utcnow() - listing_time).days

            except Exception as db_exc:
                # Non-fatal: log debug and continue to final fallback
                self.logger.debug(f"Local DB fallback for {symbol} failed: {db_exc}")

            # Final fallback: treat as old coin
            return 999

        except Exception as e:
            self.logger.debug(f"_calculate_days_since_listing unexpected error for {symbol}: {e}")
            return 999
    
    def _determine_listing_signal_status(self, change_percent: float, cumulative_percent: float) -> str:
        """신규 상장 코인의 신호 상태 판단"""
        # 강력한 매수 신호 (큰 상승)
        if change_percent > 15 or cumulative_percent > 20:
            return "STRONG_BUY"
        # 강력한 하락 신호 (큰 하락 후)
        elif change_percent < -10 or cumulative_percent < -15:
            return "STRONG_DECLINE"
        else:
            return "NORMAL"
    
    async def _broadcast_energy_analysis(self, symbol: str = "XRPUSDT", 
                                         volume_status: str = "분석 중",
                                         ema_status: str = "분석 중",
                                         macd_status: str = "분석 중",
                                         stoch_rsi_status: str = "분석 중",
                                         energy_level: str = "분석 중",
                                         energy_stars: str = ""):
        """상승 에너지 분석 결과를 WebSocket으로 전송"""
        await self._broadcast({
            "type": "ENERGY_ANALYSIS_UPDATE",
            "data": {
                "symbol": symbol,
                "volume_status": volume_status,
                "ema_status": ema_status,
                "macd_status": macd_status,
                "stoch_rsi_status": stoch_rsi_status,
                "energy_level": energy_level,
                "energy_stars": energy_stars
            }
        })
    
    async def _broadcast_trade_execution(self, message: str):
        """거래 실행 메시지를 WebSocket으로 전송"""
        await self._broadcast({
            "type": "TRADE_EXECUTION_UPDATE",
            "message": message
        })
    
    async def _broadcast_risk_management(self, message: str):
        """리스크 관리 메시지를 WebSocket으로 전송"""
        await self._broadcast({
            "type": "RISK_MANAGEMENT_UPDATE",
            "message": message
        })

    async def start_analysis(self):
        self._analysis_active = True
        self.logger.info("분석 및 자동매매 시작 (상태: Active)")
        await self._broadcast({"type": "APP_STATUS_UPDATE", "data": {"status": "connected_active"}})

    async def stop_analysis(self):
        self._analysis_active = False
        self.logger.info("분석 및 자동매매 중지 (상태: Inactive)")
        await self._broadcast({"type": "APP_STATUS_UPDATE", "data": {"status": "connected_inactive"}})

    # ============================================
    # 긴급 청산 (Forced Liquidation)
    # ============================================
    async def emergency_liquidate(self, scope: str = "all", engine: Optional[str] = None) -> Dict[str, Any]:
        """모든 또는 특정 엔진의 포지션을 즉시 시장가 청산 후 엔진을 정지.

        Args:
            scope: "all" | "single"
            engine: scope == "single" 일 때 엔진 이름 (Alpha/Beta/Gamma)

        Returns:
            결과 딕셔너리 (브로드캐스트와 동일 구조 일부)
        """
        try:
            if self._emergency_lock.locked():
                data = {
                    "status": "error",
                    "message": "Liquidation already in progress",
                    "closed_count": 0,
                    "closed_positions": [],
                    "errors": [{"symbol": "*", "error": "already_running"}]
                }
                await self._broadcast({"type": "EMERGENCY_LIQUIDATION", "data": data})
                return data

            async with self._emergency_lock:
                from backend.core.engine_manager import get_engine_manager
                engine_manager = get_engine_manager()
                targets: Dict[str, Any] = {}
                if scope == "single" and engine:
                    if engine in engine_manager.engines:
                        targets[engine] = engine_manager.engines[engine]
                    else:
                        data = {
                            "status": "error",
                            "message": f"Unknown engine: {engine}",
                            "closed_count": 0,
                            "closed_positions": [],
                            "errors": [{"symbol": "*", "error": "unknown_engine"}]
                        }
                        await self._broadcast({"type": "EMERGENCY_LIQUIDATION", "data": data})
                        return data
                else:
                    targets = dict(engine_manager.engines)

                closed_positions: List[Dict[str, Any]] = []
                errors: List[Dict[str, str]] = []

                # 포지션 청산 및 엔진 정지
                for name, eng in targets.items():
                    try:
                        # 진입 중단 (신규 시그널 억제)
                        eng.is_active = False
                        pos = eng.get_open_position()
                        if pos:
                            symbol = pos.get("symbol")
                            side = pos.get("side")
                            
                            # 1) 포지션 방향 검증 (LONG 전용 앱)
                            if side and side != "LONG":
                                self.logger.warning(
                                    f"⚠️ 비정상 포지션 방향 감지: {symbol} | "
                                    f"방향={side} (앱은 LONG만 지원)"
                                )
                                errors.append({
                                    "symbol": symbol,
                                    "error": f"UNEXPECTED_POSITION_SIDE: {side} (앱은 LONG만 지원)"
                                })
                            
                            # 2) 포지션 크기 검증 (내부 vs 실제)
                            internal_qty = pos.get("quantity", 0.0)
                            try:
                                positions = self.binance_client.get_all_positions()
                                if "error" not in positions:
                                    actual_qty = 0.0
                                    for p in positions:
                                        if p.get("symbol") == symbol and float(p.get("positionAmt", 0)) != 0:
                                            actual_qty = abs(float(p.get("positionAmt")))
                                            break
                                    
                                    if abs(actual_qty - internal_qty) > 0.001:
                                        self.logger.warning(
                                            f"⚠️ 포지션 크기 불일치: {symbol} | "
                                            f"내부={internal_qty:.4f}, 실제={actual_qty:.4f}"
                                        )
                            except Exception as verify_err:
                                self.logger.debug(f"포지션 크기 검증 실패: {verify_err}")
                            
                            # 3) 미체결 주문 취소 (재진입 방지)
                            try:
                                cancel_result = self.binance_client.cancel_all_open_orders(symbol)
                                if "error" in cancel_result:
                                    # -2011 (주문 없음) 등은 정상 상황
                                    self.logger.debug(
                                        f"미체결 주문 취소 응답: {symbol} - {cancel_result.get('error')}"
                                    )
                                else:
                                    self.logger.info(f"✅ 미체결 주문 취소 완료: {symbol}")
                            except Exception as cancel_err:
                                self.logger.warning(f"미체결 주문 취소 중 예외: {symbol} - {cancel_err}")
                            
                            # 4) 포지션 청산 (재시도 로직 포함)
                            max_retries = 2
                            binance_result = None
                            for attempt in range(max_retries):
                                binance_result = self.binance_client.close_position_market(symbol)
                                if "error" not in binance_result:
                                    break
                                if attempt < max_retries - 1:
                                    self.logger.warning(
                                        f"청산 재시도 {attempt+1}/{max_retries}: {symbol}"
                                    )
                                    await asyncio.sleep(0.3)
                            
                            if isinstance(binance_result, dict) and "error" in binance_result:
                                # 거래소 청산 실패 → 내부 상태 유지 시도하지 않고 오류 기록
                                errors.append({"symbol": symbol, "error": str(binance_result.get("error"))})
                            else:
                                # exit 가격 추출 (평균가 또는 mark price)
                                exit_price = 0.0
                                try:
                                    exit_price = float(binance_result.get("avgPrice") or 0) or 0.0
                                    if exit_price == 0:
                                        mp = self.binance_client.get_mark_price(symbol)
                                        exit_price = float(mp.get("markPrice", 0)) if isinstance(mp, dict) else 0.0
                                except Exception:
                                    pass
                                if exit_price <= 0:
                                    exit_price = pos.get("entry_price", 0.0)
                                realized_pnl = eng.close_position(exit_price)
                                closed_positions.append({
                                    "symbol": symbol,
                                    "side": side,
                                    "amount": pos.get("quantity", 0.0),
                                    "realized_pnl": realized_pnl
                                })
                        # 엔진 완전 정지
                        try:
                            eng.stop()
                            # GUI 상태 업데이트 브로드캐스트
                            await self._broadcast({
                                "type": "ENGINE_STATUS_UPDATE",
                                "data": {
                                    "engine": name,
                                    "status": "stopped",
                                    "reason": "emergency_liquidation"
                                }
                            })
                        except Exception:
                            pass
                    except Exception as e:
                        errors.append({"symbol": pos.get("symbol") if pos else name, "error": str(e)})

                status: str
                if errors and closed_positions:
                    status = "partial_failure"
                elif errors and not closed_positions:
                    status = "error"
                else:
                    status = "success"

                data = {
                    "status": status,
                    "message": "Forced liquidation completed" if status == "success" else "Forced liquidation completed with issues",
                    "closed_count": len(closed_positions),
                    "closed_positions": closed_positions,
                    "errors": errors
                }

                # 브로드캐스트 (GUI 팝업용)
                await self._broadcast({"type": "EMERGENCY_LIQUIDATION", "data": data})

                # 헤더 데이터 즉시 갱신 (실현 손익 반영 후)
                try:
                    await self._update_header_data()
                except Exception:
                    pass

                return data
        except Exception as e:
            self.logger.error(f"긴급 청산 처리 오류: {e}", exc_info=True)
            data = {
                "status": "error",
                "message": "Unexpected error during forced liquidation",
                "closed_count": 0,
                "closed_positions": [],
                "errors": [{"symbol": "*", "error": str(e)}]
            }
            try:
                await self._broadcast({"type": "EMERGENCY_LIQUIDATION", "data": data})
            except Exception:
                pass
            return data

    async def shutdown(self):
        self.logger.info("YonaService 종료 절차 시작...")
        self._running = False
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                self.logger.info("메인 루프가 성공적으로 취소되었습니다.")
        self.logger.info("YonaService 리소스 정리 완료.")
    
    # ============================================
    # 자금 배분 관리 (Funds Allocation)
    # ============================================

    def add_realized_pnl(self, engine_name: str, amount: float) -> None:
        """
        엔진 포지션 종료 시 전달되는 실현 손익을 반영합니다.

        - FundsAllocationManager에 실현 손익 누적
        - 엔진의 현재 배분 자금(designated_funds)을 DB에 비동기 저장
        - 헤더 업데이트는 호출측(app_main)에서 담당

        Args:
            engine_name: 엔진 이름 ("Alpha", "Beta", "Gamma")
            amount: 실현 손익 (USDT)
        """
        try:
            # 1) 실현 손익 누적 (헤더의 Account total balance/P&L%에 반영됨)
            self.account_manager.funds_allocation_manager.add_realized_pnl(engine_name, amount)

            # 2) 현재 엔진의 배분 자금과 레버리지 조회
            from backend.core.engine_manager import get_engine_manager
            engine_manager = get_engine_manager()
            engine = engine_manager.engines.get(engine_name)
            if not engine:
                return

            designated_funds = float(getattr(engine, "designated_funds", 0.0) or 0.0)
            applied_leverage = int(engine.config.get("leverage", 1))

            # 3) 현재 기준 투입 비중 계산 (헤더의 total_balance 기반)
            header_data = self.account_manager.get_header_data()
            total_balance = float(header_data.get("total_balance", 0.0) or 0.0)
            if total_balance > 0:
                funds_percent = (designated_funds / total_balance) * 100.0
            else:
                initial_capital = float(self.account_manager.initial_capital or 0.0)
                funds_percent = (designated_funds / initial_capital * 100.0) if initial_capital > 0 else 0.0

            # 4) 엔진 설정 DB 비동기 저장 스케줄링
            try:
                import asyncio as _asyncio
                if _asyncio.get_event_loop().is_running():
                    _asyncio.create_task(self._save_engine_settings(engine_name, designated_funds, applied_leverage, funds_percent))
                else:
                    _asyncio.run(self._save_engine_settings(engine_name, designated_funds, applied_leverage, funds_percent))
            except Exception:
                # 이벤트 루프 상태에 따라 생성 실패 시 무시 (다음 저장 시점에 반영)
                pass

        except Exception:
            # 안전상 상세 로그는 상위 로거에 위임 (핵심 루프 방해 방지)
            self.logger.warning("실현 손익 반영 중 경고 발생", exc_info=True)
    
    async def set_funds_allocation(self, engine_name: str, amount: float) -> None:
        """
        특정 엔진의 배분 자금 설정 및 DB 저장
        
        Args:
            engine_name: 엔진 이름 ("Alpha", "Beta", "Gamma")
            amount: 배분 금액 (USDT)
        """
        from backend.core.engine_manager import get_engine_manager
        from backend.core.account_manager import AccountManager
        
        self._ensure_cash_balance_initialized()
        previous_amount = self.account_manager.funds_allocation_manager.get_allocation(engine_name)
        delta = amount - previous_amount
        self._cash_balance -= delta
        
        # 엔진 매니저를 통해 엔진에 배분 자금 설정
        engine_manager = get_engine_manager()
        engine_manager.set_engine_designated_funds(engine_name, amount)
        
        # FundsAllocationManager에도 반영
        self.account_manager.funds_allocation_manager.set_allocation(engine_name, amount)
        
        # Account total balance를 기반으로 funds_percent 계산
        account_total_balance = await self.get_account_total_balance()
        # account_total_balance가 0이면 initial_capital 사용
        if account_total_balance <= 0:
            initial_capital = self.account_manager.initial_capital
            funds_percent = (amount / initial_capital * 100.0) if initial_capital > 0 else 0.0
        else:
            funds_percent = (amount / account_total_balance * 100.0) if account_total_balance > 0 else 0.0
        
        # 심볼 추출 (현재 엔진에 설정된 심볼)
        engine = engine_manager.engines.get(engine_name)
        symbol = "BTCUSDT"  # 기본값
        if engine and hasattr(engine, 'current_symbol'):
            symbol = engine.current_symbol or "BTCUSDT"
        
        # 엔진 설정 DB 저장
        await self._save_engine_settings(
            engine_name, 
            amount, 
            engine_manager.engines[engine_name].config.get("leverage", 1), 
            funds_percent,
            symbol  # 심볼 전달
        )
        await self._save_cash_balance()
        
        self.logger.info(f"{engine_name} 엔진 배분 자금 설정 완료: {amount:.2f} USDT ({funds_percent:.2f}%)")
    
    async def remove_funds_allocation(self, engine_name: str) -> None:
        """
        특정 엔진의 배분 자금 제거 및 DB 저장
        
        Args:
            engine_name: 엔진 이름 ("Alpha", "Beta", "Gamma")
        """
        from backend.core.engine_manager import get_engine_manager
        
        self._ensure_cash_balance_initialized()
        allocation_amount = self.account_manager.funds_allocation_manager.get_allocation(engine_name)
        self._cash_balance += allocation_amount
        
        # 엔진 매니저를 통해 엔진에서 배분 자금 제거
        engine_manager = get_engine_manager()
        engine_manager.set_engine_designated_funds(engine_name, 0.0)
        
        # FundsAllocationManager에서도 제거
        self.account_manager.funds_allocation_manager.remove_allocation(engine_name)
        
        # 엔진 설정 DB 저장 (자금 0으로)
        await self._save_engine_settings(engine_name, 0.0, 1, 0.0)
        await self._save_cash_balance()
        
        self.logger.info(f"{engine_name} 엔진 배분 자금 제거 완료")
    
    async def get_funds_allocations(self) -> Dict[str, float]:
        """
        모든 엔진의 배분 자금 조회
        
        Returns:
            엔진별 배분 자금 딕셔너리
        """
        return self.account_manager.funds_allocation_manager.allocations.copy()

    async def return_funds(self, engine_name: str) -> None:
        """
        특정 엔진의 운용 자금을 Available Funds로 반환
        """
        from backend.core.engine_manager import get_engine_manager
        
        engine_manager = get_engine_manager()
        engine = engine_manager.engines.get(engine_name)
        if engine is None:
            raise ValueError(f"알 수 없는 엔진: {engine_name}")
        
        if engine.is_running or getattr(engine, "in_position", False):
            raise ValueError("거래 중에는 자금을 반환할 수 없습니다.")
        
        returned_amount = float(getattr(engine, "designated_funds", 0.0) or 0.0)
        self._ensure_cash_balance_initialized()
        self._cash_balance += returned_amount
        engine_manager.set_engine_designated_funds(engine_name, 0.0)
        self.account_manager.funds_allocation_manager.set_allocation(engine_name, 0.0)
        engine.reset_realized_pnl()
        await self._save_cash_balance()
        
        await self._broadcast({
            "type": "ENGINE_FUNDS_RETURNED",
            "engine": engine_name,
            "data": {
                "returned_amount": returned_amount
            }
        })
        
        return returned_amount
    
    async def reset_initial_investment(self) -> float:
        """
        현재 선물 계정 잔고를 기준으로 Initial Investment를 재설정
        """
        from backend.core.engine_manager import get_engine_manager
        
        updated = self.account_manager.update_account_info()
        if not updated:
            raise ValueError("Binance 계좌 정보를 불러올 수 없습니다.")
        
        new_amount = max(float(self.account_manager.get_total_balance()), 0.0)
        self.account_manager.set_initial_capital(new_amount, save_to_db=True, db_path=self._db_path, force=True)
        
        # 현금 잔액 및 배분 정보 초기화
        self._cash_balance = new_amount
        self._cash_balance_initialized = True
        self.account_manager.funds_allocation_manager.reset()
        
        engine_manager = get_engine_manager()
        for engine_name, engine in engine_manager.engines.items():
            engine_manager.set_engine_designated_funds(engine_name, 0.0)
            if hasattr(engine, "reset_realized_pnl"):
                engine.reset_realized_pnl()
            # 엔진 설정 저장 (0으로)
            await self._save_engine_settings(engine_name, 0.0, engine.config.get("leverage", 1), 0.0)
        
        await self._save_app_setting("initial_capital", new_amount, "float")
        await self._save_cash_balance()
        
        # 헤더 업데이트 전송
        await self._update_header_data()
        
        return new_amount
    
    async def get_account_total_balance(self) -> float:
        """
        Account total balance 조회 (배분 차감 후 잔액)
        
        Returns:
            Account total balance (USDT)
        """
        metrics = self._compute_portfolio_metrics()
        return metrics.get("available_funds", 0.0)

    async def update_engine_leverage(self, engine_name: str, leverage: int) -> None:
        """
        특정 엔진의 런타임 레버리지를 업데이트하고 DB에 저장합니다.

        Args:
            engine_name: "Alpha"|"Beta"|"Gamma"
            leverage: 1~125
        """
        if leverage < 1 or leverage > 125:
            raise ValueError("레버리지는 1~125 사이여야 합니다.")

        from backend.core.engine_manager import get_engine_manager
        engine_manager = get_engine_manager()
        engine = engine_manager.engines.get(engine_name)
        if engine is None:
            raise ValueError(f"알 수 없는 엔진: {engine_name}")

        # 런타임 설정 반영
        engine.update_config({"leverage": leverage})

        # 현재 배분 자금 및 퍼센트 산출
        designated_funds = float(getattr(engine, "designated_funds", 0.0) or 0.0)

        account_total_balance = await self.get_account_total_balance()
        if account_total_balance > 0:
            funds_percent = (designated_funds / account_total_balance) * 100.0
        else:
            initial_capital = float(self.account_manager.initial_capital or 0.0)
            funds_percent = (designated_funds / initial_capital * 100.0) if initial_capital > 0 else 0.0

        # 심볼 추출
        symbol = "BTCUSDT"  # 기본값
        if hasattr(engine, 'current_symbol'):
            symbol = engine.current_symbol or "BTCUSDT"

        # 엔진 설정 저장
        await self._save_engine_settings(engine_name, designated_funds, leverage, funds_percent, symbol)

    async def update_engine_symbol(self, engine_name: str, symbol: str) -> None:
        """
        특정 엔진의 거래 심볼을 업데이트합니다.

        Args:
            engine_name: "Alpha"|"Beta"|"Gamma"
            symbol: 예) "BTCUSDT"
        """
        from backend.core.engine_manager import get_engine_manager
        engine_manager = get_engine_manager()
        engine = engine_manager.engines.get(engine_name)
        if engine is None:
            raise ValueError(f"알 수 없는 엔진: {engine_name}")
        engine.current_symbol = symbol
        # 상태 메시지 브로드캐스트 (선택): 심볼 설정 알림
        try:
            await self._broadcast({
                "type": "ENGINE_STATUS_MESSAGE",
                "engine": engine_name,
                "category": "trade",
                "message": f"심볼 설정: {symbol}"
            })
        except Exception:
            pass
    
    # ============================================
    # 엔진 설정 저장/로드
    # ============================================
    
    async def _save_engine_settings(
        self, engine_name: str, designated_funds: float, 
        applied_leverage: int, funds_percent: float,
        symbol: str = "BTCUSDT"
    ) -> None:
        """
        엔진 설정을 DB에 저장
        
        Args:
            engine_name: 엔진 이름
            designated_funds: 배분 자금
            applied_leverage: 적용 레버리지
            funds_percent: 투입 자금 퍼센트
            symbol: 거래 심볼
        """
        try:
            now_utc = dt.datetime.utcnow().isoformat()
            
            async with aiosqlite.connect(self._db_path) as db:
                # 기존 설정 확인
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT engine_name FROM engine_settings WHERE engine_name = ?",
                    (engine_name,)
                )
                existing = await cur.fetchone()
                
                if existing:
                    # 업데이트
                    await db.execute("""
                        UPDATE engine_settings 
                        SET designated_funds = ?, applied_leverage = ?, 
                            funds_percent = ?, symbol = ?, updated_at_utc = ?
                        WHERE engine_name = ?
                    """, (designated_funds, applied_leverage, funds_percent, symbol, now_utc, engine_name))
                else:
                    # 삽입
                    await db.execute("""
                        INSERT INTO engine_settings 
                        (engine_name, designated_funds, applied_leverage, funds_percent, symbol, updated_at_utc, created_at_utc)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (engine_name, designated_funds, applied_leverage, funds_percent, symbol, now_utc, now_utc))
                
                await db.commit()
                self.logger.debug(f"엔진 설정 저장 완료: {engine_name}, 심볼: {symbol}")
        except Exception as e:
            self.logger.warning(f"엔진 설정 저장 실패: {e}")
    
    async def _load_engine_settings(self) -> None:
        """DB에서 엔진 설정을 로드하여 각 엔진에 적용"""
        try:
            from backend.core.engine_manager import get_engine_manager
            
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT engine_name, designated_funds, applied_leverage, symbol FROM engine_settings"
                )
                rows = await cur.fetchall()
                
                engine_manager = get_engine_manager()
                
                for row in rows:
                    engine_name = row["engine_name"]
                    designated_funds = row["designated_funds"]
                    applied_leverage = row["applied_leverage"]
                    symbol = row["symbol"]  # 심볼 로드
                    
                    if engine_name in engine_manager.engines:
                        engine = engine_manager.engines[engine_name]
                        
                        # 1. 배분 자금 설정
                        engine_manager.set_engine_designated_funds(engine_name, designated_funds)
                        self.account_manager.funds_allocation_manager.set_allocation(engine_name, designated_funds)
                        
                        # 2. 레버리지 설정
                        engine.config["leverage"] = applied_leverage
                        
                        # 3. 심볼 설정 및 prepare_symbol 실행
                        if hasattr(engine, 'orchestrator') and hasattr(engine.orchestrator, 'cfg'):
                            engine.orchestrator.cfg.symbol = symbol
                            engine.orchestrator.cfg.leverage = applied_leverage
                            engine.current_symbol = symbol
                            
                            # Binance에 마진/레버리지 준비 (앱 재시작 시 자동 준비)
                            if hasattr(engine.orchestrator, 'exec'):
                                ok = engine.orchestrator.exec.prepare_symbol(
                                    symbol, 
                                    applied_leverage, 
                                    engine.orchestrator.cfg.isolated_margin
                                )
                                if ok:
                                    self.logger.info(f"{engine_name} 심볼 준비 완료: {symbol} @ {applied_leverage}x")
                                else:
                                    self.logger.warning(f"{engine_name} 심볼 준비 실패: {symbol}")
                        
                        self.logger.info(
                            f"엔진 설정 로드 완료: {engine_name} - "
                            f"심볼: {symbol}, 배분: {designated_funds:.2f} USDT, 레버리지: {applied_leverage}x"
                        )
        except Exception as e:
            self.logger.warning(f"엔진 설정 로드 실패: {e}")
    
    # ============================================
    # 전역 설정 저장/로드
    # ============================================
    
    async def _save_app_setting(self, key: str, value: Any, value_type: str = "string") -> None:
        """
        전역 앱 설정을 DB에 저장
        
        Args:
            key: 설정 키
            value: 설정 값
            value_type: 값 타입 ("string", "float", "int", "datetime", "json")
        """
        try:
            now_utc = dt.datetime.utcnow().isoformat()
            
            # 값 타입에 따라 문자열 변환
            if value_type == "json":
                import json
                value_str = json.dumps(value)
            elif value_type == "datetime":
                value_str = value.isoformat() if hasattr(value, 'isoformat') else str(value)
            else:
                value_str = str(value)
            
            async with aiosqlite.connect(self._db_path) as db:
                # 기존 설정 확인
                db.row_factory = aiosqlite.Row
                cur = await db.execute("SELECT key FROM app_settings WHERE key = ?", (key,))
                existing = await cur.fetchone()
                
                if existing:
                    # 업데이트
                    await db.execute("""
                        UPDATE app_settings 
                        SET value = ?, value_type = ?, updated_at_utc = ?
                        WHERE key = ?
                    """, (value_str, value_type, now_utc, key))
                else:
                    # 삽입
                    await db.execute("""
                        INSERT INTO app_settings (key, value, value_type, updated_at_utc, created_at_utc)
                        VALUES (?, ?, ?, ?, ?)
                    """, (key, value_str, value_type, now_utc, now_utc))
                
                await db.commit()
                self.logger.debug(f"앱 설정 저장 완료: {key} = {value_str}")
        except Exception as e:
            self.logger.warning(f"앱 설정 저장 실패: {e}")
    
    async def _load_app_settings(self) -> None:
        """DB에서 전역 앱 설정을 로드"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute("SELECT key, value, value_type FROM app_settings")
                rows = await cur.fetchall()
                
                for row in rows:
                    key = row["key"]
                    value_str = row["value"]
                    value_type = row["value_type"]
                    
                    # 값 타입에 따라 변환
                    if value_type == "float":
                        value = float(value_str)
                    elif value_type == "int":
                        value = int(value_str)
                    elif value_type == "datetime":
                        value = dt.datetime.fromisoformat(value_str)
                    elif value_type == "json":
                        import json
                        value = json.loads(value_str)
                    else:
                        value = value_str
                    
                    # initial_capital 설정
                    if key == "initial_capital" and isinstance(value, (int, float)):
                        self.account_manager.set_initial_capital(float(value))
                        self.logger.info(f"초기 자본 로드 완료: {value:.2f} USDT")
                    elif key == "cash_balance" and isinstance(value, (int, float)):
                        self._cash_balance = float(value)
                        self._cash_balance_initialized = True
                        self.logger.info(f"가용 자금 로드 완료: {value:.2f} USDT")
        except Exception as e:
            self.logger.warning(f"앱 설정 로드 실패: {e}")
    
    # ============================================
    # 블랙리스트 관리
    # ============================================
    
    async def _init_database(self) -> None:
        """데이터베이스 및 블랙리스트 테이블 초기화 (기존 테이블 유지)"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                # 기존 블랙리스트 테이블 유지 (마이그레이션으로 관리되지 않음)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS yona_blacklist (
                        symbol TEXT PRIMARY KEY,
                        added_at_utc TEXT NOT NULL,
                        status TEXT DEFAULT 'MANUAL'
                    )
                """)
                await db.commit()
                self.logger.info(f"블랙리스트 테이블 확인 완료: {self._db_path}")
        except Exception as e:
            self.logger.warning(f"블랙리스트 테이블 초기화 실패: {e}")
    
    async def _load_blacklist_cache(self) -> None:
        """DB에서 블랙리스트를 메모리 캐시로 로드"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute("SELECT symbol, added_at_utc FROM yona_blacklist")
                rows = await cur.fetchall()
                self._blacklist = {r["symbol"]: r["added_at_utc"] for r in rows}
                self.logger.info(f"블랙리스트 캐시 로드 완료: {len(self._blacklist)}개 심볼")
        except Exception as e:
            self.logger.warning(f"블랙리스트 캐시 로드 실패: {e}")
    
    async def list_blacklist(self) -> List[Dict[str, Any]]:
        """블랙리스트 목록 조회"""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT symbol, added_at_utc, COALESCE(status, 'MANUAL') as status FROM yona_blacklist ORDER BY added_at_utc DESC"
                )
                rows = await cur.fetchall()
                return [{"symbol": r["symbol"], "added_at_utc": r["added_at_utc"], "status": r["status"]} for r in rows]
        except Exception as e:
            self.logger.warning(f"블랙리스트 조회 실패: {e}")
            return [{"symbol": s, "added_at_utc": t, "status": "MANUAL"} for s, t in self._blacklist.items()]
    
    async def add_blacklist(self, symbols: List[str], status: str = "MANUAL") -> None:
        """블랙리스트에 심볼 추가 후 즉시 랭킹 및 SETTLING 업데이트"""
        if not symbols:
            return
        now_utc = dt.datetime.utcnow().replace(microsecond=0).isoformat(sep=' ')
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.executemany(
                    "INSERT OR REPLACE INTO yona_blacklist(symbol, added_at_utc, status) VALUES(?, ?, ?)",
                    [(s, now_utc, status) for s in symbols]
                )
                await db.commit()
                self.logger.info(f"블랙리스트 추가 완료: {symbols} (status: {status})")
        except Exception as e:
            self.logger.warning(f"블랙리스트 추가 실패(디스크): {e}")
        
        for s in symbols:
            self._blacklist[s] = now_utc
        
        # 블랙리스트 추가 후 즉시 랭킹 업데이트 재전송 (Binance Live vs1 방식)
        try:
            await self._update_ranking_data()
            self.logger.info(f"블랙리스트 추가 후 랭킹 즉시 업데이트 완료")
        except Exception as e:
            self.logger.warning(f"블랙리스트 추가 후 랭킹 업데이트 실패: {e}")
        
        # SETTLING 코인을 블랙리스트에 추가했을 경우 즉시 SETTLING_UPDATE 재전송
        try:
            settling_data = await self._compute_settling_update()
            # 빈 배열이어도 전송해야 GUI가 테이블을 비울 수 있음!
            if self._broadcaster:
                await self._broadcast({
                    "type": "SETTLING_UPDATE",
                    "data": settling_data
                })
                self.logger.info(f"블랙리스트 추가 후 SETTLING_UPDATE 재전송 완료: {len(settling_data)}개")
        except Exception as e:
            self.logger.warning(f"블랙리스트 추가 후 SETTLING_UPDATE 재전송 실패: {e}")
    
    async def remove_blacklist(self, symbols: List[str]) -> None:
        """블랙리스트에서 심볼 제거 후 즉시 랭킹 및 SETTLING 업데이트"""
        if not symbols:
            return
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.executemany(
                    "DELETE FROM yona_blacklist WHERE symbol = ?",
                    [(s,) for s in symbols]
                )
                await db.commit()
                self.logger.info(f"블랙리스트 제거 완료: {symbols}")
        except Exception as e:
            self.logger.warning(f"블랙리스트 제거 실패(디스크): {e}")
        
        for s in symbols:
            self._blacklist.pop(s, None)
        
        # 블랙리스트 제거 후 즉시 랭킹 업데이트 재전송 (해당 심볼이 랭킹에 복귀)
        try:
            await self._update_ranking_data()
            self.logger.info(f"블랙리스트 제거 후 랭킹 즉시 업데이트 완료 (심볼 복귀)")
        except Exception as e:
            self.logger.warning(f"블랙리스트 제거 후 랭킹 업데이트 실패: {e}")
        
        # SETTLING 코인을 블랙리스트에서 제거했을 경우 즉시 SETTLING_UPDATE 재전송
        try:
            settling_data = await self._compute_settling_update()
            if self._broadcaster:
                await self._broadcast({
                    "type": "SETTLING_UPDATE",
                    "data": settling_data
                })
                self.logger.info(f"블랙리스트 제거 후 SETTLING_UPDATE 재전송 완료: {len(settling_data)}개")
        except Exception as e:
            self.logger.warning(f"블랙리스트 제거 후 SETTLING_UPDATE 재전송 실패: {e}")
    
    # ============================================
    # SETTLING 코인 자동 검색
    # ============================================
    
    async def _compute_settling_update(self) -> List[Dict[str, Any]]:
        """SETTLING 상태 코인 목록 자동 검색 및 생성"""
        try:
            # exchangeInfo에서 SETTLING 상태 코인 목록 가져오기
            self.logger.info("SETTLING 코인 검색 시작: exchangeInfo 조회 중...")
            exchange_info = self.binance_client.get_exchange_info()
            
            if isinstance(exchange_info, dict) and "error" in exchange_info:
                self.logger.warning(f"exchangeInfo 조회 실패: {exchange_info.get('error')}")
                return []
            
            total_symbols = len(exchange_info.get("symbols", []))
            self.logger.info(f"총 {total_symbols}개 심볼 조회 완료, SETTLING 상태 필터링 중...")
            
            settling_symbols = []
            for s in exchange_info.get("symbols", []):
                if (
                    s.get("quoteAsset") == "USDT"
                    and s.get("contractType") == "PERPETUAL"
                    and s.get("status") == "SETTLING"
                ):
                    settling_symbols.append(s["symbol"])
            
            self.logger.info(f"SETTLING 상태 코인 {len(settling_symbols)}개 발견: {settling_symbols}")
            
            if not settling_symbols:
                self.logger.info("SETTLING 상태 코인이 없습니다.")
                return []
            
            # 이미 수집된 24hr ticker 데이터 재활용
            ticker_data = self.binance_client.get_24hr_ticker()
            
            if not isinstance(ticker_data, list):
                self.logger.warning("24hr ticker 데이터 조회 실패")
                return []
            
            # 티커 데이터를 딕셔너리로 변환 (빠른 조회)
            ticker_dict = {t.get("symbol"): t for t in ticker_data}
            
            # SETTLING 코인들의 데이터 구성
            settling_data = []
            for symbol in settling_symbols:
                ticker = ticker_dict.get(symbol)
                if ticker:
                    if symbol not in self._blacklist:
                        settling_data.append({
                            "symbol": symbol,
                            "change_percent": round(float(ticker.get("priceChangePercent", 0)), 2),
                            "status": "SETTLING",
                            "volume": round(float(ticker.get("quoteVolume", 0)), 0)
                        })
                    else:
                        self.logger.info(f"블랙리스트 제외: {symbol}")
            
            # 변화율 절대값 순으로 정렬하여 상위 20개만 반환
            settling_data.sort(key=lambda x: abs(x["change_percent"]), reverse=True)
            
            self.logger.info(f"SETTLING 코인 검색 완료: {len(settling_data)}개 반환 (상위 20개)")
            return settling_data[:20]
            
        except Exception as e:
            self.logger.error(f"SETTLING 업데이트 생성 실패: {e}", exc_info=True)
            return []

    async def analyze_entry_timing(self, symbol: str) -> Dict[str, Any]:
        """
        포지션 진입 타이밍 분석 (Binance Live vs1 정밀 분석 이식)
        - 다중 시간대 분석 (1분/5분/15분)
        - 6개 기술지표 (EMA, RSI, MACD, VWAP, BPR, VSS)
        - 5개 독립 신호 검증 시스템
        - 4단계 진입 등급 체계
        """
        import math
        try:
            # === STEP 1: 다중 시간대 데이터 수집 ===
            kl_1m = self.binance_client.get_klines(symbol=symbol, interval='1m', limit=120)
            kl_5m = self.binance_client.get_klines(symbol=symbol, interval='5m', limit=50)
            kl_15m = self.binance_client.get_klines(symbol=symbol, interval='15m', limit=30)
            
            if not kl_1m or len(kl_1m) < 50:
                return self._get_fallback_analysis(symbol)
            
            # === STEP 2: 1분 데이터 파싱 ===
            close_1m: List[float] = []
            high_1m: List[float] = []
            low_1m: List[float] = []
            vol_1m: List[float] = []
            typical_1m: List[float] = []
            
            for r in kl_1m:
                try:
                    c = float(r[4]); h = float(r[2]); l = float(r[3]); v = float(r[5])
                    tp = (h + l + c) / 3.0
                    close_1m.append(c); high_1m.append(h); low_1m.append(l)
                    vol_1m.append(v); typical_1m.append(tp)
                except Exception:
                    continue
            
            # 5분 데이터 파싱
            close_5m: List[float] = []
            if kl_5m and len(kl_5m) >= 20:
                for r in kl_5m:
                    try:
                        close_5m.append(float(r[4]))
                    except Exception:
                        continue
            
            # 15분 데이터 파싱
            close_15m: List[float] = []
            if kl_15m and len(kl_15m) >= 15:
                for r in kl_15m:
                    try:
                        close_15m.append(float(r[4]))
                    except Exception:
                        continue
            
            n = len(close_1m)
            if n < 50:
                return self._get_fallback_analysis(symbol)
            
            # === STEP 3: 기술지표 계산 함수 정의 ===
            def ema(arr: List[float], period: int) -> List[float]:
                """지수이동평균"""
                if not arr or period <= 1:
                    return arr[:]
                k = 2 / (period + 1)
                out: List[float] = []
                s = arr[0]
                out.append(s)
                for v in arr[1:]:
                    s = v * k + s * (1 - k)
                    out.append(s)
                return out
            
            def rsi(prices: List[float], period: int = 14) -> List[float]:
                """RSI 계산 (Wilder's Smoothing)"""
                if len(prices) < period + 1:
                    return [50.0] * len(prices)
                
                deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
                gains = [max(0, d) for d in deltas]
                losses = [max(0, -d) for d in deltas]
                
                avg_gain = sum(gains[:period]) / period
                avg_loss = sum(losses[:period]) / period
                
                rsi_values = [50.0] * period
                
                for i in range(period, len(deltas)):
                    avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                    avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                    
                    if avg_loss == 0:
                        rsi_val = 100
                    else:
                        rs = avg_gain / avg_loss
                        rsi_val = 100 - (100 / (1 + rs))
                    
                    rsi_values.append(rsi_val)
                
                return rsi_values
            
            def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, List[float]]:
                """MACD 계산"""
                if len(prices) < slow + signal:
                    return {"macd": [0.0] * len(prices), "signal": [0.0] * len(prices), "histogram": [0.0] * len(prices)}
                
                ema_fast = ema(prices, fast)
                ema_slow = ema(prices, slow)
                
                macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(prices))]
                signal_line = ema(macd_line, signal)
                histogram = [macd_line[i] - signal_line[i] for i in range(len(macd_line))]
                
                return {"macd": macd_line, "signal": signal_line, "histogram": histogram}
            
            # === STEP 4: 기술지표 계산 ===
            ema20_1m = ema(close_1m, 20)
            ema50_1m = ema(close_1m, 50)
            rsi_1m = rsi(close_1m, 14)
            macd_1m = macd(close_1m, 12, 26, 9)
            
            current_price = close_1m[-1]
            ema20_val = ema20_1m[-1]
            ema50_val = ema50_1m[-1]
            rsi_current = rsi_1m[-1]
            
            # VWAP 계산
            vwap: List[float] = []
            cum_pv = 0.0; cum_v = 0.0
            for i in range(n):
                v_i = max(0.0, vol_1m[i])
                cum_pv += typical_1m[i] * v_i
                cum_v += v_i
                vwap.append((cum_pv / cum_v) if cum_v > 0 else typical_1m[i])
            
            vwap_val = vwap[-1]
            
            # BPR (Bull Power Ratio) 계산
            lookback = min(20, n)
            bull = sum(1 for i in range(n - lookback, n) if i > 0 and close_1m[i] >= close_1m[i - 1])
            bpr_val = bull / float(lookback) if lookback > 0 else 0.5
            bpr_series = [0.5] * (n - 1) + [bpr_val]
            
            # VSS (Volume Surge Score) 계산
            vss_val = 1.0
            if n >= 21:
                recent_v = vol_1m[-1]
                avg20 = sum(vol_1m[-21:-1]) / 20.0 if sum(vol_1m[-21:-1]) > 0 else 0.0
                if avg20 > 0:
                    vss_val = min(2.5, max(0.0, recent_v / avg20))
            vss_series = [1.0] * (n - 1) + [vss_val]
            
            # === STEP 5: 5분/15분 추세 분석 ===
            trend_5m = "중립"
            strength_5m = 0
            predicted_upside_5m = 0.0
            
            if len(close_5m) >= 20:
                ema20_5m = ema(close_5m, 20)
                current_5m = close_5m[-1]
                ema20_5m_val = ema20_5m[-1]
                
                price_vs_ema = (current_5m - ema20_5m_val) / ema20_5m_val * 100
                
                if current_5m > ema20_5m_val * 1.005:
                    trend_5m = "강상승"
                    strength_5m = min(100, int(abs(price_vs_ema) * 10))
                    predicted_upside_5m = min(8.0, abs(price_vs_ema) * 2)
                elif current_5m > ema20_5m_val * 1.002:
                    trend_5m = "상승"
                    strength_5m = min(80, int(abs(price_vs_ema) * 15))
                    predicted_upside_5m = min(5.0, abs(price_vs_ema) * 1.5)
                elif current_5m < ema20_5m_val * 0.995:
                    trend_5m = "강하락"
                    strength_5m = min(100, int(abs(price_vs_ema) * 10))
                    predicted_upside_5m = max(-8.0, -abs(price_vs_ema) * 2)
                elif current_5m < ema20_5m_val * 0.998:
                    trend_5m = "하락"
                    strength_5m = min(80, int(abs(price_vs_ema) * 15))
                    predicted_upside_5m = max(-5.0, -abs(price_vs_ema) * 1.5)
            
            trend_15m = "중립"
            strength_15m = 0
            predicted_upside_15m = 0.0
            
            if len(close_15m) >= 15:
                ema20_15m = ema(close_15m, 20)
                current_15m = close_15m[-1]
                ema20_15m_val = ema20_15m[-1]
                
                price_vs_ema_15m = (current_15m - ema20_15m_val) / ema20_15m_val * 100
                
                if current_15m > ema20_15m_val * 1.008:
                    trend_15m = "강상승"
                    strength_15m = min(100, int(abs(price_vs_ema_15m) * 8))
                    predicted_upside_15m = min(15.0, abs(price_vs_ema_15m) * 3)
                elif current_15m > ema20_15m_val * 1.003:
                    trend_15m = "상승"
                    strength_15m = min(80, int(abs(price_vs_ema_15m) * 12))
                    predicted_upside_15m = min(10.0, abs(price_vs_ema_15m) * 2)
                elif current_15m < ema20_15m_val * 0.992:
                    trend_15m = "강하락"
                    strength_15m = min(100, int(abs(price_vs_ema_15m) * 8))
                    predicted_upside_15m = max(-15.0, -abs(price_vs_ema_15m) * 3)
                elif current_15m < ema20_15m_val * 0.997:
                    trend_15m = "하락"
                    strength_15m = min(80, int(abs(price_vs_ema_15m) * 12))
                    predicted_upside_15m = max(-10.0, -abs(price_vs_ema_15m) * 2)
            
            # === STEP 6: 다중 신호 검증 시스템 ===
            entry_signals = 0
            signal_messages = []
            
            # 1. 거래량 급증 감지
            recent_volume = vol_1m[-1]
            avg_volume_20 = sum(vol_1m[-20:]) / 20.0 if len(vol_1m) >= 20 else recent_volume
            volume_spike = recent_volume > (avg_volume_20 * 3.0)
            
            if volume_spike:
                entry_signals += 30
                signal_messages.append("거래량 급증")
            
            # 2. VWAP 돌파 확인
            vwap_break = current_price > vwap_val
            
            if vwap_break:
                entry_signals += 25
                signal_messages.append("VWAP 돌파")
            
            # 3. 5분 상승 추세 확인
            trend_5m_bullish = trend_5m in ["상승", "강상승"]
            
            if trend_5m_bullish:
                entry_signals += 20
                signal_messages.append("5분 상승")
            
            # 4. 24시간 최고가 돌파
            high_24h = max(high_1m[-min(1440, len(high_1m)):]) if len(high_1m) > 0 else current_price
            high_break = current_price > (high_24h * 1.002)
            
            if high_break:
                entry_signals += 20
                signal_messages.append("24시간 고점 돌파")
            
            # 5. 연속 상승 확인
            consecutive_green = False
            if len(close_1m) >= 3:
                consecutive_green = all(close_1m[i] > close_1m[i-1] for i in range(-3, 0))
            
            if consecutive_green:
                entry_signals += 15
                signal_messages.append("연속 상승")
            
            # === STEP 7: 진입 신호 등급 판정 ===
            if entry_signals >= 90:
                final_score = 95
                signal_status = "🚀 즉시 진입"
            elif entry_signals >= 70:
                final_score = 85
                signal_status = "✅ 진입 권장"
            elif entry_signals >= 50:
                final_score = 70
                signal_status = "⏰ 진입 대기"
            else:
                final_score = entry_signals
                signal_status = "❌ 진입 금지"
            
            # === STEP 8: 진입/손절/목표가 계산 ===
            entry_zone_min = max(ema20_val, vwap_val) * 0.999
            entry_zone_max = max(ema20_val, vwap_val) * 1.001
            
            swing_low = min(low_1m[-20:]) if len(low_1m) >= 20 else current_price * 0.98
            stop_loss = swing_low * 0.998
            
            risk_ratio = (current_price - stop_loss) / current_price if current_price > 0 else 0.02
            tp1 = current_price * (1 + risk_ratio * 1.5)
            tp2 = current_price * (1 + risk_ratio * 3.0)
            
            # === STEP 9: 종합 추세 판단 ===
            overall_trend = "횡보"
            
            if trend_15m in ["강상승", "상승"] and trend_5m_bullish and current_price > ema20_val:
                overall_trend = "강상승"
            elif trend_15m in ["강상승", "상승"] and current_price > ema20_val:
                overall_trend = "상승"
            elif trend_5m_bullish and current_price > ema20_val > ema50_val:
                overall_trend = "상승"
            elif trend_15m in ["강하락", "하락"] and trend_5m in ["하락", "강하락"]:
                overall_trend = "강하락"
            elif trend_15m in ["강하락", "하락"] or (trend_5m in ["하락", "강하락"] and current_price < ema20_val):
                overall_trend = "하락"
            
            return {
                "symbol": symbol,
                "score": int(final_score),
                "series": {
                    "close": close_1m,
                    "ema20": ema20_1m,
                    "ema50": ema50_1m,
                    "vwap": vwap,
                    "bpr": bpr_series,
                    "vss": vss_series
                },
                "trend_analysis": {
                    "5m": {
                        "direction": trend_5m,
                        "strength": strength_5m,
                        "predicted_upside": predicted_upside_5m,
                        "price_status": {"status": "분석완료"}
                    },
                    "15m": {
                        "direction": trend_15m,
                        "strength": strength_15m,
                        "predicted_upside": predicted_upside_15m,
                        "price_status": {"status": "분석완료"}
                    },
                    "overall": overall_trend,
                    "signal_status": signal_status,
                    "active_signals": signal_messages,
                    "rsi": round(rsi_current, 1),
                    "volume_spike": volume_spike,
                    "vwap_break": vwap_break,
                    "high_break": high_break,
                    "consecutive_green": consecutive_green,
                    "entry_signals_score": entry_signals
                },
                "levels": {
                    "entry_zone": {"min": float(entry_zone_min), "max": float(entry_zone_max)},
                    "stop": float(stop_loss),
                    "tp1": float(tp1),
                    "tp2": float(tp2)
                }
            }
            
        except Exception as e:
            self.logger.error(f"진입 타이밍 분석 실패 ({symbol}): {e}", exc_info=True)
            return self._get_fallback_analysis(symbol)
    
    def _get_fallback_analysis(self, symbol: str) -> Dict[str, Any]:
        """API 실패 시 기본 분석 데이터"""
        return {
            "symbol": symbol,
            "score": 0,
            "series": {
                "close": [],
                "ema20": [],
                "ema50": [],
                "vwap": [],
                "bpr": [],
                "vss": []
            },
            "trend_analysis": {
                "5m": {
                    "direction": "연결중",
                    "strength": 0,
                    "predicted_upside": 0.0,
                    "price_status": {"status": "대기"}
                },
                "15m": {
                    "direction": "연결중",
                    "strength": 0,
                    "predicted_upside": 0.0,
                    "price_status": {"status": "대기"}
                },
                "overall": "바이낸스 API 연결 중",
                "signal_status": "❌ 연결 필요",
                "active_signals": [],
                "rsi": 50.0,
                "volume_spike": False,
                "vwap_break": False,
                "high_break": False,
                "consecutive_green": False,
                "entry_signals_score": 0
            },
            "levels": {
                "entry_zone": {},
                "stop": None,
                "tp1": None,
                "tp2": None
            }
        }
