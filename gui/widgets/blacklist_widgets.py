"""블랙리스트 및 SETTLING 테이블 위젯"""
from typing import List, Dict, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHBoxLayout, 
    QWidget, QCheckBox, QAbstractItemView, QHeaderView
)


class SettlingTableWidget(QTableWidget):
    """SETTLING update 테이블"""
    
    symbol_clicked = Signal(str)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(0, 4, parent)
        
        # 헤더
        self.setHorizontalHeaderLabels(["선택", "코인심볼", "상승률%", "거래상태"])
        
        # 컬럼 설정
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 테이블 설정
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setMaximumHeight(200)
        
        # 체크박스 참조
        self._checkboxes: List[QCheckBox] = []
        
        # 셀 클릭 이벤트
        self.cellClicked.connect(self._on_cell_clicked)
    
    def populate(self, items: List[Dict[str, Any]]):
        """SETTLING 데이터로 테이블 채우기 (체크박스 상태 보존 + 위젯 완전 제거)"""
        # 기존 체크 상태 저장 (업데이트 전 상태 보존)
        checked_symbols = set(self.get_checked_symbols())
        
        # 기존 모든 셀 위젯 명시적으로 제거 (메모리 누수 방지)
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                widget = self.cellWidget(row, col)
                if widget:
                    self.removeCellWidget(row, col)
        
        self.setRowCount(len(items))
        self._checkboxes.clear()
        
        for i, item in enumerate(items):
            # 체크박스 (컬럼 0)
            chk = QCheckBox()
            symbol = item.get("symbol", "")
            chk.setProperty("symbol", symbol)
            
            # 이전에 체크되어 있었던 심볼이면 체크 상태 복원
            if symbol in checked_symbols:
                chk.setChecked(True)
            
            self._checkboxes.append(chk)
            
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.setCellWidget(i, 0, chk_widget)
            
            # 코인심볼 (컬럼 1)
            symbol_item = QTableWidgetItem(symbol)
            symbol_item.setTextAlignment(Qt.AlignCenter)
            symbol_item.setData(Qt.UserRole, f"https://www.binance.com/en/futures/{symbol}")
            self.setItem(i, 1, symbol_item)
            
            # 상승률% (컬럼 2)
            change_percent = item.get("change_percent", 0.0)
            change_item = QTableWidgetItem(f"{change_percent:+.1f}%")
            change_item.setTextAlignment(Qt.AlignCenter)
            if change_percent > 0:
                change_item.setForeground(QColor("#4caf50"))
            elif change_percent < 0:
                change_item.setForeground(QColor("#f44336"))
            self.setItem(i, 2, change_item)
            
            # 거래상태 (컬럼 3)
            status_item = QTableWidgetItem("SETTLING")
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setForeground(QColor("#ff9800"))
            self.setItem(i, 3, status_item)
    
    def _on_cell_clicked(self, row: int, col: int):
        """셀 클릭 처리"""
        if col == 1:  # 심볼 컬럼
            item = self.item(row, col)
            if item:
                url = item.data(Qt.UserRole)
                if url:
                    import webbrowser
                    webbrowser.open(url)
    
    def get_checked_symbols(self) -> List[str]:
        """체크된 심볼들 반환"""
        symbols = []
        for chk in self._checkboxes:
            if chk.isChecked():
                symbol = chk.property("symbol")
                if symbol:
                    symbols.append(str(symbol))
        return symbols
    
    def clear_all_checks(self):
        """모든 체크박스 해제"""
        for chk in self._checkboxes:
            chk.setChecked(False)


class BlacklistTableWidget(QTableWidget):
    """블랙리스트 테이블"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(0, 4, parent)
        
        # 헤더
        self.setHorizontalHeaderLabels(["선택", "추가일시(UTC)", "거래상태", "심볼"])
        
        # 컬럼 설정
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # 테이블 설정
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # 체크박스 참조
        self._checkboxes: List[QCheckBox] = []
    
    def populate(self, items: List[Dict[str, Any]]):
        """블랙리스트 데이터로 테이블 채우기 (체크박스 상태 보존 + 위젯 완전 제거)"""
        # 기존 체크 상태 저장 (업데이트 전 상태 보존)
        checked_symbols = set(self.get_checked_symbols())
        
        # 기존 모든 셀 위젯 명시적으로 제거 (메모리 누수 방지)
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                widget = self.cellWidget(row, col)
                if widget:
                    self.removeCellWidget(row, col)
        
        self.setRowCount(len(items))
        self._checkboxes.clear()
        
        for i, item in enumerate(items):
            # 체크박스 (컬럼 0)
            chk = QCheckBox()
            symbol = item.get("symbol", "")
            chk.setProperty("symbol", symbol)
            
            # 이전에 체크되어 있었던 심볼이면 체크 상태 복원
            if symbol in checked_symbols:
                chk.setChecked(True)
            
            self._checkboxes.append(chk)
            
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.setCellWidget(i, 0, chk_widget)
            
            # 추가일시 (컬럼 1)
            date_item = QTableWidgetItem(item.get("added_at_utc", ""))
            date_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(i, 1, date_item)
            
            # 거래상태 (컬럼 2)
            status = item.get("status", "MANUAL")
            status_item = QTableWidgetItem(status)
            status_item.setTextAlignment(Qt.AlignCenter)
            if status == "SETTLING":
                status_item.setForeground(QColor("#ff9800"))
            else:
                status_item.setForeground(QColor("#666"))
            self.setItem(i, 2, status_item)
            
            # 심볼 (컬럼 3)
            symbol_item = QTableWidgetItem(symbol)
            symbol_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(i, 3, symbol_item)
    
    def get_checked_symbols(self) -> List[str]:
        """체크된 심볼들 반환"""
        symbols = []
        for chk in self._checkboxes:
            if chk.isChecked():
                symbol = chk.property("symbol")
                if symbol:
                    symbols.append(str(symbol))
        return symbols
    
    def clear_all_checks(self):
        """모든 체크박스 해제"""
        for chk in self._checkboxes:
            chk.setChecked(False)
