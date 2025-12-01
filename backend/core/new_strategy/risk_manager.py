"""리스크 관리 엔진 - 손절/익절/트레일링/시간제한"""
from dataclasses import dataclass
from typing import Optional, List
import logging
import math

from .data_structures import (
    PositionState,
    PositionSide,
    IndicatorSet,
    SignalResult,
    SignalAction,
    ExitReason,
    ExitSignal,
)

logger = logging.getLogger(__name__)


@dataclass
class RiskManagerConfig:
    # 손절/익절/트레일링 설정
    stop_loss_pct: float = 0.005           # 0.5%
    tp_primary_pct: float = 0.02           # 2.0% 선확정
    tp_extended_pct: float = 0.035         # 3.5% 확장 익절 목표
    trailing_stop_pct: float = 0.006       # 0.6% (요청 반영)
    breakeven_trigger_pct: float = 0.01    # 1.0% 수익 시 본절 이동

    # 시간 제한 (분) - None이면 비활성
    time_limit_minutes: Optional[int] = None

    # 상승 에너지(신호 점수) 기준
    extended_energy_score_threshold: float = 130.0


class RiskManager:
    """
    포지션의 동적 손절/익절 관리:
    - 고정 손절: -0.5%
    - 선익절: +2% 도달 시
      - 최소 +2% 확정(스탑을 +2% 이상으로 끌어올림)
      - 상승 에너지(신호 점수) 충분하면 목표를 +3.5%로 확장해 보유
      - 에너지가 부족하면 즉시 익절
    - 트레일링: 활성화 후 최고가 대비 -0.6%
    - 본절 이동: +1% 수익 시 스탑을 진입가로 이동
    """

    def __init__(self, config: Optional[RiskManagerConfig] = None):
        self.config = config or RiskManagerConfig()
        self._risk_event_callback = None

    def set_risk_event_callback(self, callback):
        """리스크 이벤트 콜백 설정 (trailing, stop 이동 등)"""
        self._risk_event_callback = callback

    def _emit_risk_event(self, event_type: str, **kwargs):
        if self._risk_event_callback:
            try:
                self._risk_event_callback({"type": event_type, **kwargs})
            except Exception as e:
                logger.error(f"Risk event callback error: {e}")

    def evaluate(
        self,
        position: PositionState,
        current_price: float,
        indicators_1m: IndicatorSet,
        last_signal: Optional[SignalResult] = None,
        now_ms: Optional[int] = None,
    ) -> Optional[ExitSignal]:
        # 방향은 LONG만 지원 (설계 제약)
        if position.side != PositionSide.LONG:
            return None

        # 최고/최저 가격 갱신
        position.highest_price = max(position.highest_price, current_price)
        position.lowest_price = min(position.lowest_price, current_price)

        # 현재 손익률 계산
        pnl_pct = (current_price / position.entry_price - 1.0) * 100.0
        position.unrealized_pnl_pct = pnl_pct

        # 1) 시간 제한 체크
        if self._should_exit_by_time(now_ms, position.opened_at):
            return ExitSignal(
                symbol=position.symbol,
                timestamp=now_ms or indicators_1m.timestamp,
                reason=ExitReason.TIME_LIMIT,
                action=SignalAction.CLOSE_LONG,
                message="Time limit reached",
            )

        # 2) 고정 손절 (즉시)
        if pnl_pct <= -self.config.stop_loss_pct * 100.0:
            return ExitSignal(
                symbol=position.symbol,
                timestamp=now_ms or indicators_1m.timestamp,
                reason=ExitReason.STOP_LOSS,
                action=SignalAction.CLOSE_LONG,
                message=f"Stop loss hit ({pnl_pct:.2f}%)",
            )

        # 3) 본절 이동 (+1%) 및 트레일링 활성화
        if pnl_pct >= self.config.breakeven_trigger_pct * 100.0 and not position.trailing_activated:
            old_stop = position.stop_loss_price
            position.stop_loss_price = max(position.stop_loss_price, position.entry_price)
            position.trailing_activated = True
            self._emit_risk_event(
                "TRAILING_ACTIVATED",
                symbol=position.symbol,
                entry_price=position.entry_price,
                old_stop=old_stop,
                new_stop=position.stop_loss_price,
                pnl_pct=pnl_pct
            )

        # 4) +2% 선확정 로직
        if pnl_pct >= self.config.tp_primary_pct * 100.0:
            # 최소 +2% 확정: 스탑을 entry*(1+0.02) 이상으로
            min_lock_price = position.entry_price * (1.0 + self.config.tp_primary_pct)
            position.stop_loss_price = max(position.stop_loss_price, min_lock_price)

            # 상승 에너지 평가: 충분하면 +3.5% 목표, 부족하면 즉시 익절
            energy_ok = self._energy_is_strong(last_signal)
            if energy_ok:
                position.take_profit_price = position.entry_price * (1.0 + self.config.tp_extended_pct)
            else:
                return ExitSignal(
                    symbol=position.symbol,
                    timestamp=now_ms or indicators_1m.timestamp,
                    reason=ExitReason.TAKE_PROFIT,
                    action=SignalAction.CLOSE_LONG,
                    message="Take profit at +2% (insufficient momentum)",
                )

        # 5) 트레일링 스탑 업데이트 (활성화된 경우)
        if position.trailing_activated:
            trail_price = position.highest_price * (1.0 - self.config.trailing_stop_pct)
            # 2% 확정보다 낮아지지 않도록 보정
            min_lock_price = position.entry_price * (1.0 + self.config.tp_primary_pct)
            trail_price = max(trail_price, min_lock_price if pnl_pct >= self.config.tp_primary_pct * 100.0 else trail_price)
            position.stop_loss_price = max(position.stop_loss_price, trail_price)

            # 트레일링 스탑 체결
            if current_price <= position.stop_loss_price:
                return ExitSignal(
                    symbol=position.symbol,
                    timestamp=now_ms or indicators_1m.timestamp,
                    reason=ExitReason.TRAILING_STOP,
                    action=SignalAction.CLOSE_LONG,
                    message=f"Trailing stop hit at {position.stop_loss_price:.4f}",
                )

        # 6) 확장 익절 도달 (+3.5%)
        if position.take_profit_price and current_price >= position.take_profit_price:
            return ExitSignal(
                symbol=position.symbol,
                timestamp=now_ms or indicators_1m.timestamp,
                reason=ExitReason.TAKE_PROFIT,
                action=SignalAction.CLOSE_LONG,
                message="Extended take profit (+3.5%) reached",
            )

        # 보유
        return None

    def _should_exit_by_time(self, now_ms: Optional[int], opened_at_ms: int) -> bool:
        if self.config.time_limit_minutes is None:
            return False
        if now_ms is None:
            return False
        limit_ms = self.config.time_limit_minutes * 60 * 1000
        return (now_ms - opened_at_ms) >= limit_ms

    def _energy_is_strong(self, last_signal: Optional[SignalResult]) -> bool:
        if not last_signal:
            return False
        if last_signal.action == SignalAction.CLOSE_LONG:
            return False
        return last_signal.score >= self.config.extended_energy_score_threshold
