"""데이터 수집 모듈 - Binance 실시간/과거 캔들 데이터 조회"""
import asyncio
from typing import List, Dict, Optional, Callable
from collections import defaultdict, deque
import logging

from .data_structures import Candle, APIError, InsufficientDataError

logger = logging.getLogger(__name__)


class MarketDataCache:
    """멀티 심볼/타임프레임 시계열 데이터 캐시"""
    
    def __init__(self, max_candles: int = 2000):
        self.max_candles = max_candles
        # {symbol: {interval: deque[Candle]}}
        self._cache: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=max_candles)))
    
    def add_candle(self, candle: Candle) -> None:
        """새 캔들 추가 (최신 데이터는 뒤에 추가)"""
        cache = self._cache[candle.symbol][candle.interval]
        
        # 중복 체크 (같은 open_time)
        if cache and cache[-1].open_time == candle.open_time:
            # 기존 캔들 업데이트 (실시간 갱신)
            cache[-1] = candle
        else:
            cache.append(candle)
    
    def add_candles_bulk(self, candles: List[Candle]) -> None:
        """과거 데이터 벌크 추가 (오름차순 정렬 가정)"""
        for candle in candles:
            self.add_candle(candle)
    
    def get_latest_candles(self, symbol: str, interval: str, count: int) -> List[Candle]:
        """최신 N개 캔들 조회 (시간 순서 오름차순)"""
        cache = self._cache[symbol][interval]
        if len(cache) < count:
            raise InsufficientDataError(
                f"요청 캔들 수({count}) > 캐시 크기({len(cache)}) for {symbol}/{interval}"
            )
        return list(cache)[-count:]
    
    def get_latest_candle(self, symbol: str, interval: str) -> Optional[Candle]:
        """최신 캔들 1개 조회"""
        cache = self._cache[symbol][interval]
        return cache[-1] if cache else None
    
    def has_sufficient_data(self, symbol: str, interval: str, required_count: int) -> bool:
        """충분한 데이터 존재 여부"""
        cache = self._cache[symbol][interval]
        return len(cache) >= required_count
    
    def clear(self, symbol: Optional[str] = None) -> None:
        """캐시 초기화 (symbol 미지정 시 전체)"""
        if symbol:
            self._cache.pop(symbol, None)
        else:
            self._cache.clear()


class BinanceDataFetcher:
    """Binance API를 통한 캔들 데이터 수집"""
    
    KLINE_INTERVALS = {
        "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m",
        "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1d"
    }
    
    def __init__(self, binance_client):
        """
        Args:
            binance_client: backend.api_client.binance_client.BinanceClient 인스턴스
        """
        self.client = binance_client
        self.cache = MarketDataCache()
        self._running = False
        self._update_tasks: Dict[str, asyncio.Task] = {}
    
    async def fetch_historical_candles(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Candle]:
        """
        과거 캔들 데이터 조회 (Binance REST API)
        
        Args:
            symbol: 심볼 (예: "BTCUSDT")
            interval: 타임프레임 (예: "1m", "3m", "15m")
            limit: 조회 개수 (최대 1500)
            start_time: 시작 시간 (Unix timestamp ms)
            end_time: 종료 시간 (Unix timestamp ms)
        
        Returns:
            Candle 리스트 (시간 오름차순)
        
        Raises:
            APIError: API 호출 실패 시
        """
        if interval not in self.KLINE_INTERVALS:
            raise ValueError(f"지원하지 않는 타임프레임: {interval}")
        
        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=min(limit, 1500),
                start_time=start_time,
                end_time=end_time
            )
            
            candles = []
            for k in klines:
                candle = Candle(
                    symbol=symbol,
                    interval=interval,
                    open_time=int(k[0]),
                    close_time=int(k[6]),
                    open=float(k[1]),
                    high=float(k[2]),
                    low=float(k[3]),
                    close=float(k[4]),
                    volume=float(k[5]),
                    quote_volume=float(k[7]),
                    trades_count=int(k[8])
                )
                candles.append(candle)
            
            # 캐시 업데이트
            self.cache.add_candles_bulk(candles)
            
            logger.info(f"과거 캔들 {len(candles)}개 조회 완료: {symbol}/{interval}")
            return candles
            
        except Exception as e:
            logger.error(f"과거 캔들 조회 실패: {symbol}/{interval} - {e}")
            raise APIError(f"Binance Klines API 오류: {e}") from e
    
    async def get_latest_candles(self, symbol: str, interval: str, count: int) -> List[Candle]:
        """
        캐시에서 최신 N개 캔들 조회 (부족 시 API 요청)
        
        Args:
            symbol: 심볼
            interval: 타임프레임
            count: 필요한 캔들 개수
        
        Returns:
            Candle 리스트 (시간 오름차순)
        
        Raises:
            InsufficientDataError: 데이터 부족 시
        """
        # 캐시에 충분한 데이터 있는지 확인
        if self.cache.has_sufficient_data(symbol, interval, count):
            return self.cache.get_latest_candles(symbol, interval, count)
        
        # 부족하면 API에서 조회
        logger.warning(
            f"캐시 데이터 부족({symbol}/{interval}), API 조회 중... (필요: {count})"
        )
        await self.fetch_historical_candles(symbol, interval, limit=max(count, 500))
        
        # 재시도
        if self.cache.has_sufficient_data(symbol, interval, count):
            return self.cache.get_latest_candles(symbol, interval, count)
        else:
            raise InsufficientDataError(
                f"API 조회 후에도 데이터 부족: {symbol}/{interval} (필요: {count})"
            )
    
    async def start_realtime_updates(
        self,
        symbols: List[str],
        intervals: List[str],
        on_candle_update: Optional[Callable[[Candle], None]] = None
    ) -> None:
        """
        실시간 캔들 업데이트 시작 (WebSocket)
        
        Args:
            symbols: 구독할 심볼 리스트
            intervals: 구독할 타임프레임 리스트
            on_candle_update: 캔들 업데이트 시 호출할 콜백 (선택)
        
        Note:
            - 현재는 폴링 방식으로 구현 (1초마다 최신 캔들 조회)
            - 추후 WebSocket으로 전환 가능
        """
        if self._running:
            logger.warning("실시간 업데이트가 이미 실행 중입니다")
            return
        
        self._running = True
        logger.info(f"실시간 업데이트 시작: {len(symbols)} symbols, {len(intervals)} intervals")
        
        # 각 심볼/타임프레임 조합마다 폴링 태스크 생성
        for symbol in symbols:
            for interval in intervals:
                key = f"{symbol}_{interval}"
                task = asyncio.create_task(
                    self._poll_candle_updates(symbol, interval, on_candle_update)
                )
                self._update_tasks[key] = task
    
    async def _poll_candle_updates(
        self,
        symbol: str,
        interval: str,
        on_candle_update: Optional[Callable[[Candle], None]]
    ) -> None:
        """개별 심볼/타임프레임 폴링 태스크"""
        while self._running:
            try:
                # 최신 캔들 1개 조회
                candles = await self.fetch_historical_candles(symbol, interval, limit=1)
                if candles:
                    latest = candles[0]
                    
                    # 콜백 호출
                    if on_candle_update:
                        try:
                            on_candle_update(latest)
                        except Exception as e:
                            logger.error(f"캔들 업데이트 콜백 오류: {e}")
                
                # 1초 대기
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"캔들 폴링 오류 ({symbol}/{interval}): {e}")
                await asyncio.sleep(5)  # 오류 시 5초 대기 후 재시도
    
    async def stop_realtime_updates(self) -> None:
        """실시간 업데이트 중지"""
        if not self._running:
            return
        
        self._running = False
        
        # 모든 폴링 태스크 취소
        for task in self._update_tasks.values():
            task.cancel()
        
        # 태스크 완료 대기
        await asyncio.gather(*self._update_tasks.values(), return_exceptions=True)
        self._update_tasks.clear()
        
        logger.info("실시간 업데이트 중지 완료")
    
    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """캐시 초기화"""
        self.cache.clear(symbol)
        logger.info(f"캐시 초기화: {symbol or '전체'}")
