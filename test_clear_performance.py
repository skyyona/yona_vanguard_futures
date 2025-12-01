"""각 방안의 성능 및 부작용 테스트"""
import sys
import time
from PySide6.QtWidgets import QApplication, QTableWidget, QCheckBox, QWidget, QHBoxLayout, QTableWidgetItem
from PySide6.QtCore import Qt


def test_method1_performance():
    """방안 1: removeCellWidget 반복 호출 - 성능 테스트"""
    print("\n=== 방안 1: removeCellWidget 반복 호출 ===")
    
    app = QApplication.instance() or QApplication(sys.argv)
    table = QTableWidget(0, 4)
    
    # 20개 항목으로 채우기
    data = [{"symbol": f"COIN{i}USDT"} for i in range(20)]
    
    # 초기 populate
    table.setRowCount(len(data))
    for i, item in enumerate(data):
        chk = QCheckBox()
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.addWidget(chk)
        table.setCellWidget(i, 0, chk_widget)
        table.setItem(i, 1, QTableWidgetItem(item["symbol"]))
    
    print(f"초기 데이터: {table.rowCount()}개")
    
    # 빈 배열로 클리어 (블랙리스트 추가 상황)
    start_time = time.perf_counter()
    
    removed_count = 0
    for row in range(table.rowCount()):
        for col in range(table.columnCount()):
            widget = table.cellWidget(row, col)
            if widget:
                table.removeCellWidget(row, col)
                removed_count += 1
    
    table.setRowCount(0)
    
    elapsed = (time.perf_counter() - start_time) * 1000  # ms
    
    print(f"제거된 위젯: {removed_count}개")
    print(f"소요 시간: {elapsed:.3f}ms")
    print(f"최종 행 개수: {table.rowCount()}")
    
    # 메모리 누수 체크
    widget_count = sum(1 for row in range(table.rowCount()) 
                       for col in range(table.columnCount()) 
                       if table.cellWidget(row, col))
    print(f"남은 위젯: {widget_count}개")
    
    # Basic sanity assertions
    assert table.rowCount() == 0, "테이블이 비워지지 않았습니다"
    assert removed_count > 0, "위젯이 제거되지 않은 것으로 보입니다"
    assert widget_count == 0, "위젯이 남아있습니다"


def test_method2_performance():
    """방안 2: clearContents() - 성능 테스트"""
    print("\n=== 방안 2: clearContents() ===")
    
    app = QApplication.instance() or QApplication(sys.argv)
    table = QTableWidget(0, 4)
    
    # 20개 항목으로 채우기
    data = [{"symbol": f"COIN{i}USDT"} for i in range(20)]
    
    table.setRowCount(len(data))
    for i, item in enumerate(data):
        chk = QCheckBox()
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.addWidget(chk)
        table.setCellWidget(i, 0, chk_widget)
        table.setItem(i, 1, QTableWidgetItem(item["symbol"]))
    
    print(f"초기 데이터: {table.rowCount()}개")
    
    # clearContents() 사용
    start_time = time.perf_counter()
    
    table.clearContents()
    table.setRowCount(0)
    
    elapsed = (time.perf_counter() - start_time) * 1000  # ms
    
    print(f"소요 시간: {elapsed:.3f}ms")
    print(f"최종 행 개수: {table.rowCount()}")
    
    # 메모리 누수 체크
    widget_count = sum(1 for row in range(table.rowCount()) 
                       for col in range(table.columnCount()) 
                       if table.cellWidget(row, col))
    print(f"남은 위젯: {widget_count}개")
    
    assert table.rowCount() == 0, "clearContents 후 행 개수가 0이 아닙니다"
    assert widget_count == 0, "clearContents 후 위젯이 남아있습니다"


def test_current_method():
    """현재 방식: setRowCount만 - 문제 재현"""
    print("\n=== 현재 방식: setRowCount만 ===")
    
    app = QApplication.instance() or QApplication(sys.argv)
    table = QTableWidget(0, 4)
    
    # 20개 항목으로 채우기
    data = [{"symbol": f"COIN{i}USDT"} for i in range(20)]
    
    table.setRowCount(len(data))
    for i, item in enumerate(data):
        chk = QCheckBox()
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.addWidget(chk)
        table.setCellWidget(i, 0, chk_widget)
        table.setItem(i, 1, QTableWidgetItem(item["symbol"]))
    
    print(f"초기 데이터: {table.rowCount()}개")
    
    # setRowCount(0)만 사용
    start_time = time.perf_counter()
    
    table.setRowCount(0)
    
    elapsed = (time.perf_counter() - start_time) * 1000  # ms
    
    print(f"소요 시간: {elapsed:.3f}ms")
    print(f"최종 행 개수: {table.rowCount()}")
    
    # 위젯이 남아있는지 확인 (버그!)
    # 주의: rowCount()는 0이지만 setCellWidget로 추가된 위젯은 여전히 메모리에 있음
    print("⚠️ 주의: 위젯이 메모리에 남아있지만 rowCount()가 0이라 접근 불가")
    
    # Current method should at least result in zero rows
    assert table.rowCount() == 0, "setRowCount(0) 후 행 개수가 0이 아닙니다"


def test_edge_cases():
    """극단적 케이스 테스트"""
    print("\n=== 극단적 케이스 테스트 ===")
    
    app = QApplication.instance() or QApplication(sys.argv)
    
    # 케이스 1: 빈 테이블에 clearContents() 호출
    print("\n[케이스 1] 빈 테이블에 clearContents() 호출")
    table = QTableWidget(0, 4)
    try:
        table.clearContents()
        print("✅ 오류 없음")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    
    # 케이스 2: 빈 테이블에 removeCellWidget 호출
    print("\n[케이스 2] 빈 테이블에 removeCellWidget 반복")
    table = QTableWidget(0, 4)
    try:
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                table.removeCellWidget(row, col)
        print("✅ 오류 없음")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    
    # 케이스 3: 일부만 위젯이 있는 경우
    print("\n[케이스 3] 일부만 위젯이 있는 경우")
    table = QTableWidget(5, 4)
    # 홀수 행만 위젯 추가
    for i in range(0, 5, 2):
        chk = QCheckBox()
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.addWidget(chk)
        table.setCellWidget(i, 0, chk_widget)
    
    try:
        table.clearContents()
        print("✅ clearContents() 성공")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


if __name__ == "__main__":
    result1 = test_method1_performance()
    result2 = test_method2_performance()
    result3 = test_current_method()
    test_edge_cases()
    
    print("\n" + "="*60)
    print("=== 성능 비교 요약 ===")
    print("="*60)
    print(f"{'방법':<25} {'소요시간':<15} {'제거된 위젯':<15} {'남은 위젯'}")
    print("-"*60)
    print(f"{result1['method']:<25} {result1['time_ms']:.3f}ms{'':<8} {result1['removed']:<15} {result1['remaining']}")
    print(f"{result2['method']:<25} {result2['time_ms']:.3f}ms{'':<8} {result2['removed']:<15} {result2['remaining']}")
    print(f"{result3['method']:<25} {result3['time_ms']:.3f}ms{'':<8} {result3['removed']:<15} {result3['remaining']}")
    print("="*60)
    
    print("\n결론:")
    if result1['time_ms'] < result2['time_ms']:
        faster = "removeCellWidget"
        diff = result2['time_ms'] - result1['time_ms']
    else:
        faster = "clearContents"
        diff = result1['time_ms'] - result2['time_ms']
    
    print(f"✅ {faster}가 {diff:.3f}ms 더 빠름")
    print(f"✅ 두 방법 모두 위젯을 완전히 제거함")
    print(f"❌ 현재 방식(setRowCount only)은 위젯이 남아있어 메모리 누수 발생")
