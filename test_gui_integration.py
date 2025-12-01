"""
GUI + Backend 통합 테스트
- NewModular 엔진 GUI 표시 확인
- API 엔드포인트 동작 확인
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("=" * 80)
print("GUI + Backend 통합 테스트")
print("=" * 80)

# 1. GUI 위젯 import 확인
print("\n[1/4] GUI 위젯 import 확인")
try:
    from gui.widgets.footer_engines_widget import MiddleSessionWidget
    print("✅ MiddleSessionWidget import 성공")
except Exception as e:
    print(f"❌ MiddleSessionWidget import 실패: {e}")
    sys.exit(1)

# 2. NewModular 위젯 생성 확인
print("\n[2/4] NewModular 위젯 생성 확인")
try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    widget = MiddleSessionWidget()
    
    # 4개 엔진 확인
    assert hasattr(widget, 'alpha_engine'), "Alpha 엔진 없음"
    assert hasattr(widget, 'beta_engine'), "Beta 엔진 없음"
    assert hasattr(widget, 'gamma_engine'), "Gamma 엔진 없음"
    assert hasattr(widget, 'newmodular_engine'), "NewModular 엔진 없음"
    
    print("✅ 4개 엔진 위젯 생성 확인:")
    print(f"   - Alpha: {widget.alpha_engine.engine_name}")
    print(f"   - Beta: {widget.beta_engine.engine_name}")
    print(f"   - Gamma: {widget.gamma_engine.engine_name}")
    print(f"   - NewModular: {widget.newmodular_engine.engine_name}")
    
except Exception as e:
    print(f"❌ 위젯 생성 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Backend API 라우트 확인
print("\n[3/4] Backend API 라우트 확인")
try:
    from backend.api.routes import router
    
    # 라우트 경로 추출
    routes = [route.path for route in router.routes]
    
    # NewModular 전용 라우트 확인
    new_routes = [r for r in routes if "/strategy/new/" in r]
    
    print(f"✅ NewModular 전용 API 라우트 {len(new_routes)}개 발견:")
    for route in new_routes:
        print(f"   - {route}")
    
    # 필수 라우트 확인
    assert "/strategy/new/start" in routes, "/strategy/new/start 라우트 없음"
    assert "/strategy/new/status" in routes, "/strategy/new/status 라우트 없음"
    assert "/strategy/new/stop" in routes, "/strategy/new/stop 라우트 없음"
    
    print("✅ 필수 라우트 모두 존재")
    
except Exception as e:
    print(f"❌ 라우트 확인 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. NewStrategyWrapper import 확인
print("\n[4/4] NewStrategyWrapper import 확인")
try:
    from backend.core.strategies.new_strategy_wrapper import NewStrategyWrapper
    print("✅ NewStrategyWrapper import 성공")
    print(f"   - Engine Name: NewModular")
    print(f"   - BaseStrategy 상속: {hasattr(NewStrategyWrapper, 'start')}")
    print(f"   - Orchestrator 통합: {hasattr(NewStrategyWrapper, 'orchestrator')}")
    
except Exception as e:
    print(f"❌ NewStrategyWrapper import 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 80)
print("통합 테스트 완료 ✅")
print("=" * 80)
print("\n다음 단계:")
print("1. Backend 서버 실행: python backend/app_main.py")
print("2. GUI 실행: python gui/main.py")
print("3. NewModular 엔진 시작 버튼 클릭")
print("4. Backend 로그에서 Orchestrator 실행 확인")
print("5. GUI에서 NewModular 엔진 상태 확인")
