"""실시간 랭킹리스트 테이블 위젯"""
from typing import List, Dict, Any, Optional, Set, Tuple
from .analysis_state import AnalysisState, state_label, state_style
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHBoxLayout, 
    QWidget, QCheckBox, QAbstractItemView, QHeaderView, QLabel, QPushButton
)


def format_change_percent(value: float) -> str:
    """상승률 포맷팅"""
    return f"{value:+07.2f}%"


class RankingTableWidget(QTableWidget):
    """실시간 랭킹리스트 테이블 위젯"""
    
    # 시그널 정의
    symbol_clicked = Signal(str)  # 심볼 클릭 시
    analyze_requested = Signal(str)  # 분석 요청 시
    backtest_requested = Signal(str)  # 백테스트 요청 시
    strategy_analysis_requested = Signal(str)  # 전략 분석 요청 시
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(0, 6, parent)
        
        # 헤더 설정
        self.setHorizontalHeaderLabels(["선택", "전략 백테스팅", "코인 심볼", "상승률%", "누적", "상승 유형"])
        
        # 컬럼 너비 설정
        self._setup_column_widths()
        
        # 테이블 설정
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 체크박스 참조 추적
        self._checkboxes: List[QCheckBox] = []

        # 전략 분석 버튼 관리: symbol -> QPushButton
        # populate() 리프레시가 반복되더라도 버튼/상태를
        # 유지하여 "분석중..." 상태가 중간에 초기화되지 않도록 함
        self._analysis_buttons: Dict[str, QPushButton] = {}
        # 전략 분석 상태 저장: symbol -> AnalysisState
        self._analysis_states: Dict[str, AnalysisState] = {}
        
        # 깜빡임 효과
        self._blink_cells: Set[Tuple[int, int]] = set()
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._toggle_blink)
        self._blink_timer.start(800)
        self._blink_visible = True
        self._blink_state = True
        
        # 셀 클릭 이벤트
        self.cellClicked.connect(self._on_cell_clicked)
    
    def _setup_column_widths(self):
        """컬럼 너비 비율 설정"""
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # 선택: 5%
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # 거래 적합성: 18%
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # 심볼: 23%
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # 상승률: 15%
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # 누적: 15%
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)  # 유형: 24%
        self._update_column_widths()
    
    def _update_column_widths(self):
        """현재 테이블 너비에 맞춰 컬럼 너비 업데이트"""
        total_width = self.viewport().width()
        if total_width <= 0:
            total_width = 800
        
        header = self.horizontalHeader()
        header.resizeSection(0, int(total_width * 0.05))
        header.resizeSection(1, int(total_width * 0.18))
        header.resizeSection(2, int(total_width * 0.23))
        header.resizeSection(3, int(total_width * 0.15))
        header.resizeSection(4, int(total_width * 0.15))
        header.resizeSection(5, int(total_width * 0.24))
    
    def resizeEvent(self, event):
        """테이블 크기 변경 시 컬럼 비율 유지"""
        super().resizeEvent(event)
        self._update_column_widths()
    
    def populate(self, items: List[Dict[str, Any]]):
        """데이터로 테이블 채우기"""
        # 상승률 기준 정렬 후 상위 100개
        items = sorted(items, key=lambda x: (-x.get("change_percent", 0.0), x.get("symbol", "")))
        top_items = items[:100]
        self.setRowCount(len(top_items))
        
        # 초기화 (체크박스/깜빡임 상태만 리셋)
        self._checkboxes.clear()
        self._blink_cells.clear()
        
        for i, item in enumerate(top_items):
            # ========================================
            # 백테스트 상태 초기화 (없으면 기본값)
            # ========================================
            if "backtest_status" not in item:
                item["backtest_status"] = "대기"
            if "backtest_score" not in item:
                item["backtest_score"] = 0
            
            # 선택 체크박스 (컬럼 0)
            chk = QCheckBox()
            symbol = item.get("symbol", "")
            chk.setProperty("symbol", symbol)
            self._checkboxes.append(chk)
            
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.setCellWidget(i, 0, chk_widget)
            
            # ========================================
            # 전략 백테스팅 (컬럼 1) - "전략 분석" 버튼
            #   - 기존 버튼/상태가 있으면 재사용하여
            #     LOADING/RUNNING 상태가 테이블 리프레시로
            #     초기화되지 않도록 함
            # ========================================
            existing_btn = self._analysis_buttons.get(symbol)
            if existing_btn is not None:
                button = existing_btn
                # 현재 저장된 상태로 텍스트/스타일 재적용
                state = self._analysis_states.get(symbol, AnalysisState.IDLE)
                self.set_analysis_state(symbol, state)
            else:
                button = self._create_strategy_analysis_button(symbol)
            button_widget = QWidget()
            button_layout = QHBoxLayout(button_widget)
            button_layout.addWidget(button)
            button_layout.setAlignment(Qt.AlignCenter)
            button_layout.setContentsMargins(0, 0, 0, 0)
            self.setCellWidget(i, 1, button_widget)
            
            # 코인 심볼 (컬럼 2) - 위젯
            days_since_listing = item.get("days_since_listing", 999)
            listing_signal_status = item.get("listing_signal_status", "NORMAL")
            
            symbol_widget = self._create_symbol_widget(symbol, days_since_listing, listing_signal_status)
            url = item.get("url") or f"https://www.binance.com/en/futures/{symbol}"
            symbol_widget.setProperty("url", url)
            symbol_widget.setProperty("symbol", symbol)
            self.setCellWidget(i, 2, symbol_widget)
            
            # 강력한 매수 신호 시 깜빡임
            if listing_signal_status == "STRONG_BUY" and days_since_listing <= 30:
                self._blink_cells.add((i, 2))
            
            # 상승률% (컬럼 3)
            cp = float(item.get("change_percent", 0.0))
            cp_item = QTableWidgetItem(format_change_percent(cp))
            cp_item.setTextAlignment(Qt.AlignCenter)
            cp_item.setForeground(QColor("#03b662" if cp > 0 else "#e16476" if cp < 0 else "#3c3c3c"))
            font = QFont()
            font.setBold(True)
            cp_item.setFont(font)
            self.setItem(i, 3, cp_item)
            
            # 누적 (컬럼 4)
            cumulative_raw = item.get("cumulative_percent", 0.0)
            if isinstance(cumulative_raw, str) and cumulative_raw == "+000.00":
                cum_item = QTableWidgetItem("+000.00")
                cum_item.setTextAlignment(Qt.AlignCenter)
                cum_item.setForeground(QColor("#3c3c3c"))
            else:
                cumulative_percent = float(cumulative_raw)
                cum_item = QTableWidgetItem(format_change_percent(cumulative_percent))
                cum_item.setTextAlignment(Qt.AlignCenter)
                cum_item.setForeground(QColor("#03b662" if cumulative_percent > 0 else "#e16476" if cumulative_percent < 0 else "#3c3c3c"))
            font = QFont()
            font.setBold(True)
            cum_item.setFont(font)
            self.setItem(i, 4, cum_item)
            
            # 상승유형 (컬럼 5)
            energy_type = item.get("energy_type", "데이터수신중")
            energy_item = QTableWidgetItem(energy_type)
            energy_item.setTextAlignment(Qt.AlignCenter)
            
            # 상승유형별 색상
            color_map = {
                "데이터수신중": "#000000",
                "데이터 분석 중": "#1e88e5",
                "급등": "#03b662",
                "지속 상승": "#8ad7b5",
                "횡보": "#ecd151",
                "지속 하락": "#ff8c25",
                "급락": "#e16476"
            }
            energy_item.setForeground(QColor(color_map.get(energy_type, "#000000")))
            font = QFont()
            font.setBold(True)
            energy_item.setFont(font)
            self.setItem(i, 5, energy_item)
            
            # 랭크 변화 시 깜빡임
            if item.get('rank_change', 0) >= 3:
                self._blink_cells.add((i, 5))
    
    def _create_symbol_widget(self, symbol: str, days: int, status: str) -> QWidget:
        """심볼 위젯 생성 (신규상장 표시 포함)"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)
        
        # 심볼 라벨 (좌측 정렬)
        symbol_label = QLabel(symbol)
        symbol_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        layout.addWidget(symbol_label, alignment=Qt.AlignLeft)
        
        # 신규상장 텍스트 라벨 (우측 정렬)
        if days <= 30:
            listing_text = self._get_listing_text(days, status)
            if listing_text:
                # 좌우 공간을 채우기 위한 Stretch 추가
                layout.addStretch()
                
                text_label = QLabel(listing_text)
                text_label.setStyleSheet("""
                    color: #1e88e5;
                    font-size: 9px;
                    font-weight: 900;
                    background: transparent;
                """)
                layout.addWidget(text_label, alignment=Qt.AlignRight)
        else:
            # 신규상장이 아닌 경우에도 stretch로 심볼을 좌측에 고정
            layout.addStretch()
        
        # 배경색 설정
        widget_style = self._get_widget_background_style(days, status)
        if widget_style:
            widget.setStyleSheet(widget_style)
        
        return widget
    
    def _get_listing_text(self, days_since_listing: int, signal_status: str) -> str:
        """신규 상장 텍스트 반환"""
        if signal_status == "STRONG_DECLINE":
            return "하락"
        elif days_since_listing <= 30:
            return f"new {days_since_listing}일"  # ✅ 'new N일' 형식
        else:
            return ""
    
    def _get_widget_background_style(self, days_since_listing: int, signal_status: str) -> str:
        """위젯 전체 배경 스타일 반환"""
        if signal_status == "STRONG_DECLINE":
            return """
                QWidget {
                    background-color: #3c3c3c;
                    border-radius: 4px;
                }
            """
        elif days_since_listing <= 30:
            return """
                QWidget {
                    background-color: #b9f2f9;
                    border-radius: 4px;
                }
            """
        else:
            return ""  # 일반 코인 - 배경 없음
    
    def _create_strategy_analysis_button(self, symbol: str) -> QPushButton:
        """전략 분석 버튼 생성"""
        button = QPushButton()
        button.setProperty("symbol", symbol)

        # 저장 및 초기 상태
        self._analysis_buttons[symbol] = button
        self._analysis_states[symbol] = AnalysisState.IDLE

        # 버튼 초기 표시 및 스타일 적용
        button.setText(state_label(AnalysisState.IDLE))
        style = state_style(AnalysisState.IDLE)
        if style:
            button.setStyleSheet(style)

        # 클릭 이벤트 연결
        button.clicked.connect(lambda _, s=symbol: self._on_strategy_analysis_clicked(s))

        return button

    def set_analysis_state(self, symbol: str, state: AnalysisState):
        """외부에서 호출하여 지정 심볼의 분석 버튼 상태 업데이트"""
        btn = self._analysis_buttons.get(symbol)
        if not btn:
            return

        # 저장
        self._analysis_states[symbol] = state

        # 텍스트 및 스타일 업데이트
        btn.setText(state_label(state))
        style = state_style(state)
        if style:
            btn.setStyleSheet(style)

        # 활성화/비활성화 로직
        if state in (AnalysisState.LOADING, AnalysisState.RUNNING):
            btn.setEnabled(False)
        else:
            btn.setEnabled(True)
    
    def _on_strategy_analysis_clicked(self, symbol: str):
        """전략 분석 버튼 클릭"""
        current = self._analysis_states.get(symbol, AnalysisState.IDLE)
        print(f"[RANKING_TABLE] 🔬 전략 분석 버튼 클릭: {symbol} (현재상태={current})")

        # 중복 요청 방지: LOADING/RUNNING 중에는 무시
        if current in (AnalysisState.LOADING, AnalysisState.RUNNING):
            print(f"[RANKING_TABLE] 이미 요청중이거나 분석중입니다: {symbol}")
            return

        # 즉시 UI 반영: 요청중
        self.set_analysis_state(symbol, AnalysisState.LOADING)

        # 신호 전파: 실제 분석은 외부에서 처리
        self.strategy_analysis_requested.emit(symbol)
    
    def _on_cell_clicked(self, row: int, col: int):
        """셀 클릭 처리"""
        print(f"[RANKING_TABLE] 셀 클릭: row={row}, col={col}")
        
        # 심볼 추출
        symbol_widget = self.cellWidget(row, 2)
        if not symbol_widget:
            print(f"[RANKING_TABLE] ❌ symbol_widget이 None입니다!")
            return
        
        symbol = symbol_widget.property("symbol")
        if not symbol:
            print(f"[RANKING_TABLE] ❌ symbol property가 None입니다!")
            return
        
        print(f"[RANKING_TABLE] 심볼 추출 성공: {symbol}")
        
        if col == 2:  # 심볼 컬럼 - 바이낸스 페이지 열기
            url = symbol_widget.property("url")
            if url:
                print(f"[RANKING_TABLE] 🌐 바이낸스 페이지 열기: {url}")
                import webbrowser
                webbrowser.open(url)
        elif col in [3, 4, 5]:  # 상승률/누적/유형 - 분석 + 백테스트 동시 실행!
            print(f"[RANKING_TABLE] 📊 분석 + 백테스트 요청: {symbol}")
            
            # 1️⃣ 기존 분석 (2열 업데이트)
            self.analyze_requested.emit(symbol)
            
            # 2️⃣ 백테스트 실행 (컬럼 1 업데이트)
            # NOTE: 사용자 의도에 따라 '컬럼 클릭'은 Coin Momentum & Chart 분석(분석 요청)만 수행해야 합니다.
            # 백테스트(전략 백테스팅)는 반드시 컬럼 1의 '전략 분석' 버튼에 의해서만 트리거되어야 하므로
            # 여기서는 백테스트 신호를 발생시키지 않습니다.
    
    def _toggle_blink(self):
        """깜빡임 효과 토글"""
        self._blink_state = not self._blink_state
        for row, col in self._blink_cells:
            if col == 2:  # 심볼 위젯
                widget = self.cellWidget(row, col)
                if widget:
                    if self._blink_state:
                        widget.setStyleSheet("background-color: #fff3cd;")
                    else:
                        widget.setStyleSheet("background-color: transparent;")
            else:  # 일반 아이템
                item = self.item(row, col)
                if item:
                    if self._blink_state:
                        item.setBackground(QColor("#fff3cd"))
                    else:
                        item.setBackground(QColor("transparent"))
    
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
