"""하단 푸터 위젯 - 알파, 베타, 감마 3개 자동매매 엔진"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
    QFrame, QPushButton, QLineEdit, QSlider, QComboBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QFont, QIntValidator, QDoubleValidator, QColor
from typing import Optional, Dict, Any
from datetime import datetime


class TradingEngineWidget(QWidget):
    """자동매매 엔진 위젯 (알파/베타/감마)"""
    
    # 시그널
    start_signal = Signal(str)  # 엔진 시작 (엔진명)
    stop_signal = Signal(str)   # 엔진 정지 (엔진명)
    symbol_changed = Signal(str, str)  # 심볼 변경 (엔진명, 심볼)
    settings_changed = Signal(str, dict)  # 설정 변경 (엔진명, {funds, leverage})
    
    def __init__(self, engine_name: str, engine_color: str, parent=None):
        super().__init__(parent)
        self.engine_name = engine_name  # "Alpha", "Beta", "Gamma"
        self.engine_color = engine_color  # "#4CAF50", "#2196F3", "#FF9800"
        self.is_running = False
        self.selected_symbol = ""
        self.designated_funds = 0.0
        self.applied_leverage = 1
        self.account_total_balance = 0.0  # Account total balance (실시간 업데이트)
        
        # 메시지 저장소 (3개 구간)
        self._energy_messages = []
        self._trade_messages = []
        self._risk_messages = []
        self._max_messages = 10
        
        # 거래 기록 저장소
        self._trade_history = []
        self._max_history = 100
        
        self._init_ui()
    
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(5)
        
        # 엔진별 배경 색상 설정
        # 모든 엔진 배경/강조 색상 통일 (#263238)
        bg_color = "#263238"
        border_color = "#263238"

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 8px;
            }}
        """)
        
        # 탭 위젯 생성
        self.tab_widget = QTabWidget()
        # 탭바에 엔진명을 직접 표시하고, 텍스트 크기/굵기/색상을
        # 기존 상단 헤더의 엔진명 라벨과 동일한 톤으로 맞춘다.
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                background-color: {bg_color};
            }}
            QTabBar::tab {{
                background-color: #2a2a2a;
                color: {self.engine_color};
                padding: 6px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background-color: {bg_color};
                color: {self.engine_color};
            }}
            QTabBar::tab:hover {{
                background-color: #333333;
            }}
        """)

        # 탭1: 엔진별 메인 탭 (엔진명으로 표시)
        self.engine_tab = self._create_engine_tab()
        self.tab_widget.addTab(self.engine_tab, f"{self.engine_name} 엔진")

        # 탭2: Trade History
        self.history_tab = self._create_history_tab()
        self.tab_widget.addTab(self.history_tab, "Trade History")
        
        main_layout.addWidget(self.tab_widget)
    
    def _create_engine_tab(self):
        """엔진 실행 탭 생성"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # ========== 1. 상부 영역 - 설정 및 제어 ==========
        
        # Row 1: Selected Symbol, 설정 적용, Return Funds, 거래 활성화 토글 버튼
        row1_layout = QHBoxLayout()
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(8)
        
        # Selected Symbol 표시
        symbol_container = QWidget()
        symbol_layout = QHBoxLayout(symbol_container)
        symbol_layout.setContentsMargins(0, 0, 0, 0)
        symbol_layout.setSpacing(4)
        
        symbol_title = QLabel("Selected Symbol:")
        symbol_title.setStyleSheet("color: #888888; font-size: 9px;")
        symbol_layout.addWidget(symbol_title)
        
        self.symbol_label = QLabel("-")
        self.symbol_label.setStyleSheet("color: #ffffff; font-size: 10px; font-weight: bold;")
        symbol_layout.addWidget(self.symbol_label)
        
        row1_layout.addWidget(symbol_container)
        
        # 심볼 지정 버튼
        self.symbol_select_button = QPushButton("심볼 지정")
        self.apply_settings_button = QPushButton("설정 적용")
        self.apply_settings_button.setFixedSize(70, 24)
        self.apply_settings_button.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                font-weight: bold;
                font-size: 9px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
            QPushButton:pressed {
                background-color: #D84315;
            }
        """)
        self.apply_settings_button.clicked.connect(self._on_apply_settings)
        
        row1_layout.addStretch()
        
        # 오른쪽 버튼들: 설정 적용, Return Funds, 거래 활성화
        row1_layout.addWidget(self.apply_settings_button)
        
        # Return Funds 버튼
        self.return_funds_button = QPushButton("Return Funds")
        self.return_funds_button.setFixedSize(90, 28)
        self.return_funds_button.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                font-weight: bold;
                font-size: 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #78909C;
            }
            QPushButton:pressed {
                background-color: #546E7A;
            }
        """)
        self.return_funds_button.clicked.connect(self._on_return_funds)
        row1_layout.addWidget(self.return_funds_button)
        
        # 거래 활성화/정지 토글 버튼 (Return Funds 버튼 바로 옆)
        self.toggle_button = QPushButton("거래 활성화")  # 초기: 거래 정지 상태
        self.toggle_button.setFixedSize(90, 28)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #2EBD85;
                color: white;
                font-weight: bold;
                font-size: 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #26A069;
            }
            QPushButton:checked {
                background-color: #F6465D;
                color: white;
            }
            QPushButton:checked:hover {
                background-color: #E63946;
            }
        """)
        self.toggle_button.clicked.connect(self._on_toggle_clicked)
        row1_layout.addWidget(self.toggle_button)
        
        layout.addLayout(row1_layout)
        
        # Row 2: Designated Funds, Applied Leverage
        row2_layout = QHBoxLayout()
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(15)
        
        # Designated Funds
        funds_container = QWidget()
        funds_layout = QHBoxLayout(funds_container)
        funds_layout.setContentsMargins(0, 0, 0, 0)
        funds_layout.setSpacing(5)
        
        funds_label = QLabel("Designated Funds:")
        funds_label.setStyleSheet("color: #888888; font-size: 9px;")
        funds_layout.addWidget(funds_label)
        
        # 슬라이더로 변경 (10% ~ 100%, 단위: 10%)
        self.funds_slider = QSlider(Qt.Horizontal)
        self.funds_slider.setRange(10, 100)  # 10% ~ 100%
        self.funds_slider.setValue(30)  # 기본값 30%
        self.funds_slider.setSingleStep(10)
        self.funds_slider.setPageStep(10)
        self.funds_slider.setFixedWidth(100)
        self.funds_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #2a2a2a;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #66BB6A;
            }
        """)
        self.funds_slider.valueChanged.connect(self._on_funds_slider_changed)
        funds_layout.addWidget(self.funds_slider)
        
        # 슬라이더 값 표시 (퍼센트 + 금액)
        self.funds_value_label = QLabel("30% ($0)")
        self.funds_value_label.setStyleSheet("color: #4CAF50; font-size: 9px; font-weight: bold;")
        self.funds_value_label.setFixedWidth(80)
        funds_layout.addWidget(self.funds_value_label)
        
        row2_layout.addWidget(funds_container)
        
        # Applied Leverage
        leverage_container = QWidget()
        leverage_layout = QHBoxLayout(leverage_container)
        leverage_layout.setContentsMargins(0, 0, 0, 0)
        leverage_layout.setSpacing(5)
        
        leverage_label = QLabel("Applied Leverage:")
        leverage_label.setStyleSheet("color: #888888; font-size: 9px;")
        leverage_layout.addWidget(leverage_label)
        
        self.leverage_slider = QSlider(Qt.Horizontal)
        self.leverage_slider.setMinimum(1)
        self.leverage_slider.setMaximum(50)
        self.leverage_slider.setValue(1)
        self.leverage_slider.setFixedWidth(100)
        self.leverage_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #555555;
                height: 6px;
                background: #2a2a2a;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                border: 1px solid #4CAF50;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)
        self.leverage_slider.valueChanged.connect(self._on_leverage_changed)
        leverage_layout.addWidget(self.leverage_slider)
        
        self.leverage_value_label = QLabel("1x")
        self.leverage_value_label.setStyleSheet("color: #ffffff; font-size: 9px; font-weight: bold;")
        self.leverage_value_label.setFixedWidth(30)
        leverage_layout.addWidget(self.leverage_value_label)
        
        row2_layout.addWidget(leverage_container)
        row2_layout.addStretch()
        
        layout.addLayout(row2_layout)
        
        # 구분선
        line1 = QFrame()
        line1.setFrameShape(QFrame.Shape.HLine)
        line1.setFrameShadow(QFrame.Shadow.Sunken)
        line1.setStyleSheet("background-color: #444444;")
        line1.setMaximumHeight(1)
        layout.addWidget(line1)
        
        # ========== 2. 중단부 영역 - 3개 독립 메시지 구간 ==========
        
        # 상승에너지 강도 분석 구간
        energy_title = QLabel("상승에너지 강도 분석")
        energy_title.setStyleSheet("color: #aaaaaa; font-size: 9px; font-weight: bold;")
        layout.addWidget(energy_title)
        
        self.energy_text = QTextEdit()
        self.energy_text.setReadOnly(True)
        self.energy_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #ffffff;
                border-radius: 3px;
                font-family: 'Segoe UI', 'Malgun Gothic', 'Arial', sans-serif;
                font-size: 9px;
                padding: 3px;
            }
        """)
        self.energy_text.setFixedHeight(45)
        layout.addWidget(self.energy_text)
        
        # 거래 포지션 진입/익절 분석 구간
        trade_title = QLabel("거래 포지션 진입/익절 분석")
        trade_title.setStyleSheet("color: #aaaaaa; font-size: 9px; font-weight: bold;")
        layout.addWidget(trade_title)
        
        self.trade_text = QTextEdit()
        self.trade_text.setReadOnly(True)
        self.trade_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #ffffff;
                border-radius: 3px;
                font-family: 'Segoe UI', 'Malgun Gothic', 'Arial', sans-serif;
                font-size: 9px;
                padding: 3px;
            }
        """)
        self.trade_text.setFixedHeight(45)
        layout.addWidget(self.trade_text)
        
        # 거래 리스크 관리 구간
        risk_title = QLabel("거래 리스크 관리")
        risk_title.setStyleSheet("color: #aaaaaa; font-size: 9px; font-weight: bold;")
        layout.addWidget(risk_title)
        
        self.risk_text = QTextEdit()
        self.risk_text.setReadOnly(True)
        self.risk_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #ffffff;
                border-radius: 3px;
                font-family: 'Segoe UI', 'Malgun Gothic', 'Arial', sans-serif;
                font-size: 9px;
                padding: 3px;
            }
        """)
        self.risk_text.setFixedHeight(45)
        layout.addWidget(self.risk_text)
        
        # 구분선
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        line2.setStyleSheet("background-color: #444444;")
        line2.setMaximumHeight(1)
        layout.addWidget(line2)
        
        # ========== 3. 하부 영역 - 성과 요약 ==========
        
        summary_layout = QHBoxLayout()
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(10)
        
        # Total Slot Gain/Loss
        gain_loss_container = QWidget()
        gain_loss_layout = QHBoxLayout(gain_loss_container)
        gain_loss_layout.setContentsMargins(0, 0, 0, 0)
        gain_loss_layout.setSpacing(5)
        
        gain_loss_title = QLabel("Total Slot Gain/Loss:")
        gain_loss_title.setStyleSheet("color: #888888; font-size: 9px;")
        gain_loss_layout.addWidget(gain_loss_title)
        
        self.gain_loss_label = QLabel("0.000 USDT")
        self.gain_loss_label.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold;")
        gain_loss_layout.addWidget(self.gain_loss_label)
        
        summary_layout.addWidget(gain_loss_container)
        summary_layout.addStretch()
        
        # P&L %
        pnl_container = QWidget()
        pnl_layout = QHBoxLayout(pnl_container)
        pnl_layout.setContentsMargins(0, 0, 0, 0)
        pnl_layout.setSpacing(5)
        
        pnl_title = QLabel("P&L %:")
        pnl_title.setStyleSheet("color: #888888; font-size: 9px;")
        pnl_layout.addWidget(pnl_title)
        
        self.pnl_label = QLabel("0.00 %")
        self.pnl_label.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold;")
        pnl_layout.addWidget(self.pnl_label)
        
        summary_layout.addWidget(pnl_container)
        
        layout.addLayout(summary_layout)
        
        # 초기 메시지
        self._add_energy_message(f"{self.engine_name} 엔진 초기화 완료.")
        self._add_trade_message("거래 활성화 버튼을 눌러 시작하세요.")
        self._add_risk_message("리스크 관리 시스템 대기 중.")
        
        return tab_widget
    
    def _create_history_tab(self):
        """Trade History 탭 생성"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        
        # 거래 기록 테이블
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "거래 일시", "코인 심볼", "투입 자금", "레버리지", "수익/손실", "미실현 P&L %"
        ])
        
        # 테이블 스타일
        self.history_table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a1a;
                color: #cccccc;
                border: 1px solid #333333;
                gridline-color: #333333;
                font-size: 9px;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #aaaaaa;
                padding: 4px;
                border: 1px solid #333333;
                font-weight: bold;
                font-size: 9px;
            }
            QTableWidget::item {
                padding: 3px;
            }
            QTableWidget::item:selected {
                background-color: #3a3a3a;
            }
        """)
        
        # 테이블 설정
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.history_table.verticalHeader().setVisible(False)
        
        # 컬럼 너비 설정
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        self.history_table.setColumnWidth(0, 130)  # 거래 일시
        self.history_table.setColumnWidth(1, 80)   # 코인 심볼
        self.history_table.setColumnWidth(2, 100)  # 투입 자금
        self.history_table.setColumnWidth(3, 60)   # 레버리지
        self.history_table.setColumnWidth(4, 110)  # 수익/손실
        
        layout.addWidget(self.history_table)

        # 하단: 기록 삭제 버튼
        button_row = QHBoxLayout()
        button_row.addStretch()

        self.clear_history_button = QPushButton("기록 삭제")
        self.clear_history_button.setFixedSize(80, 24)
        self.clear_history_button.setStyleSheet(
            """
            QPushButton {
                background-color: #F44336;
                color: white;
                font-size: 9px;
                font-weight: bold;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #E53935;
            }
            QPushButton:pressed {
                background-color: #D32F2F;
            }
            """
        )
        self.clear_history_button.clicked.connect(self._on_clear_history_clicked)
        button_row.addWidget(self.clear_history_button)

        layout.addLayout(button_row)

        return tab_widget
    
    def _on_toggle_clicked(self):
        """거래 활성화 토글 버튼 클릭"""
        if self.toggle_button.isChecked():
            # 체크됨 = 거래 활성화 상태 (엔진 작동 중)
            
            # 심볼 미지정 경고 (Tier 3)
            if not self.selected_symbol:
                from PySide6.QtWidgets import QMessageBox
                reply = QMessageBox.warning(
                    self,
                    "심볼 미지정",
                    f"{self.engine_name} 엔진에 거래 심볼이 지정되지 않았습니다.\n\n"
                    f"기본값(BTCUSDT)으로 거래를 시작하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    self.toggle_button.setChecked(False)
                    return
            
            self.is_running = True
            self.toggle_button.setText("거래 정지")  # 작동 중이므로 '거래 정지' 표시
            # 실행 중에는 Return Funds 버튼 비활성화
            if hasattr(self, 'return_funds_button'):
                self.return_funds_button.setEnabled(False)
            symbol_msg = f" ({self.selected_symbol})" if self.selected_symbol else " (기본값: BTCUSDT)"
            self._add_trade_message(f"{self.engine_name} 엔진 시작...{symbol_msg}")
            self.start_signal.emit(self.engine_name)
        else:
            # 체크 해제 = 거래 정지 상태 (엔진 정지)
            self.is_running = False
            self.toggle_button.setText("거래 활성화")  # 정지 상태이므로 '거래 활성화' 표시
            # 정지 상태에서는 Return Funds 버튼 활성화
            if hasattr(self, 'return_funds_button'):
                self.return_funds_button.setEnabled(True)
            self._add_trade_message(f"{self.engine_name} 엔진 정지.")
            self.stop_signal.emit(self.engine_name)
    
    def set_symbol(self, symbol: str):
        """외부에서 심볼 배치 (메인 윈도우의 버튼에서 호출)"""
        print(f"[{self.engine_name}] 🔔 set_symbol() 호출됨 - 심볼: {symbol}")
        
        # 거래 중인지 확인
        if self.is_running:
            print(f"[{self.engine_name}] ❌ 거래 진행 중 - 심볼 변경 불가")
            self._add_energy_message(
                f"⚠️ 거래 진행 중입니다!\n"
                f"   현재 거래 중인 심볼: {self.selected_symbol}\n"
                f"   심볼을 변경하려면 [거래 활성화] 버튼을 다시 클릭하여\n"
                f"   거래를 종료하세요."
            )
            
            # 경고 다이얼로그 표시
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "거래 진행 중",
                f"{self.engine_name} 엔진이 거래 진행 중입니다.\n\n"
                f"현재 거래 심볼: {self.selected_symbol}\n\n"
                f"심볼을 변경하려면 [거래 활성화] 버튼을 다시 클릭하여\n"
                f"거래를 종료한 후 다시 시도하세요."
            )
            return
        
        # 이전 심볼과 다른 경우 성과 데이터 초기화
        if self.selected_symbol and self.selected_symbol != symbol:
            print(f"[{self.engine_name}] 심볼 변경: {self.selected_symbol} → {symbol}")
            
            # GUI 성과 초기화
            self._initialize_performance_after_apply(0.0)  # Total Slot Gain/Loss = 0
            self.applied_leverage = 0  # 레버리지 초기화 (설정 적용 시 다시 설정)
            
            self._add_energy_message(f"이전 심볼 ({self.selected_symbol}) 데이터 초기화됨")
        
        # 거래 중이 아닐 때만 심볼 변경 허용
        self.selected_symbol = symbol
        self.symbol_label.setText(symbol)
        
        message = f"✅ 배치된 심볼: {symbol}"
        self._add_energy_message(message)
        
        print(f"[{self.engine_name}] ✅ 심볼 설정 완료:")
        print(f"  - selected_symbol: {self.selected_symbol}")
        print(f"  - symbol_label.text(): {self.symbol_label.text()}")
    
    def _on_apply_settings(self):
        """설정 적용 버튼 - 바이낸스 API로 레버리지 설정"""
        if not self.selected_symbol:
            self._add_energy_message("❌ 먼저 코인을 배치하세요!")
            print(f"[{self.engine_name}] 설정 적용 실패: 심볼 미선택")
            return
        
        leverage = self.leverage_slider.value()
        
        # 슬라이더 값으로 자금 계산 (퍼센트 → 금액)
        funds_percent = self.funds_slider.value()
        funds_amount = (funds_percent / 100) * self.account_total_balance
        
        if funds_amount <= 0:
            self._add_energy_message("❌ 투입 자금이 0입니다!")
            print(f"[{self.engine_name}] 설정 적용 실패: 자금 0")
            return
        
        print(f"[{self.engine_name}] 설정 적용 시작: {self.selected_symbol}, {leverage}x, {funds_percent}% (${funds_amount:.2f})")
        
        try:
            # 1. 레버리지 설정
            from backend.api_client.binance_client import BinanceClient
            
            client = BinanceClient()
            result = client.set_leverage(self.selected_symbol, leverage)
            
            if "error" in result:
                error_msg = result.get("error", "Unknown error")
                self._add_risk_message(f"레버리지 설정 실패: {error_msg}")
                print(f"[{self.engine_name}] ❌ API 오류: {result}")
                return
            
            actual_leverage = result.get("leverage", leverage)
            max_notional = result.get("maxNotionalValue", "N/A")
            self._add_trade_message(f"레버리지 {actual_leverage}x 설정 완료 (max {max_notional})")
            
            # 2. 배분 자금 설정 (API 호출)
            import requests
            from gui.main import BASE_URL
            
            allocation_response = requests.post(
                f"{BASE_URL}/api/v1/funds/allocation/set",
                json={"engine": self.engine_name, "amount": funds_amount},
                timeout=5
            )
            
            if allocation_response.status_code == 200:
                allocation_data = allocation_response.json()
                
                # 레버리지 정보 실시간 동기화 (엔진 config['leverage'])
                try:
                    lev_sync = requests.post(
                        f"{BASE_URL}/api/v1/engine/leverage",
                        json={"engine": self.engine_name, "leverage": actual_leverage},
                        timeout=5
                    )
                    if lev_sync.status_code != 200:
                        self._add_risk_message(f"레버리지 동기화 실패: {lev_sync.text}")
                    
                    # ⭐ Orchestrator 심볼 준비 (Binance에 마진/레버리지 설정)
                    prepare_response = requests.post(
                        f"{BASE_URL}/api/v1/engine/prepare-symbol",
                        json={
                            "engine": self.engine_name,
                            "symbol": self.selected_symbol,
                            "leverage": actual_leverage
                        },
                        timeout=5
                    )
                    
                    if prepare_response.status_code == 200:
                        self._add_trade_message(f"✅ Binance 설정 완료: {self.selected_symbol} @ {actual_leverage}x")
                    else:
                        self._add_risk_message(f"⚠️ Binance 설정 실패: {prepare_response.text}")
                        
                except Exception as _e:
                    self._add_risk_message(f"레버리지 동기화 오류: {str(_e)}")

                # GUI의 applied_leverage 업데이트
                self.applied_leverage = actual_leverage
                
                self._add_trade_message(
                    f"설정 적용 완료 - 심볼 {self.selected_symbol}, 레버리지 {actual_leverage}x, 투입 {funds_percent}% (${funds_amount:.2f})"
                )
                print(f"[{self.engine_name}] ✅ 설정 성공: 레버리지={actual_leverage}x, 배분={funds_amount:.2f} USDT")
                # 사용자 의도: 설정 적용 직후 Total Slot Gain/Loss는 배정된 자금 표기, P&L %는 0.00%
                self._initialize_performance_after_apply(funds_amount)
            else:
                error_msg = allocation_response.text
                self._add_risk_message(f"자금 배정 실패: {error_msg}")
                print(f"[{self.engine_name}] ⚠️ 배분 자금 설정 실패: {error_msg}")
        
        except Exception as e:
            self._add_risk_message(f"설정 적용 오류: {str(e)}")
            print(f"[{self.engine_name}] ❌ Exception: {e}")
    
    def _on_return_funds(self):
        """Return Funds 버튼 - 운용 자금을 Available Funds로 반환"""
        if self.is_running:
            self._add_trade_message("거래 중에는 자금을 반환할 수 없습니다.")
            return
        
        try:
            import requests
            from gui.main import BASE_URL
            
            response = requests.post(
                f"{BASE_URL}/api/v1/funds/allocation/return",
                json={"engine": self.engine_name},
                timeout=5
            )
            
            if response.status_code == 200:
                returned_amount = 0.0
                try:
                    returned_amount = float(response.json().get("data", {}).get("returned_amount", 0.0) or 0.0)
                except Exception:
                    returned_amount = 0.0
                self._add_trade_message("자금 반환 완료.")
                self.handle_funds_returned(returned_amount, log_message=False)
            else:
                try:
                    error_detail = response.json().get("detail", response.text)
                except Exception:
                    error_detail = response.text
                self._add_trade_message(f"자금 반환 실패: {error_detail}")
        except Exception as e:
            self._add_trade_message(f"자금 반환 오류: {str(e)}")

    def _on_clear_history_clicked(self):
        """Trade History '기록 삭제' 버튼 클릭 핸들러.

        - 백엔드 API에 "이 엔진"의 trade_history 삭제를 요청하고
        - 성공 시 이 위젯의 로컬 테이블 및 메모리 기록도 초기화합니다.
        """

        from PySide6.QtWidgets import QMessageBox
        import requests
        from gui.main import BASE_URL

        reply = QMessageBox.question(
            self,
            "Trade History 삭제",
            f"{self.engine_name} 엔진의 거래 기록을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            resp = requests.delete(
                f"{BASE_URL}/api/v1/engine/trade-history/{self.engine_name}",
                timeout=5,
            )
            if resp.status_code != 200:
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    detail = resp.text
                QMessageBox.warning(self, "삭제 실패", f"서버에서 기록 삭제에 실패했습니다:\n{detail}")
                return

            # 서버 삭제 성공 시 이 엔진 위젯의 로컬 히스토리도 정리
            self.clear_trade_history()
            QMessageBox.information(self, "삭제 완료", f"{self.engine_name} 엔진의 거래 기록이 삭제되었습니다.")
        except Exception as e:
            QMessageBox.warning(self, "삭제 오류", f"기록 삭제 중 오류가 발생했습니다:\n{e}")
    
    def handle_funds_returned(self, returned_amount: float = 0.0, log_message: bool = True):
        """엔진 자금 반환 후 UI 및 통계를 초기화"""
        self.designated_funds = 0.0
        self._reset_performance_summary()
        # 사용자 의도: 자금 반환 후 슬라이더 및 표기 초기화
        try:
            default_percent = 30
            if hasattr(self, 'funds_slider') and self.funds_slider is not None:
                self.funds_slider.setValue(default_percent)
            # 표기 라벨 갱신 (account_total_balance 기반)
            if hasattr(self, 'funds_value_label'):
                allocated_amount = (default_percent / 100) * (self.account_total_balance or 0.0)
                self.funds_value_label.setText(f"{default_percent}% (${allocated_amount:.2f})")
        except Exception:
            pass
        if log_message:
            if returned_amount > 0:
                self._add_trade_message(f"Returned Funds: {returned_amount:.2f} USDT")
            else:
                self._add_trade_message("자금이 Available Funds로 반환되었습니다.")
    
    def _reset_performance_summary(self):
        """성과 요약 라벨 초기화"""
        if hasattr(self, 'gain_loss_label'):
            self.gain_loss_label.setText("0.000 USDT")
            self.gain_loss_label.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold;")
        if hasattr(self, 'pnl_label'):
            self.pnl_label.setText("0.00 %")
            self.pnl_label.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold;")

    def _initialize_performance_after_apply(self, allocated_amount: float):
        """설정 적용 직후 성과 표시를 사용자 의도에 맞게 초기화"""
        try:
            if hasattr(self, 'gain_loss_label'):
                self.gain_loss_label.setText(f"{allocated_amount:,.3f} USDT")
                self.gain_loss_label.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold;")
            if hasattr(self, 'pnl_label'):
                self.pnl_label.setText("0.00 %")
                self.pnl_label.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold;")
        except Exception:
            pass
    
    def set_account_total_balance(self, balance: float):
        """Account total balance 설정 (헤더에서 업데이트)"""
        self.account_total_balance = balance
        # 슬라이더 값이 변경되면 다시 계산
        if self.funds_slider:
            self._on_funds_slider_changed(self.funds_slider.value())
    
    def _on_funds_slider_changed(self, value):
        """투입 자금 슬라이더 값 변경"""
        if self.account_total_balance <= 0:
            # 초기 상태에서는 0으로 표시
            self.funds_value_label.setText(f"{value}% ($0.00)")
            return
        
        allocated_amount = (value / 100) * self.account_total_balance
        
        self.funds_value_label.setText(f"{value}% (${allocated_amount:.2f})")
        self._on_settings_changed()
        print(f"[{self.engine_name}] 투입 자금: {value}% → ${allocated_amount:.2f}")
    
    def _on_leverage_changed(self, value):
        """레버리지 슬라이더 값 변경"""
        self.applied_leverage = value
        self.leverage_value_label.setText(f"{value}x")
        self._on_settings_changed()
    
    def _on_settings_changed(self):
        """설정 변경 시 호출"""
        # 슬라이더 기반 자금 계산
        funds_percent = self.funds_slider.value()
        self.designated_funds = (funds_percent / 100) * self.account_total_balance if self.account_total_balance > 0 else 0.0
        
        settings = {
            "funds": self.designated_funds,
            "leverage": self.applied_leverage
        }
        self.settings_changed.emit(self.engine_name, settings)
    
    def _add_energy_message(self, message: str):
        """상승에너지 강도 분석 메시지 추가"""
        self._energy_messages.append(message)
        if len(self._energy_messages) > self._max_messages:
            self._energy_messages.pop(0)
        self.energy_text.setPlainText("\n".join(self._energy_messages))
        self._scroll_to_bottom(self.energy_text)
    
    def _add_trade_message(self, message: str):
        """거래 포지션 진입/익절 분석 메시지 추가"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self._trade_messages.append(formatted_message)
        if len(self._trade_messages) > self._max_messages:
            self._trade_messages.pop(0)
        self.trade_text.setPlainText("\n".join(self._trade_messages))
        self._scroll_to_bottom(self.trade_text)
    
    def _add_risk_message(self, message: str):
        """거래 리스크 관리 메시지 추가"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self._risk_messages.append(formatted_message)
        if len(self._risk_messages) > self._max_messages:
            self._risk_messages.pop(0)
        self.risk_text.setPlainText("\n".join(self._risk_messages))
        self._scroll_to_bottom(self.risk_text)
    
    def _scroll_to_bottom(self, text_edit: QTextEdit):
        """텍스트 에디트를 맨 아래로 스크롤"""
        scrollbar = text_edit.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())
    
    def update_strategy_from_analysis(
        self,
        symbol: str,
        max_target_profit: float,
        risk_management: dict,
        executable_parameters: Optional[dict] = None,
        ui_meta: Optional[dict] = None
    ):
        """
        전략 분석 결과로 엔진 설정 업데이트
        
        Args:
            symbol: 코인 심볼
            max_target_profit: 최대 목표 수익률%
            risk_management: 리스크 관리 딕셔너리 (stop_loss, trailing_stop)
        """
        print(f"[{self.engine_name}] 🔧 전략 업데이트: {symbol}")
        print(f"[{self.engine_name}] 🔧 executable_parameters: {executable_parameters}")
        
        # 1. 심볼 설정
        self.selected_symbol = symbol
        if hasattr(self, 'symbol_label'):
            self.symbol_label.setText(symbol)
        
        # 2. 익절률 업데이트 (최대 목표 수익률% 기반)
        # 엔진별 기본 익절률 가져오기
        base_profit = {
            "Alpha": 3.7,
            "Beta": 5.0,
            "Gamma": 8.5
        }
        
        # 분석 결과의 최대 목표 수익률%와 기본값 중 작은 값 사용
        target_profit = min(
            max_target_profit,
            base_profit.get(self.engine_name, 3.7)
        )
        
        # 3. 리스크 관리 업데이트 (참고용)
        stop_loss = risk_management.get("stop_loss", 0.5)
        trailing_stop = risk_management.get("trailing_stop", 0.3)
        
        # 메시지 추가
        self._add_trade_message(
            f"✅ 전략 업데이트: {symbol}\n"
            f"   최대 목표 수익률: {target_profit:.2f}%\n"
            f"   손절: {stop_loss:.2f}%, 트레일링: {trailing_stop:.2f}%"
        )
        
        # 4. executable_parameters가 주어지면 실제 UI 컨트롤 및 내부 상태에 반영
        if executable_parameters:
            try:
                # leverage: only apply if user explicitly confirmed via ui_meta
                lev = executable_parameters.get("leverage")
                if lev is not None:
                    try:
                        confirmed = False
                        if isinstance(ui_meta, dict):
                            confirmed = bool(ui_meta.get('leverage_user_confirmed'))
                        if confirmed:
                            lev_int = int(float(lev))
                            lev_int = max(1, min(50, lev_int))
                            self.applied_leverage = lev_int
                            if hasattr(self, 'leverage_slider'):
                                self.leverage_slider.setValue(lev_int)
                                self.leverage_value_label.setText(f"{lev_int}x")
                        else:
                            # Do not auto-apply leverage without explicit user confirmation
                            print(f"[{self.engine_name}] ⚠️ Skipping applying leverage ({lev}) because ui_meta.leverage_user_confirmed is not True")
                    except Exception:
                        pass

                # position_size -> funds_slider (percent)
                ps = executable_parameters.get("position_size")
                if ps is not None:
                    try:
                        confirmed = False
                        if isinstance(ui_meta, dict):
                            confirmed = bool(ui_meta.get('leverage_user_confirmed'))
                        if confirmed:
                            # if fraction (<=1) convert to percent
                            if isinstance(ps, float) and ps <= 1:
                                pct = int(max(10, min(100, round(ps * 100))))
                            else:
                                pct = int(max(10, min(100, int(ps))))
                            if hasattr(self, 'funds_slider'):
                                self.funds_slider.setValue(pct)
                                # update label and internal designated funds
                                allocated_amount = (pct / 100) * self.account_total_balance
                                self.designated_funds = allocated_amount
                                self.funds_value_label.setText(f"{pct}% (${allocated_amount:.2f})")
                                # propagate settings change
                                self._on_settings_changed()
                        else:
                            print(f"[{self.engine_name}] ⚠️ Skipping applying position_size ({ps}) because ui_meta.leverage_user_confirmed is not True")
                    except Exception:
                        pass

                # stop_loss_pct / take_profit_pct / trailing_stop_pct -> record and show
                sl = executable_parameters.get("stop_loss_pct")
                tp = executable_parameters.get("take_profit_pct")
                ts = executable_parameters.get("trailing_stop_pct")
                messages = []
                if sl is not None:
                    try:
                        messages.append(f"손절: {float(sl)*100:.2f}%")
                    except Exception:
                        pass
                if tp is not None:
                    try:
                        messages.append(f"익절: {float(tp)*100:.2f}%")
                    except Exception:
                        pass
                if ts is not None:
                    try:
                        messages.append(f"트레일링: {float(ts)*100:.2f}%")
                    except Exception:
                        pass
                if messages:
                    self._add_risk_message("🔧 적용 파라미터: " + ", ".join(messages))

                # strategy-specific params (fast/slow ema etc.) -> record for visibility
                sp_extra = {}
                for k in ("fast_ema_period", "slow_ema_period", "stop_loss_pct", "take_profit_pct"):
                    if k in executable_parameters:
                        sp_extra[k] = executable_parameters.get(k)
                if sp_extra:
                    self._add_trade_message(f"파라미터 적용: {sp_extra}")
            except Exception as e:
                print(f"[{self.engine_name}] ⚠️ executable param 적용 오류: {e}")
        print(f"[{self.engine_name}] ✅ 전략 업데이트 완료: {symbol} (익절: {target_profit:.2f}%)")
    
    def handle_backend_event(self, event: Dict[str, Any]):
        """백엔드 이벤트 처리 (신규 이벤트 타입 포함)"""
        event_type = event.get("type")
        
        if event_type == "DATA_PROGRESS":
            intervals = event.get("intervals", [])
            progress_lines = []
            for itv in intervals:
                interval = itv.get("interval")
                have = itv.get("have")
                required = itv.get("required")
                ready = itv.get("ready")
                status = "✓" if ready else "..."
                progress_lines.append(f"{interval}: {have}/{required} {status}")
            self._add_energy_message(f"📊 데이터 적재 중:\n  " + "\n  ".join(progress_lines))
        
        elif event_type == "SYMBOL_UNSUPPORTED":
            reason = event.get("reason", "unknown")
            self._add_energy_message(f"❌ 심볼 미지원: {reason}")
        
        elif event_type == "WATCHLIST":
            score = event.get("score", 0)
            triggers = event.get("triggers", [])
            trigger_text = ", ".join(triggers[:3])  # 최대 3개만 표시
            self._add_energy_message(f"👁️ WATCHLIST (점수={score:.1f}): {trigger_text}")
        
        elif event_type == "THRESHOLD_UPDATE":
            min_t = event.get("min", 0)
            strong_t = event.get("strong", 0)
            instant_t = event.get("instant", 0)
            self._add_energy_message(f"🔄 동적 임계치: min={min_t:.0f} / strong={strong_t:.0f} / instant={instant_t:.0f}")
        
        elif event_type == "PROTECTIVE_PAUSE":
            failures = event.get("failures_last_window", 0)
            window = event.get("window_sec", 0)
            self._add_risk_message(f"🛡️ 보호 모드 진입: {window}초 내 {failures}회 실패")
        
        elif event_type == "PAUSE":
            self._add_trade_message("⏸️ 보호 모드 활성 - 거래 차단")
        
        elif event_type == "TRAILING_ACTIVATED":
            old_stop = event.get("old_stop", 0)
            new_stop = event.get("new_stop", 0)
            pnl_pct = event.get("pnl_pct", 0)
            self._add_risk_message(f"🔒 트레일링 활성화: Stop {old_stop:.4f}→{new_stop:.4f} (PnL={pnl_pct:.2f}%)")
        
        elif event_type == "ENTRY":
            price = event.get("price", 0)
            order_id = event.get("order_id", "")
            self._add_trade_message(f"✅ 진입 성공: {price:.4f} (주문#{order_id})")
        
        elif event_type == "ENTRY_FAIL":
            error = event.get("error", "unknown")
            self._add_trade_message(f"❌ 진입 실패: {error}")
        
        elif event_type == "EXIT":
            reason = event.get("reason", "")
            price = event.get("price", 0)
            self._add_trade_message(f"🔄 청산: {reason} @ {price:.4f}")
        
        elif event_type == "HOLD":
            # 일반 HOLD는 표시하지 않음 (로그 스팸 방지)
            pass

    def update_energy_analysis(self, data: Dict[str, Any]):
        """상승에너지 강도 분석 업데이트"""
        symbol = data.get("symbol", "-")
        volume = data.get("volume_strength", "분석 중")
        ema = data.get("ema_trend", "분석 중")
        macd = data.get("macd_signal", "분석 중")
        stoch_rsi = data.get("stoch_rsi", "분석 중")
        energy_level = data.get("energy_level", "분석 중")
        
        message = (
            f"코인 심볼: {symbol}\n"
            f"거래량: {volume} / EMA: {ema} / MACD: {macd}\n"
            f"Stoch RSI: {stoch_rsi} / 종합 상승 에너지: {energy_level}"
        )
        
        self._energy_messages = [message]  # 최신 분석으로 교체
        self.energy_text.setPlainText(message)
    
    def update_stats(self, data: Dict[str, Any]):
        """성과 요약 업데이트"""
        gain_loss = data.get("total_gain_loss")
        if gain_loss is None:
            gain_loss = data.get("realized_pnl", 0.0)
        pnl_percent = data.get("pnl_percent", 0.0)
        
        # Total Slot Gain/Loss 색상 및 표시
        if gain_loss > 0:
            gain_loss_color = "#4CAF50"
            gain_loss_text = f"+{gain_loss:,.3f} USDT"
        elif gain_loss < 0:
            gain_loss_color = "#f44336"
            gain_loss_text = f"{gain_loss:,.3f} USDT"
        else:
            gain_loss_color = "#888888"
            gain_loss_text = "0.000 USDT"
        
        self.gain_loss_label.setText(gain_loss_text)
        self.gain_loss_label.setStyleSheet(f"color: {gain_loss_color}; font-size: 10px; font-weight: bold;")
        
        # P&L % 색상 및 표시
        if pnl_percent > 0:
            pnl_color = "#4CAF50"
            pnl_text = f"+{pnl_percent:.2f} %"
        elif pnl_percent < 0:
            pnl_color = "#f44336"
            pnl_text = f"{pnl_percent:.2f} %"
        else:
            pnl_color = "#888888"
            pnl_text = "0.00 %"
        
        self.pnl_label.setText(pnl_text)
        self.pnl_label.setStyleSheet(f"color: {pnl_color}; font-size: 10px; font-weight: bold;")
    
    def add_trade_record(self, symbol: str, funds: float, leverage: int, profit_loss: float, pnl_percent: float):
        """거래 기록 추가"""
        # 현재 시간 기준 기록 (실시간 완료 이벤트용)
        trade_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 거래 기록 저장
        record = {
            "datetime": trade_datetime,
            "symbol": symbol,
            "funds": funds,
            "leverage": leverage,
            "profit_loss": profit_loss,
            "pnl_percent": pnl_percent
        }
        self._trade_history.insert(0, record)  # 최신 기록을 앞에 추가
        
        # 최대 기록 수 제한
        if len(self._trade_history) > self._max_history:
            self._trade_history.pop()
        
        # 테이블에 행 추가 (맨 위에)
        self.history_table.insertRow(0)
        
        # 거래 일시
        datetime_item = QTableWidgetItem(trade_datetime)
        datetime_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_table.setItem(0, 0, datetime_item)
        
        # 코인 심볼
        symbol_item = QTableWidgetItem(symbol)
        symbol_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_table.setItem(0, 1, symbol_item)
        
        # 투입 자금
        funds_item = QTableWidgetItem(f"{funds:,.0f} USDT")
        funds_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.history_table.setItem(0, 2, funds_item)
        
        # 레버리지
        leverage_item = QTableWidgetItem(f"{leverage}x")
        leverage_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_table.setItem(0, 3, leverage_item)
        
        # 수익/손실 (색상 적용)
        if profit_loss >= 0:
            profit_loss_text = f"+{profit_loss:,.2f} USDT"
            profit_loss_color = QColor(76, 175, 80)  # 녹색
        else:
            profit_loss_text = f"{profit_loss:,.2f} USDT"
            profit_loss_color = QColor(244, 67, 54)  # 빨간색
        
        profit_loss_item = QTableWidgetItem(profit_loss_text)
        profit_loss_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        profit_loss_item.setForeground(profit_loss_color)
        self.history_table.setItem(0, 4, profit_loss_item)
        
        # 미실현 P&L % (색상 적용)
        if pnl_percent >= 0:
            pnl_text = f"+{pnl_percent:.2f} %"
            pnl_color = QColor(76, 175, 80)  # 녹색
        else:
            pnl_text = f"{pnl_percent:.2f} %"
            pnl_color = QColor(244, 67, 54)  # 빨간색
        
        pnl_item = QTableWidgetItem(pnl_text)
        pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pnl_item.setForeground(pnl_color)
        self.history_table.setItem(0, 5, pnl_item)
        
        # 최대 행 수 제한
        while self.history_table.rowCount() > self._max_history:
            self.history_table.removeRow(self.history_table.rowCount() - 1)

    def add_trade_record_from_history(
        self,
        trade_datetime: str,
        symbol: str,
        funds: float,
        leverage: int,
        profit_loss: float,
        pnl_percent: float,
    ) -> None:
        """DB에서 불러온 기존 Trade History 레코드를 추가합니다.

        앱 재실행 후 과거 기록 복원용으로 사용됩니다.
        """

        record = {
            "datetime": trade_datetime,
            "symbol": symbol,
            "funds": funds,
            "leverage": leverage,
            "profit_loss": profit_loss,
            "pnl_percent": pnl_percent,
        }
        self._trade_history.append(record)

        # 테이블의 맨 아래에 추가 (오래된 기록부터 위로 쌓이도록)
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)

        datetime_item = QTableWidgetItem(trade_datetime)
        datetime_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_table.setItem(row, 0, datetime_item)

        symbol_item = QTableWidgetItem(symbol)
        symbol_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_table.setItem(row, 1, symbol_item)

        funds_item = QTableWidgetItem(f"{funds:,.0f} USDT")
        funds_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.history_table.setItem(row, 2, funds_item)

        leverage_item = QTableWidgetItem(f"{leverage}x")
        leverage_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_table.setItem(row, 3, leverage_item)

        if profit_loss >= 0:
            profit_loss_text = f"+{profit_loss:,.2f} USDT"
            profit_loss_color = QColor(76, 175, 80)
        else:
            profit_loss_text = f"{profit_loss:,.2f} USDT"
            profit_loss_color = QColor(244, 67, 54)

        profit_loss_item = QTableWidgetItem(profit_loss_text)
        profit_loss_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        profit_loss_item.setForeground(profit_loss_color)
        self.history_table.setItem(row, 4, profit_loss_item)

        if pnl_percent >= 0:
            pnl_text = f"+{pnl_percent:.2f} %"
            pnl_color = QColor(76, 175, 80)
        else:
            pnl_text = f"{pnl_percent:.2f} %"
            pnl_color = QColor(244, 67, 54)

        pnl_item = QTableWidgetItem(pnl_text)
        pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pnl_item.setForeground(pnl_color)
        self.history_table.setItem(row, 5, pnl_item)

        # 최대 행 수 제한 (오래된 것부터 제거)
        while self.history_table.rowCount() > self._max_history:
            self.history_table.removeRow(0)

    def clear_trade_history(self):
        """로컬 Trade History 기록 및 테이블을 모두 삭제"""
        self._trade_history.clear()
        self.history_table.setRowCount(0)
    
    def set_status(self, is_running: bool):
        """상태 설정 (외부에서 호출)"""
        self.is_running = is_running
        self.toggle_button.setChecked(is_running)
        
        if is_running:
            self.toggle_button.setText("거래 정지")
            if hasattr(self, 'return_funds_button'):
                self.return_funds_button.setEnabled(False)
        else:
            self.toggle_button.setText("거래 활성화")
            if hasattr(self, 'return_funds_button'):
                self.return_funds_button.setEnabled(True)


class MiddleSessionWidget(QWidget):
    """하단 푸터 - 알파, 베타, 감마 3개 자동매매 엔진"""
    
    # 시그널
    engine_start_signal = Signal(str)  # 엔진 시작 (엔진명)
    engine_stop_signal = Signal(str)   # 엔진 정지 (엔진명)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._load_initial_trade_history()
    
    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        # 1. Alpha 엔진
        self.alpha_engine = TradingEngineWidget("Alpha", "#4CAF50", self)
        self.alpha_engine.start_signal.connect(self._on_engine_start)
        self.alpha_engine.stop_signal.connect(self._on_engine_stop)
        main_layout.addWidget(self.alpha_engine)
        
        # 2. Beta 엔진
        self.beta_engine = TradingEngineWidget("Beta", "#2196F3", self)
        self.beta_engine.start_signal.connect(self._on_engine_start)
        self.beta_engine.stop_signal.connect(self._on_engine_stop)
        main_layout.addWidget(self.beta_engine)
        
        # 3. Gamma 엔진
        self.gamma_engine = TradingEngineWidget("Gamma", "#FF9800", self)
        self.gamma_engine.start_signal.connect(self._on_engine_start)
        self.gamma_engine.stop_signal.connect(self._on_engine_stop)
        main_layout.addWidget(self.gamma_engine)

    def _load_initial_trade_history(self) -> None:
        """앱 시작 시 각 엔진의 과거 Trade History를 백엔드에서 불러와 복원합니다."""

        try:
            import requests
            from gui.main import BASE_URL
        except Exception:
            return

        for engine_name, widget in [
            ("Alpha", self.alpha_engine),
            ("Beta", self.beta_engine),
            ("Gamma", self.gamma_engine),
        ]:
            try:
                resp = requests.get(
                    f"{BASE_URL}/api/v1/engine/trade-history/{engine_name}",
                    timeout=5,
                )
                if resp.status_code != 200:
                    continue

                data = resp.json() or []
                # API는 최신 기록이 먼저 오도록 정렬해서 주지만,
                # 테이블에는 오래된 기록부터 위→아래로 쌓이도록 역순으로 추가
                for item in reversed(data):
                    widget.add_trade_record_from_history(
                        trade_datetime=item.get("trade_datetime", ""),
                        symbol=item.get("symbol", ""),
                        funds=float(item.get("funds", 0.0) or 0.0),
                        leverage=int(item.get("leverage", 1) or 1),
                        profit_loss=float(item.get("profit_loss", 0.0) or 0.0),
                        pnl_percent=float(item.get("pnl_percent", 0.0) or 0.0),
                    )
            except Exception:
                # 초기 로딩 실패는 치명적이지 않으므로 조용히 무시
                continue

        # Previously a `newmodular_engine` alias was created here for backwards compatibility.
        # That temporary alias has been removed as part of the Alpha/Beta/Gamma migration.
    
    def _on_engine_start(self, engine_name: str):
        """엔진 시작 시그널 전파"""
        self.engine_start_signal.emit(engine_name)
    
    def _on_engine_stop(self, engine_name: str):
        """엔진 정지 시그널 전파"""
        self.engine_stop_signal.emit(engine_name)
    
    @Slot(dict)
    def handle_message(self, message: Dict[str, Any]):
        """WebSocket 메시지 처리"""
        msg_type = message.get("type")
        engine_name = message.get("engine", "")  # "Alpha", "Beta", "Gamma"
        
        # 새로운 백엔드 이벤트 타입 처리
        if msg_type in ["DATA_PROGRESS", "SYMBOL_UNSUPPORTED", "WATCHLIST", "THRESHOLD_UPDATE", 
                        "PROTECTIVE_PAUSE", "PAUSE", "TRAILING_ACTIVATED", "ENTRY", "ENTRY_FAIL", "EXIT", "HOLD"]:
            engine_widget = None
            if engine_name == "Alpha":
                engine_widget = self.alpha_engine
            elif engine_name == "Beta":
                engine_widget = self.beta_engine
            elif engine_name == "Gamma":
                engine_widget = self.gamma_engine
            
            if engine_widget:
                engine_widget.handle_backend_event(message)
            return
        
        if msg_type == "ENGINE_ENERGY_ANALYSIS":
            # 상승에너지 강도 분석
            data = message.get("data", {})
            if engine_name == "Alpha":
                self.alpha_engine.update_energy_analysis(data)
            elif engine_name == "Beta":
                self.beta_engine.update_energy_analysis(data)
            elif engine_name == "Gamma":
                self.gamma_engine.update_energy_analysis(data)
        
        elif msg_type == "ENGINE_TRADE_MESSAGE":
            # 거래 포지션 진입/익절 메시지
            msg_text = message.get("message", "")
            if engine_name == "Alpha" and msg_text:
                self.alpha_engine._add_trade_message(msg_text)
            elif engine_name == "Beta" and msg_text:
                self.beta_engine._add_trade_message(msg_text)
            elif engine_name == "Gamma" and msg_text:
                self.gamma_engine._add_trade_message(msg_text)
        
        elif msg_type == "ENGINE_RISK_MESSAGE":
            # 거래 리스크 관리 메시지
            msg_text = message.get("message", "")
            if engine_name == "Alpha" and msg_text:
                self.alpha_engine._add_risk_message(msg_text)
            elif engine_name == "Beta" and msg_text:
                self.beta_engine._add_risk_message(msg_text)
            elif engine_name == "Gamma" and msg_text:
                self.gamma_engine._add_risk_message(msg_text)
        
        elif msg_type == "ENGINE_TRADE_COMPLETED":
            # 거래 완료 - Trade History에 추가
            data = message.get("data", {})
            symbol = data.get("symbol", "")
            funds = data.get("funds", 0.0)
            leverage = data.get("leverage", 1)
            profit_loss = data.get("profit_loss", 0.0)
            pnl_percent = data.get("pnl_percent", 0.0)
            
            if engine_name == "Alpha" and symbol:
                self.alpha_engine.add_trade_record(symbol, funds, leverage, profit_loss, pnl_percent)
            elif engine_name == "Beta" and symbol:
                self.beta_engine.add_trade_record(symbol, funds, leverage, profit_loss, pnl_percent)
            elif engine_name == "Gamma" and symbol:
                self.gamma_engine.add_trade_record(symbol, funds, leverage, profit_loss, pnl_percent)
        
        elif msg_type == "ENGINE_STATS_UPDATE":
            # 엔진 통계 업데이트
            data = message.get("data", {})
            if engine_name == "Alpha":
                self.alpha_engine.update_stats(data)
            elif engine_name == "Beta":
                self.beta_engine.update_stats(data)
            elif engine_name == "Gamma":
                self.gamma_engine.update_stats(data)
        
        elif msg_type == "ENGINE_STATUS_UPDATE":
            # 엔진 상태 업데이트
            is_running = message.get("is_running", False)
            if engine_name == "Alpha":
                self.alpha_engine.set_status(is_running)
            elif engine_name == "Beta":
                self.beta_engine.set_status(is_running)
            elif engine_name == "Gamma":
                self.gamma_engine.set_status(is_running)
        
        elif msg_type == "ENGINE_STATUS_MESSAGE":
            category = message.get("category", "trade")
            msg_text = message.get("message", "")
            target = None
            if engine_name == "Alpha":
                target = self.alpha_engine
            elif engine_name == "Beta":
                target = self.beta_engine
            elif engine_name == "Gamma":
                target = self.gamma_engine
            if target and msg_text:
                if category == "risk":
                    target._add_risk_message(msg_text)
                elif category == "energy":
                    target._add_energy_message(msg_text)
                else:
                    target._add_trade_message(msg_text)
        
        elif msg_type == "ENGINE_FUNDS_RETURNED":
            returned_amount = message.get("data", {}).get("returned_amount", 0.0)
            if engine_name == "Alpha":
                self.alpha_engine.handle_funds_returned(returned_amount)
            elif engine_name == "Beta":
                self.beta_engine.handle_funds_returned(returned_amount)
            elif engine_name == "Gamma":
                self.gamma_engine.handle_funds_returned(returned_amount)
        
        # 기존 메시지 타입 호환성 유지
        elif msg_type == "ENERGY_ANALYSIS_UPDATE":
            # 알파 엔진에 표시
            data = message.get("data", {})
            self.alpha_engine.update_energy_analysis(data)
    
    def get_engine_status(self) -> Dict[str, bool]:
        """각 엔진의 실행 상태 반환"""
        return {
            "Alpha": self.alpha_engine.is_running,
            "Beta": self.beta_engine.is_running,
            "Gamma": self.gamma_engine.is_running
        }
    
    def start_all_engines(self):
        """모든 엔진 시작"""
        for engine in [self.alpha_engine, self.beta_engine, self.gamma_engine]:
            if not engine.is_running:
                engine.toggle_button.setChecked(True)
                engine._on_toggle_clicked()
    
    def stop_all_engines(self):
        """모든 엔진 정지"""
        for engine in [self.alpha_engine, self.beta_engine, self.gamma_engine]:
            if engine.is_running:
                engine.toggle_button.setChecked(False)
                engine._on_toggle_clicked()
