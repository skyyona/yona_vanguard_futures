from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, Signal, Slot

class HeaderWidget(QWidget):
    """
    애플리케이션의 상단 헤더 위젯.
    앱 타이틀, 계좌 정보, 글로벌 세션, 앱 제어 버튼을 포함합니다.
    """
    # START/STOP 버튼 클릭 시그널
    start_signal = Signal()
    stop_signal = Signal()
    # 긴급 청산 버튼 클릭 시그널
    emergency_liquidation_signal = Signal()
    # Initial Investment 재설정 시그널
    initial_investment_reset_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeaderWidget")
        self._init_ui()
        # 한국시간 실시간 표기 타이머 추가 (_init_ui() 후에 생성)
        from PySide6.QtCore import QTimer
        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_kst_time)
        self._time_timer.start(1000)
        self._update_kst_time()  # 초기 시간 표시
    def _update_kst_time(self):
        """한국시간(KST) 실시간 표기 - 5열 하단 시간 라벨 업데이트"""
        from datetime import datetime, timedelta, timezone
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst)
        time_str = now.strftime('%Y-%m-%d %p %I:%M:%S KST')
        if hasattr(self, 'global_session_time_label'):
            self.global_session_time_label.setText(time_str)

    def _init_ui(self):
        # Main horizontal layout - 1행 7열 구조
        main_horizontal_layout = QHBoxLayout(self)
        main_horizontal_layout.setContentsMargins(15, 8, 15, 8)
        main_horizontal_layout.setSpacing(10)
        
        # 1열: 앱 타이틀 + 중요 오류 메시지 창 (18%)
        column1_widget = self._create_column1_widget()
        main_horizontal_layout.addWidget(column1_widget, 18)
        
        # 2열: Initial Investment + 투입 자금 값 (13%)
        column2_widget = self._create_column2_widget()
        main_horizontal_layout.addWidget(column2_widget, 13)
        
        # 3열: Available Funds (13%)
        column3_widget = self._create_column3_widget()
        main_horizontal_layout.addWidget(column3_widget, 13)
        
        # 4열: Total Trading Value (13%)
        column4_widget = self._create_column4_widget()
        main_horizontal_layout.addWidget(column4_widget, 13)
        
        # 5열: Cumulative Return % (10%)
        column5_widget = self._create_column5_widget()
        main_horizontal_layout.addWidget(column5_widget, 10)
        
        # 6열: Global trading session + KST 시간 + 세션 메시지 (26%)
        column6_widget = self._create_column6_widget()
        main_horizontal_layout.addWidget(column6_widget, 26)
        
        # 7열: 앱 작동 상황 메시지 + 버튼 3개 (20%)
        column7_widget = self._create_column7_widget()
        main_horizontal_layout.addWidget(column7_widget, 20)


    def _create_column1_widget(self):
        """1열: 앱 타이틀(상단) + 중요 오류 메시지 창(하단)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 상단: 앱 타이틀 (가운데 정렬)
        self.title_label = QLabel("YONA Vanguard Futures")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.title_label.setFont(font)
        self.set_title_color("#FFA500")  # 초기 상태: 주황색 (대기 상태)
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # 하단: 중요 오류 메시지 창 (항상 표시되는 어두운 컨테이너)
        self.error_display = QLabel()
        self.error_display.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                background-color: #2b2d30;
                min-height: 24px;
            }
        """)
        self.error_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.error_display.setText("")  # 초기 빈 메시지
        layout.addWidget(self.error_display)
        
        return widget

    def _create_column2_widget(self):
        """2열: Initial Investment(상단) + 투입 자금 값(하단, USDT 형식)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 상단: 버튼
        self.initial_investment_button = QPushButton("[Initial Investment]")
        self.initial_investment_button.setCursor(Qt.PointingHandCursor)
        self.initial_investment_button.setStyleSheet("""
            QPushButton {
                background-color: #4fd4c7;
                color: #0f2d2f;
                font-weight: bold;
                border-radius: 12px;
                padding: 6px 12px;
                border: none;
            }
            QPushButton:hover {
                background-color: #5fe0d4;
            }
            QPushButton:pressed {
                background-color: #44bfb3;
            }
        """)
        self.initial_investment_button.clicked.connect(self.initial_investment_reset_signal.emit)
        layout.addWidget(self.initial_investment_button, alignment=Qt.AlignCenter)
        
        # 하단: 투입 자금 값 (USDT 형식)
        self.initial_investment_label = QLabel("0.00 USDT")
        self.initial_investment_label.setObjectName("initial_investment_label")
        self.initial_investment_label.setStyleSheet("color: white; font-weight: bold;")
        self.initial_investment_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.initial_investment_label)
        
        return widget

    def _create_column3_widget(self):
        """3열: Available Funds"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 상단: 기능명
        title_label = QLabel("Available Funds")
        title_label.setStyleSheet("color: #90A4AE; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 하단: 가용 자금 값
        self.available_funds_label = QLabel("0.00 USDT")
        self.available_funds_label.setObjectName("available_funds_label")
        self.available_funds_label.setStyleSheet("color: white; font-weight: bold;")
        self.available_funds_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.available_funds_label)
        
        return widget

    def _create_column4_widget(self):
        """4열: Total Trading Value"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 상단: 기능명
        title_label = QLabel("Total Trading Value")
        title_label.setStyleSheet("color: #90A4AE; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 하단: 총 거래 평가액
        self.total_trading_value_label = QLabel("0.00 USDT")
        self.total_trading_value_label.setObjectName("total_trading_value_label")
        self.total_trading_value_label.setStyleSheet("color: white; font-weight: bold;")
        self.total_trading_value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.total_trading_value_label)
        
        return widget

    def _create_column5_widget(self):
        """5열: Cumulative Return %"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        title_label = QLabel("Cumulative Return %")
        title_label.setStyleSheet("color: #90A4AE; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        self.cumulative_return_label = QLabel("+0.00 %")
        self.cumulative_return_label.setObjectName("cumulative_return_label")
        self.cumulative_return_label.setStyleSheet("color: #00C853; font-weight: bold;")
        self.cumulative_return_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.cumulative_return_label)
        
        return widget

    def _create_column6_widget(self):
        """6열: Global trading session(상단) + 하단 2열(KST 시간 + 세션 메시지)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 상단: 기능명
        title_label = QLabel("Global trading session")
        title_label.setStyleSheet("color: #90A4AE; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 하단: 2열로 나눠서 1열은 KST 시간, 2열은 세션 메시지 (가로 배치)
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)
        
        # 1열: KST 시간 (실시간 1초 업데이트)
        self.global_session_time_label = QLabel("2025-11-16 PM 11:02:44 KST")
        self.global_session_time_label.setObjectName("global_session_time_label")
        self.global_session_time_label.setStyleSheet("color: #90A4AE; font-weight: bold;")
        self.global_session_time_label.setAlignment(Qt.AlignCenter)
        bottom_layout.addWidget(self.global_session_time_label)
        
        # 2열: 세션 메시지
        self.global_session_message_label = QLabel("분석 중...")
        self.global_session_message_label.setObjectName("global_session_message_label")
        self.global_session_message_label.setStyleSheet("color: white; font-weight: bold;")
        self.global_session_message_label.setAlignment(Qt.AlignCenter)
        bottom_layout.addWidget(self.global_session_message_label)
        
        layout.addWidget(bottom_widget)
        
        return widget
    
    def _create_column7_widget(self):
        """7열: 앱 작동 상황 메시지(상단) + 버튼 3개(하단)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 상단: 앱 작동 상황 메시지
        self.status_label = QLabel("Inactive")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 하단: 버튼 3개 (forced liquidation, START, STOP)
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        
        # forced liquidation 버튼 (START 앞으로 이동)
        self.emergency_liquidation_button = QPushButton("forced liquidation")
        self.emergency_liquidation_button.setObjectName("EmergencyLiquidationButton")
        self.emergency_liquidation_button.setFixedSize(140, 35)
        self.emergency_liquidation_button.setStyleSheet("""
            QPushButton {
                background-color: #808080;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #a020f0;
            }
            QPushButton:pressed {
                background-color: #8010d0;
            }
        """)
        self.emergency_liquidation_button.clicked.connect(self.emergency_liquidation_signal.emit)
        button_layout.addWidget(self.emergency_liquidation_button)
        
        # START 버튼
        self.start_button = QPushButton("START")
        self.start_button.setObjectName("StartButton")
        self.start_button.setFixedSize(80, 35)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:disabled {
                background-color: #81C784;
            }
        """)
        self.start_button.clicked.connect(self.start_signal.emit)
        button_layout.addWidget(self.start_button)
        
        # STOP 버튼
        self.stop_button = QPushButton("STOP")
        self.stop_button.setObjectName("StopButton")
        self.stop_button.setFixedSize(80, 35)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #C62828;
                color: white;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:disabled {
                background-color: #E57373;
            }
        """)
        self.stop_button.clicked.connect(self.stop_signal.emit)
        button_layout.addWidget(self.stop_button)
        
        layout.addWidget(button_widget)
        
        return widget
        
    def set_title_color(self, color: str):
        """타이틀 색상 설정"""
        self.title_label.setStyleSheet(f"color: {color};")
        self.title_label.setFont(self.title_label.font())
        
    def show_error_message(self, message: str, error_type: str = "error"):
        """Show error message in the header (항상 표시되는 어두운 컨테이너에 흰색 텍스트)
        
        Args:
            message: The error message to display
            error_type: Type of error (error, warning, info)
        """
        # 메시지가 없으면 빈 텍스트만 표시 (창은 항상 보임)
        if not message:
            self.error_display.setText("")
            return
            
        # 어두운 컨테이너 배경에 밝은 흰색 텍스트로 고정
        self.error_display.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                background-color: #2b2d30;
                min-height: 24px;
            }
        """)
        
        self.error_display.setText(message)
        
        # Auto-clear after 10 seconds for non-critical messages
        if error_type != "error":
            from PySide6.QtCore import QTimer
            QTimer.singleShot(10000, lambda: self.clear_error_message() if self.error_display.text() == message else None)
    
    def clear_error_message(self):
        """Clear the error message (창은 숨기지 않고 빈 텍스트만 표시)"""
        self.error_display.setText("")

    @Slot(dict)
    def handle_message(self, message: dict):
        """백엔드로부터 받은 메시지를 처리하여 UI를 업데이트합니다."""
        msg_type = message.get("type")

        if msg_type == "APP_STATUS_UPDATE":
            self._update_app_status(message.get("data", {}))
        elif msg_type == "HEADER_UPDATE":
            self._update_header_data(message.get("data", {}))

    def _update_app_status(self, data: dict):
        """앱의 전반적인 상태(연결, 활성/비활성)를 업데이트합니다."""
        status = data.get("status")
        
        # 타이틀 색상 변경
        if status == "connected_inactive": # 연결됨, 비활성
            self.set_title_color("#FFA500") # 주황색
            self.status_label.setText("Inactive")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
        elif status == "connected_active": # 연결됨, 활성
            self.set_title_color("#00C853") # 녹색
            self.status_label.setText("Active")
            self.status_label.setStyleSheet("color: #00C853; font-weight: bold;")
        elif status == "error": # 오류
            self.set_title_color("#FF1744") # 빨간색
            self.status_label.setText("Error")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
        else: # 초기화 중 또는 연결 끊김
            self.set_title_color("gray")
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: gray; font-weight: bold;")
    
    def _update_header_data(self, data: dict):
        """헤더의 계좌 정보 및 세션 정보를 업데이트합니다."""
        try:
            # Initial Investment (2열) - USDT 형식으로 표시
            initial_capital = data.get("initial_capital")
            if initial_capital is not None:
                if hasattr(self, 'initial_investment_label'):
                    self.initial_investment_label.setText(f"{initial_capital:,.2f} USDT")

            # Available Funds (3열)
            available_funds = data.get("available_funds")
            if available_funds is not None and hasattr(self, 'available_funds_label'):
                self.available_funds_label.setText(f"{available_funds:,.2f} USDT")
                self.available_funds_label.setStyleSheet("color: white; font-weight: bold;")

            # Total Trading Value (4열)
            total_trading_value = data.get("total_trading_value")
            if total_trading_value is not None and hasattr(self, 'total_trading_value_label'):
                color = "#FFFFFF"
                if isinstance(initial_capital, (int, float)) and initial_capital > 0:
                    if total_trading_value > initial_capital + 1e-6:
                        color = "#00C853"
                    elif total_trading_value < initial_capital - 1e-6:
                        color = "#FF1744"
                self.total_trading_value_label.setText(f"{total_trading_value:,.2f} USDT")
                self.total_trading_value_label.setStyleSheet(f"color: {color}; font-weight: bold;")

            # Cumulative Return % (5열)
            cumulative_return = data.get("cumulative_return_percent")
            if cumulative_return is not None and hasattr(self, 'cumulative_return_label'):
                if cumulative_return >= 0:
                    text = f"+{cumulative_return:.2f} %"
                    color = "#00C853"
                else:
                    text = f"{cumulative_return:.2f} %"
                    color = "#FF1744"
                self.cumulative_return_label.setText(text)
                self.cumulative_return_label.setStyleSheet(f"color: {color}; font-weight: bold;")

            # Global trading session (5열)
            global_session = data.get("global_session")
            global_time = data.get("global_time")
            # global_time은 _update_kst_time()에서 자동으로 업데이트되므로 여기서는 백엔드가 보낸 경우에만 업데이트
            if global_time and hasattr(self, 'global_session_time_label'):
                self.global_session_time_label.setText(global_time)
            if global_session and hasattr(self, 'global_session_message_label'):
                self.global_session_message_label.setText(global_session)
                # 겹침 세션인 경우 색상 강조
                if "겹침" in global_session:
                    self.global_session_message_label.setStyleSheet("color: #e16476; font-weight: bold;")
                else:
                    self.global_session_message_label.setStyleSheet("color: white; font-weight: bold;")
        except Exception as e:
            print(f"HeaderWidget 업데이트 오류: {e}")