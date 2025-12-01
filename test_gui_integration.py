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

# 2. 엔진 위젯 생성 확인 (Alpha/Beta/Gamma)
print("\n[2/4] 엔진 위젯 생성 확인 (Alpha/Beta/Gamma)")
try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    widget = MiddleSessionWidget()

    # 3개 엔진 확인
    assert hasattr(widget, 'alpha_engine'), "Alpha 엔진 없음"
    assert hasattr(widget, 'beta_engine'), "Beta 엔진 없음"
    assert hasattr(widget, 'gamma_engine'), "Gamma 엔진 없음"

    print("✅ 3개 엔진 위젯 생성 확인:")
    print(f"   - Alpha: {widget.alpha_engine.engine_name}")
    print(f"   - Beta: {widget.beta_engine.engine_name}")
    print(f"   - Gamma: {widget.gamma_engine.engine_name}")

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

    # 엔진 제어 전용 라우트 확인 (Alpha/Beta/Gamma)
    engine_routes = [r for r in routes if r.startswith("/engine/") or r == "/engine/status"]
    print(f"✅ Engine API 관련 라우트 {len(engine_routes)}개 발견:")
    for route in engine_routes:
        print(f"   - {route}")

    # 필수 라우트 확인
    assert "/engine/start" in routes, "/engine/start 라우트 없음"
    assert "/engine/stop" in routes, "/engine/stop 라우트 없음"
    assert "/engine/status" in routes, "/engine/status 라우트 없음"

    print("✅ 필수 엔진 제어 라우트 모두 존재")

except Exception as e:
    print(f"❌ 라우트 확인 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Alpha/Beta/Gamma 전략 클래스 import 확인
print("\n[4/4] Alpha/Beta/Gamma 전략 클래스 import 확인")
try:
    from backend.core.strategies import AlphaStrategy, BetaStrategy, GammaStrategy, BaseStrategy
    print("✅ Alpha/Beta/Gamma import 성공")
    print(f"   - Alpha is subclass of BaseStrategy: {issubclass(AlphaStrategy, BaseStrategy)}")
    print(f"   - Beta is subclass of BaseStrategy: {issubclass(BetaStrategy, BaseStrategy)}")
    print(f"   - Gamma is subclass of BaseStrategy: {issubclass(GammaStrategy, BaseStrategy)}")

except Exception as e:
    print(f"❌ 전략 클래스 import 실패: {e}")
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
