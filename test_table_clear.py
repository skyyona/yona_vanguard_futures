"""QTableWidget 셀 위젯 제거 방식 테스트"""
import sys
from PySide6.QtWidgets import QApplication, QTableWidget, QCheckBox, QWidget, QHBoxLayout, QTableWidgetItem, QVBoxLayout, QPushButton, QMainWindow
from PySide6.QtCore import Qt


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("테이블 클리어 방식 테스트")
        self.resize(800, 600)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # 3개의 테이블 생성
        self.table1 = self.create_test_table("방안 1: removeCellWidget 반복")
        self.table2 = self.create_test_table("방안 2: clearContents()")
        self.table3 = self.create_test_table("현재 방식: setRowCount만")
        
        layout.addWidget(self.table1)
        layout.addWidget(self.table2)
        layout.addWidget(self.table3)
        
        # 버튼들
        btn_populate = QPushButton("데이터 3개로 채우기")
        btn_populate.clicked.connect(self.populate_all)
        layout.addWidget(btn_populate)
        
        btn_clear = QPushButton("빈 배열로 클리어 (블랙리스트 추가 상황)")
        btn_clear.clicked.connect(self.clear_all)
        layout.addWidget(btn_clear)
        
        btn_check = QPushButton("메모리 상태 확인")
        btn_check.clicked.connect(self.check_memory)
        layout.addWidget(btn_check)
    
    def create_test_table(self, title):
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels([title, "심볼", "체크박스"])
        table.setMaximumHeight(150)
        table._test_widgets = []  # 위젯 참조 추적용
        return table
    
    def populate_all(self):
        print("\n=== 데이터 3개로 채우기 ===")
        data = [
            {"symbol": "BTCUSDT"},
            {"symbol": "ETHUSDT"},
            {"symbol": "BNBUSDT"}
        ]
        self.populate_method1(self.table1, data)
        self.populate_method2(self.table2, data)
        self.populate_current(self.table3, data)
    
    def clear_all(self):
        print("\n=== 빈 배열로 클리어 (블랙리스트 추가 상황 재현) ===")
        self.populate_method1(self.table1, [])
        self.populate_method2(self.table2, [])
        self.populate_current(self.table3, [])
    
    def populate_method1(self, table, items):
        """방안 1: removeCellWidget 반복 호출"""
        print(f"\n[방안 1] 시작 - 행 개수: {table.rowCount()}, 항목 개수: {len(items)}")
        
        # 기존 모든 셀 위젯 명시적으로 제거
        removed_count = 0
        for row in range(table.rowCount()):
            for col in range(table.columnCount()):
                widget = table.cellWidget(row, col)
                if widget:
                    table.removeCellWidget(row, col)
                    removed_count += 1
        
        print(f"[방안 1] 제거된 위젯: {removed_count}개")
        
        table.setRowCount(len(items))
        table._test_widgets.clear()
        
        for i, item in enumerate(items):
            # 인덱스 표시
            idx_item = QTableWidgetItem(str(i))
            table.setItem(i, 0, idx_item)
            
            # 심볼
            symbol_item = QTableWidgetItem(item["symbol"])
            table.setItem(i, 1, symbol_item)
            
            # 체크박스
            chk = QCheckBox()
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            table.setCellWidget(i, 2, chk_widget)
            table._test_widgets.append(chk_widget)
        
        print(f"[방안 1] 완료 - 행 개수: {table.rowCount()}, 위젯 개수: {len(table._test_widgets)}")
    
    def populate_method2(self, table, items):
        """방안 2: clearContents() 사용"""
        print(f"\n[방안 2] 시작 - 행 개수: {table.rowCount()}, 항목 개수: {len(items)}")
        
        table.clearContents()  # 모든 항목과 위젯 제거
        print(f"[방안 2] clearContents() 호출 완료")
        
        table.setRowCount(len(items))
        table._test_widgets.clear()
        
        for i, item in enumerate(items):
            idx_item = QTableWidgetItem(str(i))
            table.setItem(i, 0, idx_item)
            
            symbol_item = QTableWidgetItem(item["symbol"])
            table.setItem(i, 1, symbol_item)
            
            chk = QCheckBox()
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            table.setCellWidget(i, 2, chk_widget)
            table._test_widgets.append(chk_widget)
        
        print(f"[방안 2] 완료 - 행 개수: {table.rowCount()}, 위젯 개수: {len(table._test_widgets)}")
    
    def populate_current(self, table, items):
        """현재 방식: setRowCount만"""
        print(f"\n[현재 방식] 시작 - 행 개수: {table.rowCount()}, 항목 개수: {len(items)}")
        
        table.setRowCount(len(items))
        table._test_widgets.clear()
        
        for i, item in enumerate(items):
            idx_item = QTableWidgetItem(str(i))
            table.setItem(i, 0, idx_item)
            
            symbol_item = QTableWidgetItem(item["symbol"])
            table.setItem(i, 1, symbol_item)
            
            chk = QCheckBox()
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            table.setCellWidget(i, 2, chk_widget)
            table._test_widgets.append(chk_widget)
        
        print(f"[현재 방식] 완료 - 행 개수: {table.rowCount()}, 위젯 개수: {len(table._test_widgets)}")
    
    def check_memory(self):
        print("\n=== 메모리 상태 확인 ===")
        for i, table in enumerate([self.table1, self.table2, self.table3], 1):
            widget_count = 0
            for row in range(table.rowCount()):
                for col in range(table.columnCount()):
                    if table.cellWidget(row, col):
                        widget_count += 1
            
            print(f"테이블 {i}: 행={table.rowCount()}, "
                  f"실제 위젯={widget_count}, "
                  f"추적 위젯={len(table._test_widgets)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("\n테스트 시나리오:")
    print("1. [데이터 3개로 채우기] 클릭")
    print("2. [빈 배열로 클리어] 클릭 - 블랙리스트 추가 상황 재현")
    print("3. [메모리 상태 확인] 클릭 - 각 방안의 결과 비교")
    print("\n화면을 확인하세요:")
    print("- 방안 1: 테이블이 비워져야 함")
    print("- 방안 2: 테이블이 비워져야 함")
    print("- 현재 방식: 기존 위젯이 남아있음 (버그!)")
    
    sys.exit(app.exec())
