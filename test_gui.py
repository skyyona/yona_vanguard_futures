"""YONA Vanguard Futures (new) - GUI 테스트 실행 스크립트

이 스크립트는 백엔드 없이 GUI만 테스트할 수 있도록 합니다.
"""
import sys
import os

# 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from PySide6.QtWidgets import QApplication
from gui.main import YONAMainWindow

def main():
    """메인 함수"""
    print("=" * 60)
    print("YONA Vanguard Futures (new) - GUI 테스트")
    print("=" * 60)
    print()
    print("✅ GUI 구조:")
    print("  - 헤더: 앱 타이틀, 계좌 정보, 글로벌 세션, START/STOP")
    print("  - 1열 (좌측 63%):")
    print("    - 탭1: 금일 최고 상승 예상 + 실시간 랭킹리스트")
    print("    - 탭2: SETTLING update + 블랙리스트")
    print("  - 2열 (우측 37%):")
    print("    - 추세 분석 (5분/15분봉)")
    print("    - 게이지 (0-100 점수)")
    print("    - 타이밍 분석 차트")
    print("  - 푸터: 상승에너지, 거래 실행, 리스크 관리")
    print()
    print("⚠️ 주의:")
    print("  - 백엔드 서버가 실행되지 않으면 WebSocket 연결 오류가 발생합니다.")
    print("  - 백엔드 API가 없으면 실시간 데이터가 표시되지 않습니다.")
    print("  - 이는 정상적인 동작이며, GUI 레이아웃만 확인할 수 있습니다.")
    print()
    print("시작하려면 아무 키나 누르세요...")
    input()
    
    app = QApplication(sys.argv)
    
    # 스타일시트 적용 (선택사항)
    try:
        from gui.styles.qss import APP_QSS
        app.setStyleSheet(APP_QSS)
    except Exception as e:
        print(f"스타일시트 로딩 실패 (선택사항): {e}")
    
    window = YONAMainWindow()
    window.show()
    
    print()
    print("✅ GUI 윈도우가 열렸습니다!")
    print("   - 레이아웃 확인: 2열 구조 (탭 위젯 + 포지션 분석)")
    print("   - 탭 전환: '금일 최고 && 실시간 랭킹', 'SETTLING update && BLACK list'")
    print("   - 백엔드 연결: WebSocket 및 REST API 연결 시도 중...")
    print()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
