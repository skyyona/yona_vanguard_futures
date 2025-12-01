"""IndicatorEngine 단위 테스트"""
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.core.new_strategy.data_structures import Candle
from backend.core.new_strategy.indicator_engine import IndicatorEngine
import pytest


def test_indicator_calculation():
    """지표 계산 테스트"""
    print("=" * 60)
    print("IndicatorEngine 테스트 시작")
    print("=" * 60)
    
    # 테스트용 캔들 데이터 생성 (200개)
    candles = []
    base_price = 50000.0
    
    for i in range(200):
        # 간단한 상승 추세 시뮬레이션
        price_variation = (i % 10 - 5) * 100  # -500 ~ +400
        close = base_price + i * 10 + price_variation
        high = close + 50
        low = close - 50
        volume = 1000000.0 + (i % 20) * 50000
        
        candle = Candle(
            symbol="BTCUSDT",
            interval="1m",
            open_time=1700000000000 + i * 60000,
            close_time=1700000000000 + (i + 1) * 60000,
            open=close - 10,
            high=high,
            low=low,
            close=close,
            volume=volume,
            quote_volume=volume * close,
            trades_count=1000 + i
        )
        candles.append(candle)
    
    print(f"\n생성된 캔들 수: {len(candles)}")
    print(f"심볼: {candles[0].symbol}")
    print(f"타임프레임: {candles[0].interval}")
    print(f"가격 범위: {candles[0].close:.2f} ~ {candles[-1].close:.2f}")
    
    # IndicatorEngine 초기화 및 계산
    engine = IndicatorEngine()
    
    try:
        indicators = engine.calculate(candles)
        
        print("\n" + "=" * 60)
        print("지표 계산 결과")
        print("=" * 60)
        
        print(f"\n[EMA 계열]")
        print(f"  EMA(5):   {indicators.ema_5:.2f}")
        print(f"  EMA(10):  {indicators.ema_10:.2f}")
        print(f"  EMA(20):  {indicators.ema_20:.2f}")
        print(f"  EMA(60):  {indicators.ema_60:.2f}")
        print(f"  EMA(120): {indicators.ema_120:.2f}")
        
        print(f"\n[RSI]")
        print(f"  RSI(14): {indicators.rsi_14:.2f}")
        
        print(f"\n[Stochastic RSI]")
        print(f"  %K: {indicators.stoch_rsi_k:.2f}")
        print(f"  %D: {indicators.stoch_rsi_d:.2f}")
        
        print(f"\n[MACD]")
        print(f"  MACD Line:   {indicators.macd_line:.4f}")
        print(f"  Signal Line: {indicators.macd_signal:.4f}")
        print(f"  Histogram:   {indicators.macd_histogram:.4f}")
        
        print(f"\n[VWAP & ATR]")
        print(f"  VWAP:    {indicators.vwap:.2f}")
        print(f"  ATR(14): {indicators.atr_14:.2f}")
        
        print(f"\n[거래량]")
        print(f"  Volume Spike: {indicators.volume_spike}")
        print(f"  Volume Avg(20): {indicators.volume_avg_20:.2f}")
        
        print(f"\n[추세]")
        print(f"  Trend: {indicators.trend}")
        
        # 검증
        print("\n" + "=" * 60)
        print("검증 결과")
        print("=" * 60)
        
        is_valid = engine.validate_indicators(indicators)
        print(f"지표 유효성: {'✓ 통과' if is_valid else '✗ 실패'}")
        
        # EMA 정렬 확인 (상승 추세이므로 짧은 기간이 더 높아야 함)
        ema_order_ok = indicators.ema_5 >= indicators.ema_10 >= indicators.ema_20
        print(f"EMA 정렬 (5>=10>=20): {'✓ 통과' if ema_order_ok else '✗ 실패'}")
        
        # RSI 범위 확인
        rsi_range_ok = 0 <= indicators.rsi_14 <= 100
        print(f"RSI 범위 (0-100): {'✓ 통과' if rsi_range_ok else '✗ 실패'}")
        
        # Stoch RSI 범위 확인
        stoch_range_ok = 0 <= indicators.stoch_rsi_k <= 100 and 0 <= indicators.stoch_rsi_d <= 100
        print(f"Stoch RSI 범위 (0-100): {'✓ 통과' if stoch_range_ok else '✗ 실패'}")
        
        # ATR 양수 확인
        atr_positive = indicators.atr_14 > 0
        print(f"ATR 양수: {'✓ 통과' if atr_positive else '✗ 실패'}")
        
        # 종합 결과
        all_ok = is_valid and ema_order_ok and rsi_range_ok and stoch_range_ok and atr_positive
        
        print("\n" + "=" * 60)
        if all_ok:
            print("✓ 모든 테스트 통과!")
        else:
            print("✗ 일부 테스트 실패")
        print("=" * 60)
        
        # Assert overall validity
        assert all_ok, "Indicator validation failed or some indicator checks did not pass"
    except Exception as e:
        print(f"\n✗ 지표 계산 실패: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"지표 계산 중 예외 발생: {e}")


def test_insufficient_data():
    """데이터 부족 시 예외 처리 테스트"""
    print("\n" + "=" * 60)
    print("데이터 부족 예외 처리 테스트")
    print("=" * 60)
    
    # 50개만 생성 (200개 필요)
    candles = []
    for i in range(50):
        candle = Candle(
            symbol="BTCUSDT",
            interval="1m",
            open_time=1700000000000 + i * 60000,
            close_time=1700000000000 + (i + 1) * 60000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50000.0,
            volume=1000000.0,
            quote_volume=50000000000.0,
            trades_count=1000
        )
        candles.append(candle)
    
    engine = IndicatorEngine()
    
    try:
        engine.calculate(candles)
        pytest.fail("데이터 부족 시 예외가 발생해야 합니다")
    except Exception as e:
        print(f"✓ 예상된 예외 발생: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("\nIndicatorEngine 테스트 실행\n")
    
    test1_ok = test_indicator_calculation()
    test2_ok = test_insufficient_data()
    
    print("\n" + "=" * 60)
    print("전체 테스트 결과")
    print("=" * 60)
    print(f"지표 계산 테스트: {'✓ 통과' if test1_ok else '✗ 실패'}")
    print(f"데이터 부족 테스트: {'✓ 통과' if test2_ok else '✗ 실패'}")
    
    if test1_ok and test2_ok:
        print("\n✓✓✓ 모든 테스트 통과! ✓✓✓")
    else:
        print("\n✗✗✗ 일부 테스트 실패 ✗✗✗")
    print("=" * 60)
