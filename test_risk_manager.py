"""RiskManager 단위 테스트"""
from backend.core.new_strategy.data_structures import PositionState, PositionSide, ExitReason
from backend.core.new_strategy.signal_engine import SignalResult, SignalAction
from backend.core.new_strategy.indicator_engine import IndicatorEngine
from backend.core.new_strategy.risk_manager import RiskManager, RiskManagerConfig
from backend.core.new_strategy.data_structures import IndicatorSet


def build_indicator(symbol: str, ts: int) -> IndicatorSet:
    return IndicatorSet(
        symbol=symbol,
        timestamp=ts,
        ema_5=52000, ema_10=51950, ema_20=51900, ema_60=51700, ema_120=51400,
        rsi_14=55,
        stoch_rsi_k=70, stoch_rsi_d=65,
        macd_line=10, macd_signal=5, macd_histogram=5,
        vwap=51800,
        atr_14=50.0,
        volume_spike=False,
        volume_avg_20=1000.0,
        trend="UPTREND",
    )


def make_position(entry: float, opened_at: int) -> PositionState:
    return PositionState(
        symbol="BTCUSDT",
        side=PositionSide.LONG,
        entry_price=entry,
        quantity=0.01,
        leverage=50,
        opened_at=opened_at,
        highest_price=entry,
        lowest_price=entry,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=0.0,
        stop_loss_price=entry * (1 - 0.005),
        take_profit_price=entry * (1 + 0.037),
        trailing_activated=False,
    )


def test_stop_loss_trigger():
    rm = RiskManager(RiskManagerConfig())
    pos = make_position(100.0, 1700000000000)
    ind = build_indicator("BTCUSDT", 1700000060000)

    # -0.6% 하락
    exit_sig = rm.evaluate(pos, current_price=99.4, indicators_1m=ind, last_signal=None, now_ms=1700000060000)
    print("StopLoss:", exit_sig)
    assert exit_sig is not None
    assert exit_sig.reason == ExitReason.STOP_LOSS


def test_primary_tp_then_extend_with_energy():
    rm = RiskManager(RiskManagerConfig())
    pos = make_position(100.0, 1700000000000)
    ind = build_indicator("BTCUSDT", 1700000060000)

    # 강한 에너지 신호 (점수 160)
    strong_signal = SignalResult(
        symbol="BTCUSDT", timestamp=ind.timestamp,
        action=SignalAction.BUY_LONG, score=160.0, confidence_pct=94.0,
        triggers=["test"], reason="test"
    )

    # +3% 구간: 2% 선확정 후 3.5% 확장 목표 설정되어야 함(종가<3.5%이므로 보유)
    exit_sig = rm.evaluate(pos, current_price=103.0, indicators_1m=ind, last_signal=strong_signal, now_ms=ind.timestamp)
    print("ExtendHold:", exit_sig, pos.stop_loss_price, pos.take_profit_price)
    assert exit_sig is None
    # 스탑은 최소 102 이상으로 올라가야 함
    assert pos.stop_loss_price >= 102.0
    # 확장 TP(103.5) 설정
    assert abs(pos.take_profit_price - 103.5) < 1e-6

    # 트레일링 동작 확인: 최고가 103, trail=103*(1-0.006)=102.382 -> 스탑이 그 이상이어야 함
    assert pos.stop_loss_price >= 102.382

    # 하락하여 트레일링 체결
    exit_sig2 = rm.evaluate(pos, current_price=102.3, indicators_1m=ind, last_signal=strong_signal, now_ms=ind.timestamp)
    print("TrailExit:", exit_sig2)
    assert exit_sig2 is not None
    assert exit_sig2.reason in (ExitReason.TRAILING_STOP, ExitReason.TAKE_PROFIT)


def test_primary_tp_then_close_on_weak_energy():
    rm = RiskManager(RiskManagerConfig())
    pos = make_position(100.0, 1700000000000)
    ind = build_indicator("BTCUSDT", 1700000060000)

    weak_signal = SignalResult(
        symbol="BTCUSDT", timestamp=ind.timestamp,
        action=SignalAction.HOLD, score=100.0, confidence_pct=65.0,
        triggers=["test"], reason="weak"
    )

    # +2.1% 구간: 에너지가 약하므로 즉시 익절
    exit_sig = rm.evaluate(pos, current_price=102.1, indicators_1m=ind, last_signal=weak_signal, now_ms=ind.timestamp)
    print("CloseAt2%:", exit_sig)
    assert exit_sig is not None
    assert exit_sig.reason == ExitReason.TAKE_PROFIT


if __name__ == "__main__":
    print("RiskManager 테스트 실행")
    test_stop_loss_trigger()
    test_primary_tp_then_extend_with_energy()
    test_primary_tp_then_close_on_weak_energy()
    print("✓ 모든 테스트 통과")
