"""체크박스 상태 보존 기능 테스트"""
import sys
from PySide6.QtWidgets import QApplication
from gui.widgets.blacklist_widgets import SettlingTableWidget, BlacklistTableWidget


def test_settling_widget():
    """SettlingTableWidget 체크박스 상태 보존 테스트"""
    print("\n=== SettlingTableWidget 테스트 ===")
    
    app = QApplication.instance() or QApplication(sys.argv)
    widget = SettlingTableWidget()
    
    # 초기 데이터
    initial_data = [
        {"symbol": "BTCUSDT", "change_percent": 5.5, "status": "SETTLING"},
        {"symbol": "ETHUSDT", "change_percent": -3.2, "status": "SETTLING"},
        {"symbol": "BNBUSDT", "change_percent": 2.1, "status": "SETTLING"},
    ]
    
    print("1. 초기 데이터로 populate")
    widget.populate(initial_data)
    print(f"   행 개수: {widget.rowCount()}")
    print(f"   체크된 심볼: {widget.get_checked_symbols()}")
    
    # 체크박스 체크
    print("\n2. BTCUSDT와 BNBUSDT 체크")
    for chk in widget._checkboxes:
        symbol = chk.property("symbol")
        if symbol in ["BTCUSDT", "BNBUSDT"]:
            chk.setChecked(True)
    print(f"   체크된 심볼: {widget.get_checked_symbols()}")
    
    # 데이터 업데이트 (블랙리스트에서 ETHUSDT 제거됨)
    updated_data = [
        {"symbol": "BTCUSDT", "change_percent": 6.0, "status": "SETTLING"},
        {"symbol": "BNBUSDT", "change_percent": 2.5, "status": "SETTLING"},
        {"symbol": "XRPUSDT", "change_percent": 1.8, "status": "SETTLING"},  # 새로 추가
    ]
    
    print("\n3. 업데이트된 데이터로 populate (ETHUSDT 제거, XRPUSDT 추가)")
    widget.populate(updated_data)
    print(f"   행 개수: {widget.rowCount()}")
    print(f"   체크된 심볼: {widget.get_checked_symbols()}")
    
    # 검증
    checked = widget.get_checked_symbols()
    assert "BTCUSDT" in checked, "❌ BTCUSDT 체크 상태가 보존되지 않았습니다!"
    assert "BNBUSDT" in checked, "❌ BNBUSDT 체크 상태가 보존되지 않았습니다!"
    assert "XRPUSDT" not in checked, "❌ 새로 추가된 XRPUSDT는 체크되지 않아야 합니다!"
    
    print("\n✅ SettlingTableWidget 테스트 통과!")
    


def test_blacklist_widget():
    """BlacklistTableWidget 체크박스 상태 보존 테스트"""
    print("\n=== BlacklistTableWidget 테스트 ===")
    
    app = QApplication.instance() or QApplication(sys.argv)
    widget = BlacklistTableWidget()
    
    # 초기 데이터
    initial_data = [
        {"symbol": "BTCUSDT", "added_at_utc": "2025-11-11 10:00:00", "status": "MANUAL"},
        {"symbol": "ETHUSDT", "added_at_utc": "2025-11-11 10:05:00", "status": "SETTLING"},
        {"symbol": "BNBUSDT", "added_at_utc": "2025-11-11 10:10:00", "status": "MANUAL"},
    ]
    
    print("1. 초기 데이터로 populate")
    widget.populate(initial_data)
    print(f"   행 개수: {widget.rowCount()}")
    print(f"   체크된 심볼: {widget.get_checked_symbols()}")
    
    # 체크박스 체크
    print("\n2. ETHUSDT 체크")
    for chk in widget._checkboxes:
        symbol = chk.property("symbol")
        if symbol == "ETHUSDT":
            chk.setChecked(True)
    print(f"   체크된 심볼: {widget.get_checked_symbols()}")
    
    # 데이터 업데이트 (새 항목 추가)
    updated_data = [
        {"symbol": "BTCUSDT", "added_at_utc": "2025-11-11 10:00:00", "status": "MANUAL"},
        {"symbol": "ETHUSDT", "added_at_utc": "2025-11-11 10:05:00", "status": "SETTLING"},
        {"symbol": "BNBUSDT", "added_at_utc": "2025-11-11 10:10:00", "status": "MANUAL"},
        {"symbol": "XRPUSDT", "added_at_utc": "2025-11-11 10:15:00", "status": "SETTLING"},
    ]
    
    print("\n3. 업데이트된 데이터로 populate (XRPUSDT 추가)")
    widget.populate(updated_data)
    print(f"   행 개수: {widget.rowCount()}")
    print(f"   체크된 심볼: {widget.get_checked_symbols()}")
    
    # 검증
    checked = widget.get_checked_symbols()
    assert "ETHUSDT" in checked, "❌ ETHUSDT 체크 상태가 보존되지 않았습니다!"
    assert "XRPUSDT" not in checked, "❌ 새로 추가된 XRPUSDT는 체크되지 않아야 합니다!"
    
    print("\n✅ BlacklistTableWidget 테스트 통과!")
    


if __name__ == "__main__":
    try:
        test_settling_widget()
        test_blacklist_widget()
        print("\n" + "="*50)
        print("✅ 모든 테스트 통과! 체크박스 상태 보존 기능 정상 작동")
        print("="*50)
    except AssertionError as e:
        print(f"\n❌ 테스트 실패: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
