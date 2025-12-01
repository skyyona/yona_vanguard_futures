"""GUI 차트 업데이트 전체 테스트"""
import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from gui.main import YONAMainWindow


def test_full_chart_update():
    """전체 시나리오 테스트: 클릭 → API → Signal → UI 업데이트"""
    app = QApplication(sys.argv)
    window = YONAMainWindow()
    window.show()
    
    test_results = {
        "signal_count": 0,
        "data_received": False,
        "chart_updated": False
    }
    
    def on_analysis_ready(data):
        """analysis_ready Signal 수신"""
        test_results["signal_count"] += 1
        test_results["data_received"] = True
        print(f"\n✅ analysis_ready Signal 수신! (#{test_results['signal_count']})")
        print(f"   - symbol: {data.get('symbol')}")
        print(f"   - score: {data.get('score')}")
        print(f"   - close prices: {len(data.get('series', {}).get('close', []))} 개")
        print(f"   - trend: {data.get('trend_analysis', {}).get('overall')}")
        
        # 차트가 업데이트되었는지 확인
        if len(data.get('series', {}).get('close', [])) > 0:
            test_results["chart_updated"] = True
    
    # Signal 연결
    window.analysis_ready.connect(on_analysis_ready)
    
    def run_test():
        print("\n" + "="*60)
        print("🧪 GUI 전체 시나리오 테스트")
        print("="*60)
        
        # Step 1: 더미 데이터 추가
        dummy_data = [
            {
                "symbol": "BTCUSDT",
                "change_percent": 5.5,
                "cumulative_percent": 12.3,
                "energy_type": "급등",
                "days_since_listing": 999,
                "listing_signal_status": "NORMAL"
            }
        ]
        
        print(f"\n📊 Step 1: 테이블에 데이터 추가 ({len(dummy_data)}개)")
        window.ranking_table.populate(dummy_data)
        print("   ✅ 완료")
        
        # Step 2: 셀 클릭 시뮬레이션
        print(f"\n🖱️  Step 2: 상승률% 컬럼 클릭 (BTCUSDT)")
        window.ranking_table._on_cell_clicked(0, 3)
        print("   ✅ 클릭 이벤트 발생")
        
        # Step 3: 결과 대기
        def check_results():
            print(f"\n📋 Step 3: 결과 확인 (3초 대기 후)")
            print("-" * 60)
            
            if test_results["signal_count"] > 0:
                print(f"✅ Signal 수신: {test_results['signal_count']}회")
            else:
                print(f"❌ Signal 미수신")
            
            if test_results["data_received"]:
                print(f"✅ 분석 데이터 수신 완료")
            else:
                print(f"❌ 분석 데이터 미수신")
            
            if test_results["chart_updated"]:
                print(f"✅ 차트 데이터 업데이트 완료")
            else:
                print(f"❌ 차트 데이터가 비어있음")
            
            # 최종 판정
            print("\n" + "="*60)
            if all([test_results["signal_count"] > 0, 
                   test_results["data_received"], 
                   test_results["chart_updated"]]):
                print("🎉 **모든 테스트 통과!**")
                print("   실시간 랭킹리스트 클릭 → 차트 업데이트 정상 작동!")
            else:
                print("❌ **테스트 실패**")
                if test_results["signal_count"] == 0:
                    print("   - Signal이 발생하지 않음")
                if not test_results["data_received"]:
                    print("   - 분석 데이터를 받지 못함")
                if not test_results["chart_updated"]:
                    print("   - 차트 데이터가 비어있음 (API 오류?)")
            print("="*60)
            
            # 앱 종료
            QTimer.singleShot(1000, app.quit)
        
        # 3초 후 결과 확인
        QTimer.singleShot(3000, check_results)
    
    # 1초 후 테스트 시작
    QTimer.singleShot(1000, run_test)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    test_full_chart_update()
