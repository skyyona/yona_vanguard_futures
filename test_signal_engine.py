"""SignalEngine 단위 테스트"""
from backend.core.new_strategy.data_structures import IndicatorSet
from backend.core.new_strategy.signal_engine import SignalEngine, SignalEngineConfig


def build_indicator(
    symbol: str,
    ts: int,
    ema5, ema10, ema20, ema60, ema120,
    rsi, k, d,
    macd, macds, h,
    vwap,
    vol_spike: bool,
    trend: str,
):
    return IndicatorSet(
        symbol=symbol,
        timestamp=ts,
        ema_5=ema5,
        ema_10=ema10,
        ema_20=ema20,
        ema_60=ema60,
        ema_120=ema120,
        rsi_14=rsi,
        stoch_rsi_k=k,
        stoch_rsi_d=d,
        macd_line=macd,
        macd_signal=macds,
        macd_histogram=h,
        vwap=vwap,
        atr_14=50.0,
        volume_spike=vol_spike,
        volume_avg_20=1000.0,
        trend=trend,
    )


def test_entry_strong_signal():
    engine = SignalEngine(SignalEngineConfig())

    prev = build_indicator(
        "BTCUSDT", 1700000000000,
        52100, 52000, 51900, 51600, 51300,
        32, 30, 35,
        -5, 0, -5,
        51900,
        False,
        "UPTREND",
    )

    curr = build_indicator(
        "BTCUSDT", 1700000060000,
        52250, 52150, 52000, 51680, 51370,
        45, 60, 55,
        10, 5, 5,
        51950,
        True,
        "STRONG_UPTREND",
    )

    confirm3m = build_indicator(
        "BTCUSDT", 1700000060000,
        52200, 52100, 51980, 51650, 51350,
        48, 55, 50,
        8, 4, 4,
        51930,
        False,
        "UPTREND",
    )

    result = engine.evaluate(curr, last_close=52300.0, prev_1m=prev, confirm_3m=confirm3m, filter_15m=None, in_position=False)

    print("Action:", result.action)
    print("Score:", result.score)
    print("Confidence:", result.confidence_pct)
    print("Triggers:", result.triggers)

    assert result.action.name in ("BUY_LONG", "HOLD")
    assert result.score >= 100.0


def test_exit_signal():
    engine = SignalEngine(SignalEngineConfig())

    prev = build_indicator(
        "BTCUSDT", 1700000000000,
        52000, 51950, 51900, 51700, 51400,
        65, 88, 85,
        5, 8, -3,
        51900,
        False,
        "UPTREND",
    )

    curr = build_indicator(
        "BTCUSDT", 1700000060000,
        51800, 51850, 51890, 51950, 51450,
        60, 75, 82,
        2, 5, -6,
        51920,
        False,
        "DOWNTREND",
    )

    result = engine.evaluate(curr, last_close=51850.0, prev_1m=prev, confirm_3m=None, filter_15m=None, in_position=True)

    print("Exit Action:", result.action)
    print("Exit Score:", result.score)
    print("Exit Triggers:", result.triggers)

    assert result.action.name in ("CLOSE_LONG", "HOLD")


if __name__ == "__main__":
    print("SignalEngine 테스트 실행")
    ok1 = False
    ok2 = False
    try:
        test_entry_strong_signal()
        ok1 = True
        print("✓ 진입 신호 테스트 통과")
    except AssertionError as e:
        print("✗ 진입 신호 테스트 실패:", e)
    try:
        test_exit_signal()
        ok2 = True
        print("✓ 청산 신호 테스트 통과")
    except AssertionError as e:
        print("✗ 청산 신호 테스트 실패:", e)
    print("전체 결과:", "✓" if (ok1 and ok2) else "✗")
