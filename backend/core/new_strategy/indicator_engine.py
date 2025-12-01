"""지표 계산 엔진 - 실데이터 기반 기술적 지표 계산"""
from typing import List, Dict, Optional
import logging
from collections import deque

from .data_structures import Candle, IndicatorSet, InsufficientDataError

logger = logging.getLogger(__name__)


class IndicatorEngine:
    """
    기술적 지표 계산 엔진
    
    지원 지표:
    - EMA (5, 10, 20, 60, 120)
    - RSI (14)
    - Stochastic RSI (K, D)
    - MACD (12, 26, 9)
    - VWAP (실계산)
    - ATR (14)
    - Volume Spike (20일 평균 대비 3배)
    """
    
    def __init__(self):
        self.required_candles = 200  # 안전한 계산을 위한 최소 캔들 수
    
    def calculate(self, candles: List[Candle]) -> IndicatorSet:
        """
        캔들 데이터로부터 모든 지표 계산
        
        Args:
            candles: 시간 순서대로 정렬된 캔들 리스트 (오래된 것 -> 최신)
        
        Returns:
            IndicatorSet (최신 값)
        
        Raises:
            InsufficientDataError: 캔들 데이터 부족 시
        """
        if len(candles) < self.required_candles:
            raise InsufficientDataError(
                f"지표 계산에 필요한 최소 캔들 수: {self.required_candles}, 현재: {len(candles)}"
            )
        
        symbol = candles[-1].symbol
        timestamp = candles[-1].close_time
        
        # 가격 시계열 추출
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]
        typical_prices = [(c.high + c.low + c.close) / 3.0 for c in candles]
        
        # 지표 계산
        ema_5_series = self._calculate_ema(closes, 5)
        ema_10_series = self._calculate_ema(closes, 10)
        ema_20_series = self._calculate_ema(closes, 20)
        ema_60_series = self._calculate_ema(closes, 60)
        ema_120_series = self._calculate_ema(closes, 120)
        
        rsi_14_series = self._calculate_rsi(closes, 14)
        
        stoch_rsi = self._calculate_stochastic_rsi(rsi_14_series, 14)
        
        macd_result = self._calculate_macd(closes, 12, 26, 9)
        
        vwap_series = self._calculate_vwap(typical_prices, volumes)
        
        atr_14_series = self._calculate_atr(highs, lows, closes, 14)
        
        volume_spike, volume_avg = self._calculate_volume_spike(volumes, 20, 3.0)
        
        # 추세 판단
        trend = self._determine_trend(
            ema_20_series[-1],
            ema_60_series[-1],
            ema_120_series[-1]
        )
        
        # IndicatorSet 생성 (최신 값만)
        indicator_set = IndicatorSet(
            symbol=symbol,
            timestamp=timestamp,
            ema_5=ema_5_series[-1],
            ema_10=ema_10_series[-1],
            ema_20=ema_20_series[-1],
            ema_60=ema_60_series[-1],
            ema_120=ema_120_series[-1],
            rsi_14=rsi_14_series[-1],
            stoch_rsi_k=stoch_rsi["k"],
            stoch_rsi_d=stoch_rsi["d"],
            macd_line=macd_result["macd"],
            macd_signal=macd_result["signal"],
            macd_histogram=macd_result["histogram"],
            vwap=vwap_series[-1],
            atr_14=atr_14_series[-1],
            volume_spike=volume_spike,
            volume_avg_20=volume_avg,
            trend=trend
        )
        
        logger.debug(
            f"지표 계산 완료: {symbol} - Trend={trend}, RSI={rsi_14_series[-1]:.2f}, "
            f"MACD={macd_result['macd']:.4f}, VolSpike={volume_spike}"
        )
        
        return indicator_set
    
    def _calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """
        지수 이동 평균 (Exponential Moving Average)
        
        EMA = Price(t) * k + EMA(t-1) * (1 - k)
        k = 2 / (period + 1)
        """
        if len(prices) < period:
            return [prices[0]] * len(prices)
        
        k = 2.0 / (period + 1)
        ema_values = []
        ema = prices[0]  # 첫 번째 값으로 초기화
        
        for price in prices:
            ema = price * k + ema * (1 - k)
            ema_values.append(ema)
        
        return ema_values
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """
        상대 강도 지수 (Relative Strength Index)
        
        RSI = 100 - (100 / (1 + RS))
        RS = 평균 상승폭 / 평균 하락폭
        """
        if len(prices) < period + 1:
            return [50.0] * len(prices)
        
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [max(0.0, d) for d in deltas]
        losses = [max(0.0, -d) for d in deltas]
        
        # 초기 평균 계산 (SMA)
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        rsi_values = [50.0] * (period + 1)  # 초기값 50으로 패딩
        
        # Wilder's smoothing (EMA-like)
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100.0 - (100.0 / (1.0 + rs))
            
            rsi_values.append(rsi)
        
        return rsi_values
    
    def _calculate_stochastic_rsi(self, rsi_series: List[float], period: int = 14) -> Dict[str, float]:
        """
        Stochastic RSI
        
        %K = (RSI - RSI_min) / (RSI_max - RSI_min) * 100
        %D = %K의 3일 이동평균
        """
        if len(rsi_series) < period:
            return {"k": 50.0, "d": 50.0}
        
        # 최근 period개 RSI 값으로 Stoch 계산
        rsi_window = rsi_series[-period:]
        rsi_min = min(rsi_window)
        rsi_max = max(rsi_window)
        
        if rsi_max > rsi_min:
            k_values = [(rsi - rsi_min) / (rsi_max - rsi_min) * 100.0 for rsi in rsi_window]
            k = k_values[-1]
            
            # %D는 최근 3개 %K의 평균
            if len(k_values) >= 3:
                d = sum(k_values[-3:]) / 3.0
            else:
                d = k
        else:
            k = 50.0
            d = 50.0
        
        return {"k": k, "d": d}
    
    def _calculate_macd(
        self,
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, float]:
        """
        MACD (Moving Average Convergence Divergence)
        
        MACD Line = EMA(12) - EMA(26)
        Signal Line = EMA(MACD, 9)
        Histogram = MACD - Signal
        """
        if len(prices) < slow_period + signal_period:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
        
        ema_fast = self._calculate_ema(prices, fast_period)
        ema_slow = self._calculate_ema(prices, slow_period)
        
        macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(prices))]
        signal_line = self._calculate_ema(macd_line, signal_period)
        histogram = [macd_line[i] - signal_line[i] for i in range(len(macd_line))]
        
        return {
            "macd": macd_line[-1],
            "signal": signal_line[-1],
            "histogram": histogram[-1]
        }
    
    def _calculate_vwap(self, typical_prices: List[float], volumes: List[float]) -> List[float]:
        """
        VWAP (Volume Weighted Average Price) - 실계산
        
        VWAP(t) = Σ(TP * Volume) / Σ(Volume)
        TP = (High + Low + Close) / 3
        
        Note: 누적 계산 (일중 초기화 필요 시 별도 로직 추가)
        """
        if len(typical_prices) != len(volumes):
            raise ValueError("typical_prices와 volumes 길이가 다릅니다")
        
        vwap_series = []
        cumulative_pv = 0.0  # price * volume 누적
        cumulative_v = 0.0   # volume 누적
        
        for tp, vol in zip(typical_prices, volumes):
            vol = max(0.0, vol)  # 음수 거래량 방지
            cumulative_pv += tp * vol
            cumulative_v += vol
            
            if cumulative_v > 0:
                vwap = cumulative_pv / cumulative_v
            else:
                vwap = tp  # 거래량 없으면 현재가 사용
            
            vwap_series.append(vwap)
        
        return vwap_series
    
    def _calculate_atr(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> List[float]:
        """
        ATR (Average True Range)
        
        TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
        ATR = EMA(TR, period)
        """
        if len(highs) != len(lows) or len(lows) != len(closes):
            raise ValueError("highs, lows, closes 길이가 다릅니다")
        
        if len(closes) < 2:
            return [0.0] * len(closes)
        
        # True Range 계산
        true_ranges = [highs[0] - lows[0]]  # 첫 번째 TR은 High - Low
        
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close_prev = abs(highs[i] - closes[i - 1])
            low_close_prev = abs(lows[i] - closes[i - 1])
            
            tr = max(high_low, high_close_prev, low_close_prev)
            true_ranges.append(tr)
        
        # ATR = EMA of TR
        atr_series = self._calculate_ema(true_ranges, period)
        
        return atr_series
    
    def _calculate_volume_spike(
        self,
        volumes: List[float],
        lookback: int = 20,
        threshold_multiplier: float = 3.0
    ) -> tuple[bool, float]:
        """
        거래량 급증 감지
        
        Args:
            volumes: 거래량 시계열
            lookback: 평균 계산 기간
            threshold_multiplier: 급증 판단 배수 (기본 3배)
        
        Returns:
            (급증 여부, 평균 거래량)
        """
        if len(volumes) < lookback + 1:
            return False, 0.0
        
        # 최근 lookback개 평균 (현재 제외)
        recent_avg = sum(volumes[-(lookback + 1):-1]) / lookback
        current_volume = volumes[-1]
        
        if recent_avg > 0:
            is_spike = current_volume > (recent_avg * threshold_multiplier)
        else:
            is_spike = False
        
        return is_spike, recent_avg
    
    def _determine_trend(self, ema_20: float, ema_60: float, ema_120: float) -> str:
        """
        추세 판단 (EMA 배열 기반)
        
        Returns:
            "STRONG_UPTREND" | "UPTREND" | "DOWNTREND" | "NEUTRAL"
        """
        # 강한 상승 추세: EMA20 > EMA60 * 1.001 and EMA60 > EMA120 * 1.001
        if ema_20 > ema_60 * 1.001 and ema_60 > ema_120 * 1.001:
            return "STRONG_UPTREND"
        
        # 약한 상승 추세: EMA20 > EMA60
        elif ema_20 > ema_60:
            return "UPTREND"
        
        # 하락 추세: EMA20 < EMA60 * 0.999
        elif ema_20 < ema_60 * 0.999:
            return "DOWNTREND"
        
        # 중립
        else:
            return "NEUTRAL"
    
    def validate_indicators(self, indicators: IndicatorSet) -> bool:
        """
        지표 값 유효성 검증
        
        Returns:
            True if valid, False otherwise
        """
        # RSI 범위 체크 (0-100)
        if indicators.rsi_14 is not None:
            if not (0 <= indicators.rsi_14 <= 100):
                logger.warning(f"비정상 RSI 값: {indicators.rsi_14}")
                return False
        
        # Stoch RSI 범위 체크 (0-100)
        if indicators.stoch_rsi_k is not None:
            if not (0 <= indicators.stoch_rsi_k <= 100):
                logger.warning(f"비정상 Stoch RSI K 값: {indicators.stoch_rsi_k}")
                return False
        
        # EMA 양수 체크
        for ema_name in ["ema_5", "ema_10", "ema_20", "ema_60", "ema_120"]:
            ema_val = getattr(indicators, ema_name, None)
            if ema_val is not None and ema_val <= 0:
                logger.warning(f"비정상 {ema_name} 값: {ema_val}")
                return False
        
        # ATR 음수 체크
        if indicators.atr_14 is not None and indicators.atr_14 < 0:
            logger.warning(f"비정상 ATR 값: {indicators.atr_14}")
            return False
        
        return True
