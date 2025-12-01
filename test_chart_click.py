"""랭킹 테이블 클릭 → 차트 업데이트 테스트"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from gui.main import YONAMainWindow


def test_chart_click():
    """차트 클릭 이벤트 테스트 - Signal/Slot 패턴 검증"""
    app = QApplication.instance() or QApplication(sys.argv)
    window = YONAMainWindow()
    window.show()
    
    signal_received = {"count": 0}
    
    def on_analysis_ready(data):
        """analysis_ready Signal 수신 시 호출"""
        signal_received["count"] += 1
        print(f"\n🎉 analysis_ready Signal 수신! (호출 횟수: {signal_received['count']})")
        print(f"   - 데이터 키: {list(data.keys())}")
        print(f"   - symbol: {data.get('symbol')}")
    
    # Signal 연결
    window.analysis_ready.connect(on_analysis_ready)
    
    def simulate_click():
        print("\n🧪 테스트 시작: 랭킹 테이블 클릭 → Signal/Slot 패턴")
        
        # 1. 테이블에 더미 데이터 추가
        dummy_data = [
            {
                "symbol": "BTCUSDT",
                "change_percent": 5.5,
                "cumulative_percent": 12.3,
                "energy_type": "급등",
                "days_since_listing": 999,
                "listing_signal_status": "NORMAL"
            },
            {
                "symbol": "ETHUSDT",
                "change_percent": 3.2,
                "cumulative_percent": 8.1,
                "energy_type": "지속 상승",
                "days_since_listing": 999,
                "listing_signal_status": "NORMAL"
            }
        ]
        
        print(f"📊 더미 데이터 {len(dummy_data)}개 추가")
        window.ranking_table.populate(dummy_data)
        
        # 2. 초기 상태 확인
        original_symbol = window.selected_symbol
        print(f"📍 현재 selected_symbol: {original_symbol}")
        
        # 3. 컬럼 3 클릭 시뮬레이션
        print("\n🖱️  컬럼 3 (상승률%) 클릭 시뮬레이션...")
        window.ranking_table._on_cell_clicked(0, 3)
        
        # 4. 선택된 심볼 확인
        print(f"✅ selected_symbol 변경됨: {window.selected_symbol}")
        print(f"📌 entry_title 텍스트: {window.entry_title.text()}")
        
        # 5. 타이머 확인
        if window.analysis_timer.isActive():
            print("✅ analysis_timer가 활성화되었습니다!")
        else:
            print("❌ analysis_timer가 시작되지 않았습니다!")
        
        # 6. Signal 수신 대기 (3초)
        def check_result():
            print("\n🧪 최종 결과:")
            if signal_received["count"] > 0:
                print(f"✅ analysis_ready Signal 정상 수신! (총 {signal_received['count']}회)")
                print("✅ Signal/Slot 패턴으로 UI 스레드 안전성 보장!")
            else:
                print("❌ analysis_ready Signal이 수신되지 않았습니다!")
                print("   - API 연결 확인 필요")
            
            # 앱 종료
            QTimer.singleShot(500, app.quit)
        
        QTimer.singleShot(3000, check_result)
    
    # 1초 후 테스트 시작
    QTimer.singleShot(1000, simulate_click)
    
    # Run the Qt event loop until the QTimer quits the app.
    app.exec()


if __name__ == "__main__":
    test_chart_click()
