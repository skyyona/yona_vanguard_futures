"""애플리케이션 스타일시트"""

APP_QSS = """
/* 전역 스타일 */
QWidget {
    font-family: "Segoe UI", "맑은 고딕", sans-serif;
    font-size: 11px;
}

/* 탭 위젯 */
QTabWidget::pane {
    border: 1px solid #cccccc;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #e0e0e0;
    color: #333333;
    padding: 8px 16px;
    border: 1px solid #cccccc;
    border-bottom: none;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #000000;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #f0f0f0;
}

/* 테이블 */
QTableWidget {
    gridline-color: #e0e0e0;
    background-color: #ffffff;
    alternate-background-color: #f8f8f8;
    selection-background-color: #2196F3;
    selection-color: white;
}

QTableWidget::item {
    padding: 4px;
}

QHeaderView::section {
    background-color: #f5f5f5;
    color: #333333;
    font-weight: bold;
    border: 1px solid #e0e0e0;
    padding: 6px;
}

/* 버튼 */
QPushButton {
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
}

QPushButton:hover {
    opacity: 0.9;
}

QPushButton:pressed {
    opacity: 0.8;
}

/* 스크롤바 */
QScrollBar:vertical {
    border: none;
    background-color: #f0f0f0;
    width: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #c0c0c0;
    min-height: 20px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background-color: #a0a0a0;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background-color: #f0f0f0;
    height: 12px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #c0c0c0;
    min-width: 20px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #a0a0a0;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* 스플리터 */
QSplitter::handle {
    background-color: #e0e0e0;
}

QSplitter::handle:hover {
    background-color: #2196F3;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}
"""
