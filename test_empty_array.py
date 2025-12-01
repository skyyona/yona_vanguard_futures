"""빈 배열 populate 테스트 - 블랙리스트 추가 후 SETTLING 테이블 비워지는지 확인"""
import sys
from PySide6.QtWidgets import QApplication
from gui.widgets.blacklist_widgets import SettlingTableWidget, BlacklistTableWidget


def test_empty_array_settling():
    """SETTLING 테이블 빈 배열 테스트"""
    print("\n=== SETTLING 테이블 빈 배열 테스트 ===")
    
    app = QApplication.instance() or QApplication(sys.argv)
    widget = SettlingTableWidget()
    
    # 1. 초기 데이터 (20개)
    initial_data = [{"symbol": f"COIN{i}USDT", "change_percent": i * 0.5, "status": "SETTLING"} 
                    for i in range(1, 21)]
    
    print("1. 초기 데이터 20개로 populate")
    widget.populate(initial_data)
    print(f"   행 개수: {widget.rowCount()}")
    
    # 위젯 개수 확인
    widget_count = sum(1 for row in range(widget.rowCount()) 
                       for col in range(widget.columnCount()) 
                       if widget.cellWidget(row, col))
    print(f"   실제 위젯 개수: {widget_count}")
    
    # 2. 일부 체크
    print("\n2. COIN1USDT, COIN5USDT, COIN10USDT 체크")
    for chk in widget._checkboxes:
        symbol = chk.property("symbol")
        if symbol in ["COIN1USDT", "COIN5USDT", "COIN10USDT"]:
            chk.setChecked(True)
    checked = widget.get_checked_symbols()
    print(f"   체크된 심볼: {checked}")
    
    # 3. 빈 배열로 클리어 (블랙리스트 추가 상황)
    print("\n3. 빈 배열로 populate (모든 SETTLING 코인이 블랙리스트에 추가된 상황)")
    widget.populate([])
    print(f"   행 개수: {widget.rowCount()}")
    
    # 위젯 개수 확인 (중요!)
    widget_count = sum(1 for row in range(widget.rowCount()) 
                       for col in range(widget.columnCount()) 
                       if widget.cellWidget(row, col))
    print(f"   실제 위젯 개수: {widget_count}")
    
    # 검증
    assert widget.rowCount() == 0, "❌ 행 개수가 0이 아닙니다!"
    assert widget_count == 0, "❌ 위젯이 남아있습니다! (메모리 누수)"
    assert len(widget._checkboxes) == 0, "❌ 체크박스 참조가 남아있습니다!"
    
    print("\n✅ SETTLING 테이블 빈 배열 테스트 통과!")
    return True


def test_empty_array_blacklist():
    """블랙리스트 테이블 빈 배열 테스트"""
    print("\n=== 블랙리스트 테이블 빈 배열 테스트 ===")
    
    app = QApplication.instance() or QApplication(sys.argv)
    widget = BlacklistTableWidget()
    
    # 1. 초기 데이터 (10개)
    initial_data = [
        {"symbol": f"COIN{i}USDT", "added_at_utc": f"2025-11-11 10:{i:02d}:00", "status": "SETTLING"} 
        for i in range(1, 11)
    ]
    
    print("1. 초기 데이터 10개로 populate")
    widget.populate(initial_data)
    print(f"   행 개수: {widget.rowCount()}")
    
    widget_count = sum(1 for row in range(widget.rowCount()) 
                       for col in range(widget.columnCount()) 
                       if widget.cellWidget(row, col))
    print(f"   실제 위젯 개수: {widget_count}")
    
    # 2. 일부 체크
    print("\n2. COIN3USDT, COIN7USDT 체크")
    for chk in widget._checkboxes:
        symbol = chk.property("symbol")
        if symbol in ["COIN3USDT", "COIN7USDT"]:
            chk.setChecked(True)
    checked = widget.get_checked_symbols()
    print(f"   체크된 심볼: {checked}")
    
    # 3. 빈 배열로 클리어 (모든 블랙리스트 제거 상황)
    print("\n3. 빈 배열로 populate (모든 블랙리스트 제거된 상황)")
    widget.populate([])
    print(f"   행 개수: {widget.rowCount()}")
    
    widget_count = sum(1 for row in range(widget.rowCount()) 
                       for col in range(widget.columnCount()) 
                       if widget.cellWidget(row, col))
    print(f"   실제 위젯 개수: {widget_count}")
    
    # 검증
    assert widget.rowCount() == 0, "❌ 행 개수가 0이 아닙니다!"
    assert widget_count == 0, "❌ 위젯이 남아있습니다! (메모리 누수)"
    assert len(widget._checkboxes) == 0, "❌ 체크박스 참조가 남아있습니다!"
    
    print("\n✅ 블랙리스트 테이블 빈 배열 테스트 통과!")
    return True


def test_multiple_updates():
    """여러 번 업데이트 테스트 (메모리 누수 확인)"""
    print("\n=== 여러 번 업데이트 테스트 (메모리 누수 확인) ===")
    
    app = QApplication.instance() or QApplication(sys.argv)
    widget = SettlingTableWidget()
    
    for cycle in range(5):
        print(f"\n[사이클 {cycle + 1}]")
        
        # 데이터 개수를 다르게
        data_count = (cycle % 3) * 10  # 0, 10, 20, 0, 10
        data = [{"symbol": f"TEST{i}USDT", "change_percent": i * 0.1, "status": "SETTLING"} 
                for i in range(data_count)]
        
        widget.populate(data)
        print(f"  데이터: {data_count}개, 행 개수: {widget.rowCount()}")
        
        widget_count = sum(1 for row in range(widget.rowCount()) 
                           for col in range(widget.columnCount()) 
                           if widget.cellWidget(row, col))
        print(f"  실제 위젯 개수: {widget_count}")
        
        # 검증
        assert widget.rowCount() == data_count, f"❌ 행 개수 불일치! 예상: {data_count}, 실제: {widget.rowCount()}"
        
        # 위젯 개수는 체크박스만 있는 컬럼 하나이므로 data_count와 같아야 함
        expected_widgets = data_count  # 체크박스 위젯만
        assert widget_count == expected_widgets, f"❌ 위젯 개수 불일치! 예상: {expected_widgets}, 실제: {widget_count}"
    
    print("\n✅ 여러 번 업데이트 테스트 통과! (메모리 누수 없음)")
    return True


if __name__ == "__main__":
    try:
        test_empty_array_settling()
        test_empty_array_blacklist()
        test_multiple_updates()
        
        print("\n" + "="*60)
        print("✅ 모든 테스트 통과!")
        print("="*60)
        print("\n주요 검증 항목:")
        print("1. ✅ 빈 배열 전달 시 테이블이 완전히 비워짐")
        print("2. ✅ 위젯이 메모리에서 완전히 제거됨 (메모리 누수 없음)")
        print("3. ✅ 체크박스 참조가 올바르게 정리됨")
        print("4. ✅ 여러 번 업데이트 시에도 메모리 누수 없음")
        print("\n이제 블랙리스트 추가 시 'Setting update' 창이 올바르게 비워집니다!")
        
    except AssertionError as e:
        print(f"\n❌ 테스트 실패: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
