"""방안 B 구현 완전성 검증 스크립트"""
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

def check_code_implementation():
    """코드 레벨 구현 검증"""
    print("\n" + "="*80)
    print("  📋 코드 레벨 구현 완전성 검증")
    print("="*80)
    
    checks = []
    
    # 1. BaseStrategy 검증
    print("\n[1] BaseStrategy 검증")
    try:
        with open("backend/core/strategies/base_strategy.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        # binance_client 파라미터 확인
        if "def __init__(self, engine_name: str, binance_client: Optional[Any] = None):" in content:
            print("  ✅ __init__ 시그니처에 binance_client 파라미터 추가됨")
            checks.append(True)
        else:
            print("  ❌ __init__ 시그니처에 binance_client 파라미터 없음")
            checks.append(False)
            
        # 의존성 주입 로직 확인
        if "if binance_client is not None:" in content and "self.binance_client = binance_client" in content:
            print("  ✅ 의존성 주입 로직 구현됨")
            checks.append(True)
        else:
            print("  ❌ 의존성 주입 로직 누락")
            checks.append(False)
            
        # 하위 호환성 확인
        if "else:" in content and "BinanceClient()" in content:
            print("  ✅ 하위 호환성 로직 구현됨 (독립 생성)")
            checks.append(True)
        else:
            print("  ❌ 하위 호환성 로직 누락")
            checks.append(False)
            
        # 로깅 확인
        if "공유 BinanceClient 사용" in content and "독립 BinanceClient 생성" in content:
            print("  ✅ 주입 여부 로깅 구현됨")
            checks.append(True)
        else:
            print("  ❌ 로깅 누락")
            checks.append(False)
            
    except Exception as e:
        print(f"  ❌ 검증 실패: {e}")
        checks.extend([False] * 4)
    
    # 2. AlphaStrategy 검증
    print("\n[2] AlphaStrategy 검증")
    try:
        with open("backend/core/strategies/alpha_strategy.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        if "binance_client: Optional[Any] = None" in content:
            print("  ✅ __init__ 파라미터에 binance_client 추가됨")
            checks.append(True)
        else:
            print("  ❌ binance_client 파라미터 누락")
            checks.append(False)
            
        if 'super().__init__("Alpha", binance_client=binance_client)' in content:
            print("  ✅ 부모 클래스에 binance_client 전달")
            checks.append(True)
        else:
            print("  ❌ 부모 클래스 전달 누락")
            checks.append(False)
            
        if "BinanceClient 인스턴스 (선택적, EngineManager에서 주입)" in content:
            print("  ✅ 문서화 추가됨")
            checks.append(True)
        else:
            print("  ⚠️  문서화 권장")
            checks.append(True)  # 옵션이므로 통과
            
    except Exception as e:
        print(f"  ❌ 검증 실패: {e}")
        checks.extend([False] * 3)
    
    # 3. BetaStrategy 검증
    print("\n[3] BetaStrategy 검증")
    try:
        with open("backend/core/strategies/beta_strategy.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        if "binance_client: Optional[Any] = None" in content:
            print("  ✅ __init__ 파라미터에 binance_client 추가됨")
            checks.append(True)
        else:
            print("  ❌ binance_client 파라미터 누락")
            checks.append(False)
            
        if 'super().__init__("Beta", binance_client=binance_client)' in content:
            print("  ✅ 부모 클래스에 binance_client 전달")
            checks.append(True)
        else:
            print("  ❌ 부모 클래스 전달 누락")
            checks.append(False)
            
    except Exception as e:
        print(f"  ❌ 검증 실패: {e}")
        checks.extend([False] * 2)
    
    # 4. GammaStrategy 검증
    print("\n[4] GammaStrategy 검증")
    try:
        with open("backend/core/strategies/gamma_strategy.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        if "binance_client: Optional[Any] = None" in content:
            print("  ✅ __init__ 파라미터에 binance_client 추가됨")
            checks.append(True)
        else:
            print("  ❌ binance_client 파라미터 누락")
            checks.append(False)
            
        if 'super().__init__("Gamma", binance_client=binance_client)' in content:
            print("  ✅ 부모 클래스에 binance_client 전달")
            checks.append(True)
        else:
            print("  ❌ 부모 클래스 전달 누락")
            checks.append(False)
            
    except Exception as e:
        print(f"  ❌ 검증 실패: {e}")
        checks.extend([False] * 2)
    
    # 5. EngineManager 검증
    print("\n[5] EngineManager 검증")
    try:
        with open("backend/core/engine_manager.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        # 공유 클라이언트 생성 확인
        if "self._shared_binance_client = BinanceClient()" in content:
            print("  ✅ 공유 BinanceClient 생성 로직 구현됨")
            checks.append(True)
        else:
            print("  ❌ 공유 BinanceClient 생성 누락")
            checks.append(False)
            
        # Alpha 주입 확인
        if 'AlphaStrategy(\n                binance_client=self._shared_binance_client\n            )' in content or \
           'AlphaStrategy(binance_client=self._shared_binance_client)' in content:
            print("  ✅ Alpha에 공유 클라이언트 주입")
            checks.append(True)
        else:
            print("  ❌ Alpha 주입 누락")
            checks.append(False)
            
        # Beta 주입 확인
        if 'BetaStrategy(\n                binance_client=self._shared_binance_client\n            )' in content or \
           'BetaStrategy(binance_client=self._shared_binance_client)' in content:
            print("  ✅ Beta에 공유 클라이언트 주입")
            checks.append(True)
        else:
            print("  ❌ Beta 주입 누락")
            checks.append(False)
            
        # Gamma 주입 확인
        if 'GammaStrategy(\n                binance_client=self._shared_binance_client\n            )' in content or \
           'GammaStrategy(binance_client=self._shared_binance_client)' in content:
            print("  ✅ Gamma에 공유 클라이언트 주입")
            checks.append(True)
        else:
            print("  ❌ Gamma 주입 누락")
            checks.append(False)
            
        # shutdown 정리 확인
        if "self._shared_binance_client.session.close()" in content:
            print("  ✅ shutdown에서 세션 정리 구현됨")
            checks.append(True)
        else:
            print("  ❌ shutdown 정리 누락")
            checks.append(False)
            
        # 로깅 확인
        if "공유 BinanceClient 생성 완료" in content and "모든 엔진이 공유 BinanceClient 사용" in content:
            print("  ✅ 주입 확인 로깅 구현됨")
            checks.append(True)
        else:
            print("  ❌ 로깅 누락")
            checks.append(False)
            
    except Exception as e:
        print(f"  ❌ 검증 실패: {e}")
        checks.extend([False] * 6)
    
    return all(checks), checks

def check_runtime_behavior():
    """런타임 동작 검증"""
    print("\n" + "="*80)
    print("  🚀 런타임 동작 검증")
    print("="*80)
    
    try:
        from backend.core.engine_manager import EngineManager
        
        print("\n[테스트] EngineManager 생성 및 검증")
        manager = EngineManager()
        
        # 공유 클라이언트 존재 확인
        if not hasattr(manager, '_shared_binance_client'):
            print("  ❌ _shared_binance_client 속성 없음")
            return False
            
        shared_id = id(manager._shared_binance_client)
        print(f"  ✅ 공유 클라이언트 ID: {shared_id}")
        
        # 각 엔진 클라이언트 ID 확인
        alpha_id = id(manager.engines["Alpha"].binance_client)
        beta_id = id(manager.engines["Beta"].binance_client)
        gamma_id = id(manager.engines["Gamma"].binance_client)
        
        print(f"  Alpha  ID: {alpha_id}")
        print(f"  Beta   ID: {beta_id}")
        print(f"  Gamma  ID: {gamma_id}")
        
        # 동일성 검증
        if alpha_id == beta_id == gamma_id == shared_id:
            print("  ✅ 모든 엔진이 동일한 인스턴스 사용")
            
            # Orchestrator까지 확인
            alpha_orch_id = id(manager.engines["Alpha"].orchestrator.client)
            beta_orch_id = id(manager.engines["Beta"].orchestrator.client)
            gamma_orch_id = id(manager.engines["Gamma"].orchestrator.client)
            
            if alpha_orch_id == beta_orch_id == gamma_orch_id == shared_id:
                print("  ✅ Orchestrator도 동일한 인스턴스 사용")
                manager.shutdown()
                return True
            else:
                print("  ❌ Orchestrator가 다른 인스턴스 사용")
                manager.shutdown()
                return False
        else:
            print("  ❌ 엔진들이 다른 인스턴스 사용")
            manager.shutdown()
            return False
            
    except Exception as e:
        print(f"  ❌ 런타임 검증 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_backward_compatibility():
    """하위 호환성 검증"""
    print("\n" + "="*80)
    print("  🔄 하위 호환성 검증")
    print("="*80)
    
    try:
        from backend.core.strategies import AlphaStrategy
        
        print("\n[테스트] binance_client 미제공 시 자동 생성")
        strategy = AlphaStrategy(symbol="TESTUSDT")
        
        if strategy.binance_client is None:
            print("  ❌ BinanceClient가 None")
            return False
            
        print(f"  ✅ 독립 BinanceClient 생성됨 (ID: {id(strategy.binance_client)})")
        return True
        
    except Exception as e:
        print(f"  ❌ 하위 호환성 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "🔍"*40)
    print("  방안 B: 공유 BinanceClient 주입 방식 구현 완전성 검증")
    print("🔍"*40)
    
    # 코드 레벨 검증
    code_pass, code_checks = check_code_implementation()
    
    # 런타임 검증
    runtime_pass = check_runtime_behavior()
    
    # 하위 호환성 검증
    compat_pass = check_backward_compatibility()
    
    # 최종 결과
    print("\n" + "="*80)
    print("  📊 최종 검증 결과")
    print("="*80)
    print(f"\n  코드 구현 검증: {'✅ 통과' if code_pass else '❌ 실패'} ({sum(code_checks)}/{len(code_checks)} 항목)")
    print(f"  런타임 동작 검증: {'✅ 통과' if runtime_pass else '❌ 실패'}")
    print(f"  하위 호환성 검증: {'✅ 통과' if compat_pass else '❌ 실패'}")
    
    all_pass = code_pass and runtime_pass and compat_pass
    
    print("\n" + "="*80)
    if all_pass:
        print("  🎊 방안 B 구현 완전성 검증 성공!")
        print("  ✅ 모든 요구사항이 정확하게 구현되었습니다.")
    else:
        print("  ⚠️  일부 항목 미구현 또는 오류 발견")
    print("="*80)
    
    sys.exit(0 if all_pass else 1)
