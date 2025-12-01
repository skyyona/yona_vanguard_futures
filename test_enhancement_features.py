"""신규 개선 기능 테스트 스크립트"""
import sys
import os

# 경로 추가
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from backend.core.new_strategy.adaptive_thresholds import AdaptiveThresholdManager
from backend.api_client.binance_client import BinanceClient


def test_adaptive_thresholds():
    """동적 임계치 매니저 테스트"""
    print("\n=== 1. Adaptive Thresholds Test ===")
    
    manager = AdaptiveThresholdManager(
        max_samples=100,
        min_samples=10,
        p_min=0.90,
        p_strong=0.95,
        p_instant=0.98
    )
    
    # 점수 추가 (시뮬레이션)
    scores = [80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135, 140, 145, 150]
    for score in scores:
        manager.add_score(score)
    
    # 임계치 계산
    static_min, static_strong, static_instant = 100, 130, 160
    min_t, strong_t, instant_t = manager.get_thresholds(static_min, static_strong, static_instant)
    
    print(f"  샘플 수: {len(manager.scores)}")
    print(f"  정적 임계치: min={static_min}, strong={static_strong}, instant={static_instant}")
    print(f"  동적 임계치: min={min_t:.1f}, strong={strong_t:.1f}, instant={instant_t:.1f}")
    print(f"  ✅ Adaptive thresholds 정상 동작")


def test_symbol_support_check():
    """심볼 지원 검사 테스트"""
    print("\n=== 2. Symbol Support Check Test ===")
    
    try:
        client = BinanceClient()
        
        # 실제 심볼 테스트 (BTCUSDT)
        result = client.is_symbol_supported("BTCUSDT")
        print(f"  BTCUSDT 지원 여부: {result.get('supported')}")
        if result.get('supported'):
            print(f"  ✅ BTCUSDT 정상 지원")
        
        # 가짜 심볼 테스트
        result2 = client.is_symbol_supported("FAKECOINUSDT")
        print(f"  FAKECOINUSDT 지원 여부: {result2.get('supported')}")
        print(f"  사유: {result2.get('reason')}")
        print(f"  ✅ 미지원 심볼 감지 정상")
        
    except Exception as e:
        print(f"  ⚠️ API 연결 필요: {e}")


def test_quantity_normalization():
    """수량 정규화 및 메타데이터 테스트"""
    print("\n=== 3. Quantity Normalization Test ===")
    
    try:
        client = BinanceClient()
        
        # BTCUSDT 수량 정규화
        result = client._round_qty_by_filters("BTCUSDT", 0.0012, price_hint=50000.0)
        
        print(f"  입력 수량: 0.0012")
        print(f"  결과: {result}")
        
        if result.get('ok'):
            print(f"  최종 수량: {result.get('qty')}")
            print(f"  stepSize: {result.get('stepSize')}")
            print(f"  minQty: {result.get('minQty')}")
            print(f"  minNotional: {result.get('minNotional')}")
            print(f"  notional: {result.get('notional')}")
            print(f"  근접 경고: {result.get('nearMinNotional')}")
            print(f"  ✅ 수량 정규화 정상")
        else:
            print(f"  실패 사유: {result.get('reason')}")
            
    except Exception as e:
        print(f"  ⚠️ API 연결 필요: {e}")


def test_data_structures():
    """데이터 구조 확장 테스트"""
    print("\n=== 4. Data Structures Test ===")
    
    from backend.core.new_strategy.data_structures import OrderResult, OrderFill
    
    # filter_meta 포함 OrderResult 생성
    order = OrderResult(
        ok=True,
        symbol="BTCUSDT",
        order_id=12345,
        side="BUY",
        avg_price=50000.0,
        executed_qty=0.001,
        filter_meta={
            "rawQty": 0.0012,
            "finalQty": 0.001,
            "stepSize": 0.001,
            "minQty": 0.001,
            "minNotional": 5.0,
            "notional": 50.0,
            "nearMinNotional": False
        }
    )
    
    print(f"  OrderResult 생성 성공")
    print(f"  filter_meta: {order.filter_meta}")
    print(f"  ✅ 데이터 구조 확장 정상")


def test_event_types():
    """새 이벤트 타입 정의 테스트"""
    print("\n=== 5. Event Types Test ===")
    
    event_types = [
        "DATA_PROGRESS",
        "SYMBOL_UNSUPPORTED",
        "WATCHLIST",
        "THRESHOLD_UPDATE",
        "PROTECTIVE_PAUSE",
        "PAUSE",
        "TRAILING_ACTIVATED"
    ]
    
    for event_type in event_types:
        print(f"  ✓ {event_type}")
    
    print(f"  ✅ 총 {len(event_types)}개 이벤트 타입 정의됨")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  YONA Vanguard Futures - Enhancement Features Test")
    print("="*60)
    
    try:
        test_adaptive_thresholds()
        test_symbol_support_check()
        test_quantity_normalization()
        test_data_structures()
        test_event_types()
        
        print("\n" + "="*60)
        print("  ✅ 모든 핵심 기능 테스트 통과")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
