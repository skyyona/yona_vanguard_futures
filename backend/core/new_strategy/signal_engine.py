"""신호 생성 엔진 - 점수 기반 진입/청산 결정"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
import logging

from .data_structures import IndicatorSet, SignalResult, SignalAction

logger = logging.getLogger(__name__)


@dataclass
class SignalEngineConfig:
    min_entry_score: float = 100.0
    strong_entry_score: float = 130.0
    instant_entry_score: float = 160.0

    # 가중치 (최대 총점 170)
    w_volume_spike: float = 30.0
    w_vwap_breakout: float = 25.0
    w_5m_uptrend: float = 20.0
    w_ema_alignment: float = 20.0
    w_consecutive_rise: float = 15.0
    w_3m_trend_confirm: float = 20.0
    w_bear_energy_fade: float = 15.0
    w_macd_golden_cross: float = 15.0
    w_rsi_oversold_rebound: float = 10.0


class SignalEngine:
    """지표 집합을 기반으로 점수화하여 매매 신호를 생성"""

    def __init__(self, config: Optional[SignalEngineConfig] = None):
        self.config = config or SignalEngineConfig()

    def evaluate(
        self,
        current_1m: IndicatorSet,
        last_close: float,
        prev_1m: Optional[IndicatorSet] = None,
        confirm_3m: Optional[IndicatorSet] = None,
        filter_15m: Optional[IndicatorSet] = None,
        in_position: bool = False,
    ) -> SignalResult:
        """현재 지표를 바탕으로 진입/청산/HOLD 신호 산출"""
        if in_position:
            exit_action, exit_score, exit_triggers = self._evaluate_exit(current_1m, prev_1m)
            if exit_action == SignalAction.CLOSE_LONG:
                return SignalResult(
                    symbol=current_1m.symbol,
                    timestamp=current_1m.timestamp,
                    action=SignalAction.CLOSE_LONG,
                    score=exit_score,
                    confidence_pct=min(100.0, max(0.0, exit_score)),
                    triggers=exit_triggers,
                    reason="Exit conditions triggered",
                )
            # 유지
            return SignalResult(
                symbol=current_1m.symbol,
                timestamp=current_1m.timestamp,
                action=SignalAction.HOLD,
                score=0.0,
                confidence_pct=0.0,
                triggers=[],
                reason="No exit conditions",
            )

        # 필터: 15m이 명확히 하락이면 진입 억제
        if filter_15m and filter_15m.trend == "DOWNTREND":
            return SignalResult(
                symbol=current_1m.symbol,
                timestamp=current_1m.timestamp,
                action=SignalAction.HOLD,
                score=0.0,
                confidence_pct=0.0,
                triggers=["15m DOWNTREND filter"],
                reason="Higher timeframe downtrend filter",
            )

        score, triggers = self._score_entry(
            current_1m=current_1m,
            last_close=last_close,
            prev_1m=prev_1m,
            confirm_3m=confirm_3m,
        )

        confidence = min(100.0, round((score / 170.0) * 100.0, 2))

        if score >= self.config.instant_entry_score:
            action = SignalAction.BUY_LONG
            reason = "Instant entry threshold met"
        elif score >= self.config.strong_entry_score:
            action = SignalAction.BUY_LONG
            reason = "Strong entry threshold met"
        elif score >= self.config.min_entry_score:
            action = SignalAction.HOLD
            reason = "Watchlist threshold met"
        else:
            action = SignalAction.HOLD
            reason = "No entry"

        return SignalResult(
            symbol=current_1m.symbol,
            timestamp=current_1m.timestamp,
            action=action,
            score=score,
            confidence_pct=confidence,
            triggers=triggers,
            reason=reason,
        )

    def _score_entry(
        self,
        current_1m: IndicatorSet,
        last_close: float,
        prev_1m: Optional[IndicatorSet] = None,
        confirm_3m: Optional[IndicatorSet] = None,
    ) -> Tuple[float, List[str]]:
        c = self.config
        score = 0.0
        triggers: List[str] = []

        # 거래량 급증
        if current_1m.volume_spike:
            score += c.w_volume_spike
            triggers.append("Volume spike")

        # VWAP 돌파 (종가 > VWAP)
        if current_1m.vwap is not None and last_close is not None:
            if last_close > current_1m.vwap:
                score += c.w_vwap_breakout
                triggers.append("VWAP breakout")

        # 5m 상승 추세 ~ 1m 기준 EMA20>EMA60
        if (current_1m.ema_20 is not None and current_1m.ema_60 is not None and
                current_1m.ema_20 > current_1m.ema_60):
            score += c.w_5m_uptrend
            triggers.append("Uptrend (EMA20>EMA60)")

        # EMA 정렬 (5>10>20>60>120)
        e5, e10, e20, e60, e120 = (
            current_1m.ema_5, current_1m.ema_10, current_1m.ema_20, current_1m.ema_60, current_1m.ema_120
        )
        if all(v is not None for v in [e5, e10, e20, e60, e120]):
            if e5 > e10 > e20 > e60 > e120:
                score += c.w_ema_alignment
                triggers.append("EMA alignment 5>10>20>60>120")

        # 연속 상승 (EMA20 상승 기울기)
        if prev_1m and current_1m.ema_20 is not None and prev_1m.ema_20 is not None:
            if current_1m.ema_20 > prev_1m.ema_20:
                score += c.w_consecutive_rise
                triggers.append("EMA20 rising")

        # 3m 추세 확인
        if confirm_3m and confirm_3m.trend in ("UPTREND", "STRONG_UPTREND"):
            score += c.w_3m_trend_confirm
            triggers.append("3m trend confirm")

        # 음봉 에너지 소멸 ~ MACD 히스토그램 증가
        if prev_1m and current_1m.macd_histogram is not None and prev_1m.macd_histogram is not None:
            if current_1m.macd_histogram > prev_1m.macd_histogram:
                score += c.w_bear_energy_fade
                triggers.append("Histogram rising")

        # MACD 골든크로스
        if current_1m.macd_line is not None and current_1m.macd_signal is not None:
            if prev_1m and prev_1m.macd_line is not None and prev_1m.macd_signal is not None:
                if prev_1m.macd_line <= prev_1m.macd_signal and current_1m.macd_line > current_1m.macd_signal:
                    score += c.w_macd_golden_cross
                    triggers.append("MACD golden cross")
            elif current_1m.macd_line > current_1m.macd_signal:
                score += min(c.w_macd_golden_cross, 10.0)
                triggers.append("MACD bullish")

        # RSI 과매도 반등
        if prev_1m and current_1m.rsi_14 is not None and prev_1m.rsi_14 is not None:
            if prev_1m.rsi_14 < 35.0 and current_1m.rsi_14 > prev_1m.rsi_14:
                score += c.w_rsi_oversold_rebound
                triggers.append("RSI rebound from oversold")

        return score, triggers

    def _evaluate_exit(
        self,
        current_1m: IndicatorSet,
        prev_1m: Optional[IndicatorSet] = None,
    ) -> Tuple[SignalAction, float, List[str]]:
        exit_triggers: List[str] = []
        exit_score = 0.0

        # EMA 역전
        if current_1m.ema_20 is not None and current_1m.ema_60 is not None:
            if current_1m.ema_20 < current_1m.ema_60 * 0.999:
                exit_triggers.append("EMA20 below EMA60")
                exit_score += 50.0

        # MACD 데드크로스 + 히스토그램 약세
        if current_1m.macd_line is not None and current_1m.macd_signal is not None:
            if current_1m.macd_line < current_1m.macd_signal:
                exit_triggers.append("MACD dead cross")
                exit_score += 40.0
        if current_1m.macd_histogram is not None and prev_1m and prev_1m.macd_histogram is not None:
            if current_1m.macd_histogram < prev_1m.macd_histogram:
                exit_triggers.append("Histogram falling")
                exit_score += 20.0

        # Stoch RSI 과매수 하향 교차
        if (
            current_1m.stoch_rsi_k is not None and current_1m.stoch_rsi_d is not None and
            prev_1m and prev_1m.stoch_rsi_k is not None and prev_1m.stoch_rsi_d is not None
        ):
            if prev_1m.stoch_rsi_k >= prev_1m.stoch_rsi_d and current_1m.stoch_rsi_k < current_1m.stoch_rsi_d and current_1m.stoch_rsi_k > 80.0:
                exit_triggers.append("Stoch RSI overbought cross down")
                exit_score += 20.0

        if exit_triggers:
            return SignalAction.CLOSE_LONG, min(100.0, exit_score), exit_triggers
        else:
            return SignalAction.HOLD, 0.0, []
