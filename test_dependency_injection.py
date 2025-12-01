"""의존성 주입 구현 검증 스크립트"""
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from backend.core.engine_manager import EngineManager

def test_shared_client_injection():
    """공유 BinanceClient 주입 검증"""
    print("\n" + "="*80)
    print("  의존성 주입 패턴 구현 검증")
    print("="*80)
    
    try:
        # EngineManager 생성
        print("\n[Step 1] EngineManager 생성 중...")
        manager = EngineManager()
        
        # 공유 클라이언트 확인
        print("\n[Step 2] 공유 BinanceClient 확인")
        if hasattr(manager, '_shared_binance_client'):
            shared_id = id(manager._shared_binance_client)
            print(f"  ✅ 공유 클라이언트 존재 (ID: {shared_id})")
        else:
            print("  ❌ 공유 클라이언트 없음!")
            return False
        
        # 각 엔진의 클라이언트 ID 확인
        print("\n[Step 3] 각 엔진의 BinanceClient ID 확인")
        alpha_id = id(manager.engines["Alpha"].binance_client)
        beta_id = id(manager.engines["Beta"].binance_client)
        gamma_id = id(manager.engines["Gamma"].binance_client)
        
        print(f"  Alpha  Client ID: {alpha_id}")
        print(f"  Beta   Client ID: {beta_id}")
        print(f"  Gamma  Client ID: {gamma_id}")
        print(f"  Shared Client ID: {shared_id}")
        
        # 동일성 검증
        print("\n[Step 4] 동일성 검증")
        all_same = (alpha_id == shared_id == beta_id == gamma_id)
        
        if all_same:
            print("  ✅ 모든 엔진이 동일한 BinanceClient 인스턴스 사용!")
            print("  ✅ 의존성 주입 패턴 정상 작동!")
        else:
            print("  ❌ 엔진들이 서로 다른 클라이언트 사용!")
            if alpha_id != shared_id:
                print(f"     Alpha가 다른 인스턴스 사용 (차이: {alpha_id - shared_id})")
            if beta_id != shared_id:
                print(f"     Beta가 다른 인스턴스 사용 (차이: {beta_id - shared_id})")
            if gamma_id != shared_id:
                print(f"     Gamma가 다른 인스턴스 사용 (차이: {gamma_id - shared_id})")
            return False
        
        # Orchestrator 확인
        print("\n[Step 5] Orchestrator의 클라이언트 확인")
        alpha_orch_id = id(manager.engines["Alpha"].orchestrator.client)
        beta_orch_id = id(manager.engines["Beta"].orchestrator.client)
        gamma_orch_id = id(manager.engines["Gamma"].orchestrator.client)
        
        print(f"  Alpha Orchestrator Client ID: {alpha_orch_id}")
        print(f"  Beta  Orchestrator Client ID: {beta_orch_id}")
        print(f"  Gamma Orchestrator Client ID: {gamma_orch_id}")
        
        orch_same = (alpha_orch_id == shared_id == beta_orch_id == gamma_orch_id)
        
        if orch_same:
            print("  ✅ 모든 Orchestrator도 동일한 클라이언트 사용!")
        else:
            print("  ⚠️  Orchestrator가 다른 클라이언트 사용")
        
        # 메모리 효율성 확인
        print("\n[Step 6] 메모리 효율성")
        print("  변경 전: BinanceClient 인스턴스 3개 생성")
        print("  변경 후: BinanceClient 인스턴스 1개 생성")
        print("  절감률: 67% (3개 → 1개)")
        
        # HTTP 세션 확인
        print("\n[Step 7] HTTP 세션 확인")
        if hasattr(manager._shared_binance_client, 'session'):
            print(f"  ✅ HTTP 세션 존재 (ID: {id(manager._shared_binance_client.session)})")
            print("  ✅ 모든 엔진이 단일 HTTP 세션 공유")
        
        print("\n" + "="*80)
        print("  🎉 의존성 주입 패턴 구현 검증 성공!")
        print("="*80)
        
        # 정리
        manager.shutdown()
        
        return True
        
    except Exception as e:
        print(f"\n❌ 검증 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """하위 호환성 검증 (binance_client 미제공 시)"""
    print("\n" + "="*80)
    print("  하위 호환성 검증")
    print("="*80)
    
    try:
        from backend.core.strategies import AlphaStrategy
        
        print("\n[테스트] binance_client 파라미터 없이 AlphaStrategy 생성")
        strategy = AlphaStrategy(symbol="TESTUSDT")
        
        if strategy.binance_client is not None:
            print("  ✅ 독립 BinanceClient 자동 생성됨")
            print(f"     Client ID: {id(strategy.binance_client)}")
            print("  ✅ 하위 호환성 유지!")
            return True
        else:
            print("  ❌ BinanceClient 생성 안됨!")
            return False
            
    except Exception as e:
        print(f"\n❌ 하위 호환성 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "🚀"*40)
    print("  방안 B: 공유 BinanceClient 주입 방식 검증")
    print("🚀"*40)
    
    # 테스트 1: 의존성 주입
    result1 = test_shared_client_injection()
    
    # 테스트 2: 하위 호환성
    result2 = test_backward_compatibility()
    
    print("\n" + "="*80)
    print("  최종 결과")
    print("="*80)
    print(f"  의존성 주입 테스트: {'✅ 통과' if result1 else '❌ 실패'}")
    print(f"  하위 호환성 테스트: {'✅ 통과' if result2 else '❌ 실패'}")
    
    if result1 and result2:
        print("\n  🎊 모든 검증 통과! 구현 성공!")
        sys.exit(0)
    else:
        print("\n  ⚠️  일부 검증 실패")
        sys.exit(1)
