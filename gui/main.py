import sys
import os
import requests
import threading
from datetime import datetime
from typing import Optional
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QMessageBox, QLabel, QTabWidget, QPushButton, QSplitter
)
from PySide6.QtCore import Slot, Signal, Qt, QTimer

# --- 경로 설정 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# 위젯 임포트
from gui.widgets.analysis_state import AnalysisState
from gui.widgets.header_widget import HeaderWidget
from gui.widgets.footer_engines_widget import MiddleSessionWidget
from gui.widgets.ranking_table_widget import RankingTableWidget
from gui.widgets.surge_prediction_widget import SurgePredictionWidget
from gui.widgets.blacklist_widgets import SettlingTableWidget, BlacklistTableWidget
from gui.widgets.position_analysis_widgets import TrendAnalysisWidget, TimingAnalysisView
from gui.widgets.strategy_analysis_dialog import StrategyAnalysisDialog
from utils.ws_client import WebSocketClient
from backend.utils.logger import setup_logger # 백엔드 로거를 공유

# 백엔드 설정
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8200
BASE_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
WS_URL = f"ws://{BACKEND_HOST}:{BACKEND_PORT}/ws"
# 백테스팅 전용 엔드포인트 (GUI가 백테스팅 서버를 직접 호출하도록 함)
BACKTEST_BASE_URL = "http://127.0.0.1:8001"

class YONAMainWindow(QMainWindow):
    # Signal 선언 (스레드 안전한 통신용)
    blacklist_data_received = Signal(list)
    analysis_ready = Signal(object)  # 분석 데이터 수신 시그널
    backtest_completed = Signal(str, str, float, dict)  # symbol, suitability, score, metrics
    backtest_failed = Signal(str, str)  # symbol, error
    strategy_engine_assigned = Signal(str, dict)  # 엔진 배치 시 (engine_name, strategy_data)
    
    def __init__(self):
        super().__init__()
        self.logger = setup_logger()
        self.setWindowTitle("YONA Vanguard Futures (new)")
        self.setGeometry(100, 100, 1400, 900)

        # 분석 관련 변수
        self.selected_symbol = ""
        self._analysis_inflight = False
        self._blacklist_loading = False
        # 앱 전체 시작 여부 (START 버튼 클릭 전에는 중단 세션/푸터 비활성)
        self._app_started = False
        
        # 시간 고정 관련 변수
        self.fixed_time: Optional[datetime] = None

        self._init_ui()
        self._init_ws_client()
        self._init_timers()
        
        # Signal 연결
        self.blacklist_data_received.connect(self._update_blacklist_table)
        self.analysis_ready.connect(self._apply_analysis_data)  # 분석 데이터 수신 시 UI 업데이트
        self.backtest_completed.connect(self._on_backtest_completed)
        self.backtest_failed.connect(self._on_backtest_failed)
        self.strategy_engine_assigned.connect(self._on_strategy_engine_assigned)  # 전략 엔진 배치

        self.logger.info("GUI 메인 윌도우 초기화 완료.")

    def _init_ui(self):
        """UI의 기본 레이아웃을 설정합니다."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 헤더 위젯 (상단 10%)
        self.header_widget = HeaderWidget(self)
        main_layout.addWidget(self.header_widget, 10)

        # 2. 중앙 영역 - 2열 구조 (중단 세션 50%)
        middle_splitter = QSplitter(Qt.Horizontal)
        
        # 2-1. 1열 (좌측 63%): 탭 위젯
        self.tab_widget = QTabWidget()
        
        # 탭 1: Real-time Ranking List
        ranking_tab = QWidget()
        ranking_layout = QVBoxLayout(ranking_tab)
        ranking_layout.setContentsMargins(5, 5, 5, 5)
        ranking_layout.setSpacing(5)
        # 실시간 랭킹리스트 섹션만 남김
        ranking_section = QWidget()
        ranking_section_layout = QVBoxLayout(ranking_section)
        ranking_section_layout.setContentsMargins(0, 0, 0, 0)
        # 헤더 행
        ranking_header = QHBoxLayout()
        ranking_title = QLabel("Real-time Ranking List")
        ranking_title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px; color: #000000;")
        ranking_header.addWidget(ranking_title)
        ranking_header.addStretch()
        
        # 시간 고정 UI 추가
        self.fixed_time_label = QLabel("[--:--:--]")
        self.fixed_time_label.setAlignment(Qt.AlignCenter)
        self.fixed_time_label.setStyleSheet("font-size: 11px; padding: 4px;")
        ranking_header.addWidget(self.fixed_time_label)
        
        self.time_fix_button = QPushButton("[시간고정]")
        self.time_fix_button.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 4px 8px; border-radius: 4px; border: none; font-size: 11px; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        self.time_fix_button.clicked.connect(self._on_time_fix_clicked)
        ranking_header.addWidget(self.time_fix_button)
        
        ranking_header.addStretch()
        
        self.add_button = QPushButton("[추가]")
        self.add_button.setStyleSheet("background-color: #e16476; color: white; font-weight: bold; padding: 4px 8px;")
        self.add_button.clicked.connect(self._on_add_blacklist)
        ranking_header.addWidget(self.add_button)
        ranking_section_layout.addLayout(ranking_header)
        # 랭킹 테이블
        self.ranking_table = RankingTableWidget(self)
        self.ranking_table.analyze_requested.connect(self._on_analyze_symbol)
        self.ranking_table.backtest_requested.connect(self._on_backtest_requested)  # ✨ 추가
        self.ranking_table.strategy_analysis_requested.connect(self._on_strategy_analysis_requested)  # 전략 분석 요청
        ranking_section_layout.addWidget(self.ranking_table)
        ranking_layout.addWidget(ranking_section)
        # 탭 2: Settling update && Blacklist
        blacklist_tab = QWidget()
        blacklist_layout = QVBoxLayout(blacklist_tab)
        blacklist_layout.setContentsMargins(5, 5, 5, 5)
        # SETTLING 섹션 (상단 30%)
        settling_section = QWidget()
        settling_section_layout = QVBoxLayout(settling_section)
        settling_header = QHBoxLayout()
        settling_title = QLabel("Settling update")
        settling_title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px; color: #000000;")
        settling_header.addWidget(settling_title)
        settling_header.addStretch()
        self.add_settling_button = QPushButton("[추가]")
        self.add_settling_button.setStyleSheet("background-color: #e16476; color: white; font-weight: bold; padding: 4px 8px;")
        self.add_settling_button.clicked.connect(self._on_add_settling_blacklist)
        settling_header.addWidget(self.add_settling_button)
        settling_section_layout.addLayout(settling_header)
        self.settling_table = SettlingTableWidget(self)
        settling_section_layout.addWidget(self.settling_table)
        # 블랙리스트 섹션 (하단 70%)
        blacklist_section = QWidget()
        blacklist_section_layout = QVBoxLayout(blacklist_section)
        blacklist_header = QHBoxLayout()
        blacklist_title = QLabel("Blacklist")
        blacklist_title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px; color: #000000;")
        blacklist_header.addWidget(blacklist_title)
        blacklist_header.addStretch()
        self.remove_button = QPushButton("[해지]")
        self.remove_button.setStyleSheet("background-color: #ff8c25; color: white; font-weight: bold; padding: 4px 8px;")
        self.remove_button.clicked.connect(self._on_remove_blacklist)
        blacklist_header.addWidget(self.remove_button)
        blacklist_section_layout.addLayout(blacklist_header)
        self.blacklist_table = BlacklistTableWidget(self)
        blacklist_section_layout.addWidget(self.blacklist_table)
        # 분할기로 30:70 비율
        blacklist_splitter = QSplitter(Qt.Vertical)
        blacklist_splitter.addWidget(settling_section)
        blacklist_splitter.addWidget(blacklist_section)
        blacklist_splitter.setStretchFactor(0, 30)
        blacklist_splitter.setStretchFactor(1, 70)
        blacklist_layout.addWidget(blacklist_splitter)
        # 탭 추가
        self.tab_widget.addTab(ranking_tab, "Real-time Ranking List")
        self.tab_widget.addTab(blacklist_tab, "Settling update && Blacklist")
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        middle_splitter.addWidget(self.tab_widget)
        
        # 2-2. 2열 (우측 37%): 포지션 진입 분석
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(5)
        
        # 포지션 진입 헤더
        entry_header = QHBoxLayout()
        self.entry_title = QLabel("Coin Momentum & Chart - ")
        self.entry_title.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.entry_symbol_label = QLabel("-")
        self.entry_symbol_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #FFC107;")
        entry_header.addWidget(self.entry_title)
        entry_header.addWidget(self.entry_symbol_label)
        entry_header.addStretch()
        
        right_layout.addLayout(entry_header)
        
        # 추세 분석 위젯
        self.trend_analysis = TrendAnalysisWidget(self)
        right_layout.addWidget(self.trend_analysis)
        
        # 타이밍 분석 차트
        self.analysis_view = TimingAnalysisView(self)
        right_layout.addWidget(self.analysis_view, 1)
        
        middle_splitter.addWidget(right_widget)
        
        # 2열 비율 설정 (63:37)
        middle_splitter.setStretchFactor(0, 63)
        middle_splitter.setStretchFactor(1, 37)
        
        main_layout.addWidget(middle_splitter, 50)

        # 3. 푸터 위젯 (하단 40%) - 알파/베타/감마 3개 자동매매 엔진
        self.middle_session_widget = MiddleSessionWidget(self)
        main_layout.addWidget(self.middle_session_widget, 40)
        
        # START/STOP 버튼 시그널 연결
        self.header_widget.start_signal.connect(self.on_start_clicked)
        self.header_widget.stop_signal.connect(self.on_stop_clicked)
        # 긴급 청산 버튼 시그널 연결
        self.header_widget.emergency_liquidation_signal.connect(self.on_emergency_liquidation_clicked)
        # Initial Investment 버튼
        self.header_widget.initial_investment_reset_signal.connect(self._on_reset_initial_investment)
        
        # 엔진 시작/정지 시그널 연결
        self.middle_session_widget.engine_start_signal.connect(self._on_engine_start)
        self.middle_session_widget.engine_stop_signal.connect(self._on_engine_stop)

    
    def _init_ws_client(self):
        """백엔드와 통신할 WebSocket 클라이언트를 초기화합니다."""
        self.ws_client = WebSocketClient(WS_URL)
        self.ws_client.message_received.connect(self._distribute_message)
        self.ws_client.start()
    
    def _init_timers(self):
        """타이머 초기화"""
        # 분석 타이머
        self.analysis_timer = QTimer(self)
        self.analysis_timer.setInterval(2000)
        self.analysis_timer.timeout.connect(self._on_analyze_timing)
        
        # 시간 고정 경과 시간 표시 타이머 (생성은 하지만 시작하지 않음)
        self.fixed_time_timer = QTimer(self)
        self.fixed_time_timer.timeout.connect(self._update_fixed_time_display)
    
    @Slot(dict)
    def _distribute_message(self, message: dict):
        """수신된 메시지를 적절한 하위 위젯으로 분배합니다."""
        msg_type = message.get("type")
        self.logger.debug(f"WebSocket 메시지 수신: {msg_type}")

        # 헤더 위젯 메시지 처리
        if hasattr(self.header_widget, 'handle_message'):
            self.header_widget.handle_message(message)
        
        # START 이전에는 헤더/긴급/에러만 처리하고 나머지는 무시
        if not self._app_started:
            if msg_type == "EMERGENCY_LIQUIDATION":
                self._handle_emergency_liquidation(message.get("data", {}))
            elif msg_type == "CRITICAL_ERROR":
                self.handle_critical_error(message.get("title", "오류"), message.get("message", "알 수 없는 오류"))
            # 헤더 업데이트에서 Account total balance만 푸터 위젯에 반영하는 것은 허용
            if msg_type == "HEADER_UPDATE":
                header_data = message.get("data", {})
                available_funds = header_data.get("available_funds", 0.0)
                self.middle_session_widget.alpha_engine.set_account_total_balance(available_funds)
                self.middle_session_widget.beta_engine.set_account_total_balance(available_funds)
                self.middle_session_widget.gamma_engine.set_account_total_balance(available_funds)
            return

        # HEADER_UPDATE 메시지 처리 - Account total balance를 엔진 위젯에 전달 (START 이후에도 유지)
        if msg_type == "HEADER_UPDATE":
            header_data = message.get("data", {})
            available_funds = header_data.get("available_funds", 0.0)
            # 각 엔진 위젯에 Account total balance 전달
            self.middle_session_widget.alpha_engine.set_account_total_balance(available_funds)
            self.middle_session_widget.beta_engine.set_account_total_balance(available_funds)
            self.middle_session_widget.gamma_engine.set_account_total_balance(available_funds)

        # 중단 세션/푸터 메시지 처리 (START 이후에만)
        if hasattr(self.middle_session_widget, 'handle_message'):
            self.middle_session_widget.handle_message(message)
        # 메시지 타입별 처리 (START 이후)
        if msg_type == "BINANCE_LIVE_RANKING" or msg_type == "RANKING_UPDATE":
            items = message.get("data", [])
            self.ranking_table.populate(items)
        elif msg_type == "SETTLING_UPDATE":
            settling_data = message.get("data", [])
            self.settling_table.populate(settling_data)
        elif msg_type == "TIMING_ANALYSIS_UPDATE":
            analysis_data = message.get("data", {})
            self._apply_analysis_data(analysis_data)
        elif msg_type == "EMERGENCY_LIQUIDATION":
            self._handle_emergency_liquidation(message.get("data", {}))
        elif msg_type == "CRITICAL_ERROR":
            self.handle_critical_error(message.get("title", "오류"), message.get("message", "알 수 없는 오류"))
    
    def _handle_emergency_liquidation(self, data: dict):
        """긴급 포지션 청산 결과 처리 및 사용자 피드백"""
        status = data.get("status")
        msg = data.get("message", "")
        
        if status == "success":
            closed_count = data.get("closed_count", 0)
            closed_positions = data.get("closed_positions", [])
            
            # 청산된 포지션 목록 생성
            position_details = "\n".join([
                f"  • {p['symbol']}: {p['amount']:.4f} ({p['side']})"
                for p in closed_positions
            ]) if closed_positions else "  없음"
            
            QMessageBox.information(
                self,
                "✅ 긴급 포지션 청산 완료",
                f"{msg}\n\n청산된 포지션 ({closed_count}개):\n{position_details}"
            )
            self.logger.info(f"긴급 청산 성공: {closed_count}개 포지션")
            
        elif status == "partial_failure":
            errors = data.get("errors", [])
            
            # 실패한 포지션 목록 생성
            error_details = "\n".join([
                f"  • {e['symbol']}: {e['error']}"
                for e in errors
            ]) if errors else "  알 수 없는 오류"
            
            QMessageBox.warning(
                self,
                "⚠️ 긴급 포지션 청산 부분 실패",
                f"{msg}\n\n실패한 포지션 ({len(errors)}개):\n{error_details}\n\n"
                "성공한 포지션은 정상적으로 청산되었습니다."
            )
            self.logger.warning(f"긴급 청산 부분 실패: {len(errors)}개 포지션 실패")
            
        else:  # error
            QMessageBox.critical(
                self,
                "❌ 긴급 포지션 청산 오류",
                f"{msg}\n\n포지션 청산 중 오류가 발생했습니다.\n"
                "바이낸스 계정을 직접 확인하시기 바랍니다."
            )
            self.logger.error(f"긴급 청산 오류: {msg}")
    
    @Slot(object)
    def _apply_analysis_data(self, data: dict):
        """분석 데이터를 위젯에 적용 (UI 스레드에서 실행됨)"""
        try:
            print(f"[MAIN] 📊 분석 데이터 적용 시작 (UI 스레드)")
            
            # 추세 분석
            trend = data.get("trend_analysis", {})
            if trend:
                print(f"[MAIN] 🎯 추세 분석 업데이트: {trend.get('overall', 'N/A')}")
                self.trend_analysis.update_trend(trend)
            
            # 차트
            print(f"[MAIN] 📈 차트 데이터 업데이트")
            self.analysis_view.set_data(data)
            print(f"[MAIN] ✅ 분석 데이터 적용 완료")
            
        except Exception as e:
            print(f"[MAIN] ❌분석 데이터 적용 오류: {e}")
            self.logger.error(f"분석 데이터 적용 오류: {e}")

    @Slot()
    def on_start_clicked(self):
        """START 버튼 클릭 시 백엔드에 API 요청"""
        try:
            response = requests.post(f"{BASE_URL}/api/v1/start", timeout=5)
            response.raise_for_status()
            self.logger.info("백엔드에 START 명령 전송 완료.")
            self._app_started = True
        except requests.exceptions.RequestException as e:
            self.logger.error(f"START 명령 전송 실패: {e}")
            self.handle_critical_error("연결 오류", "백엔드에 START 명령을 보낼 수 없습니다.")

    @Slot()
    def on_stop_clicked(self):
        """STOP 버튼 클릭 시 분석 중지 (긴급 청산 없이)"""
        try:
            response = requests.post(f"{BASE_URL}/api/v1/stop", timeout=5)
            response.raise_for_status()
            self.logger.info("백엔드에 STOP 명령 전송 완료.")
            # 전체 앱 비활성 처리: 중단 세션/푸터 메시지 무시, 타이머 정지
            self._app_started = False
            if hasattr(self, 'analysis_timer') and self.analysis_timer.isActive():
                self.analysis_timer.stop()
            self.selected_symbol = ""
        except requests.exceptions.RequestException as e:
            self.logger.error(f"STOP 명령 전송 실패: {e}")
            QMessageBox.critical(
                self,
                "연결 오류",
                f"백엔드 서버와 통신할 수 없습니다.\n\n오류: {str(e)}"
            )
    
    @Slot()
    def on_emergency_liquidation_clicked(self):
        """긴급 청산 버튼 클릭 시 모든 포지션 시장가 청산"""
        # 긴급 청산 확인 다이얼로그
        reply = QMessageBox.warning(
            self,
            "⚠️ 긴급 포지션 청산",
            "모든 활성 포지션을 시장가로 즉시 청산합니다.\n"
            "이 작업은 되돌릴 수 없습니다.\n\n"
            "계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            self.logger.info("사용자가 긴급 청산을 취소했습니다.")
            return
        
        try:
            # 긴급 청산 API 호출
            response = requests.post(f"{BASE_URL}/api/v1/emergency/liquidate", timeout=10)
            response.raise_for_status()
            self.logger.info("긴급 청산 명령 전송 완료.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"긴급 청산 명령 전송 실패: {e}")
            QMessageBox.critical(
                self,
                "연결 오류",
                f"백엔드 서버와 통신할 수 없습니다.\n\n오류: {str(e)}"
            )
    
    @Slot(str)
    def _on_engine_start(self, engine_name: str):
        """특정 엔진 시작 요청"""
        if not self._app_started:
            QMessageBox.information(self, "앱 대기 상태", "먼저 상단의 START 버튼을 눌러주세요.")
            return
        try:
            # NewModular 엔진은 별도 API 사용
            if engine_name == "NewModular":
                response = requests.post(
                    f"{BASE_URL}/api/v1/strategy/new/start",
                    json={
                        "symbol": "BTCUSDT",  # 기본값, 추후 설정에서 가져오기
                        "leverage": 10,
                        "quantity": None
                    },
                    timeout=5
                )
            else:
                # Alpha/Beta/Gamma 엔진: GUI에서 선택된 심볼 가져오기
                selected_symbol = None
                if engine_name == "Alpha":
                    selected_symbol = self.middle_session_widget.alpha_engine.selected_symbol
                elif engine_name == "Beta":
                    selected_symbol = self.middle_session_widget.beta_engine.selected_symbol
                elif engine_name == "Gamma":
                    selected_symbol = self.middle_session_widget.gamma_engine.selected_symbol
                
                # 심볼이 지정되지 않았으면 기본값 사용
                if not selected_symbol:
                    selected_symbol = "BTCUSDT"
                    self.logger.warning(f"{engine_name} 엔진 심볼 미지정, 기본값 사용: {selected_symbol}")
                
                response = requests.post(
                    f"{BASE_URL}/api/v1/engine/start",
                    json={"engine": engine_name, "symbol": selected_symbol},
                    timeout=5
                )
            response.raise_for_status()
            self.logger.info(f"{engine_name} 엔진 시작 요청 완료.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"{engine_name} 엔진 시작 실패: {e}")
            QMessageBox.warning(self, "엔진 시작 실패", f"{engine_name} 엔진을 시작할 수 없습니다.")
    
    @Slot(str)
    def _on_engine_stop(self, engine_name: str):
        """특정 엔진 정지 요청"""
        if not self._app_started:
            # 대기 상태에서도 개별 엔진 정지는 보낼 필요 없음
            return
        try:
            # NewModular 엔진은 별도 API 사용
            if engine_name == "NewModular":
                response = requests.post(
                    f"{BASE_URL}/api/v1/strategy/new/stop",
                    json={"force": False},  # 포지션 보유 시 경고
                    timeout=5
                )
            else:
                response = requests.post(
                    f"{BASE_URL}/api/v1/engine/stop",
                    json={"engine": engine_name},
                    timeout=5
                )
            response.raise_for_status()
            self.logger.info(f"{engine_name} 엔진 정지 요청 완료.")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"{engine_name} 엔진 정지 실패: {e}")
            QMessageBox.warning(self, "엔진 정지 실패", f"{engine_name} 엔진을 정지할 수 없습니다.")
            self.handle_critical_error("연결 오류", "백엔드에 STOP 명령을 보낼 수 없습니다.")
    
    # 급등 예상 코인 기능 완전 삭제
    
    def _on_analyze_symbol(self, symbol: str):
        """랭킹 테이블에서 분석 요청"""
        if not self._app_started:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "앱 대기 상태", "먼저 START 버튼을 눌러 분석을 시작하세요.")
            return
        print(f"[MAIN] _on_analyze_symbol 호출됨: symbol={symbol}")
        self.selected_symbol = symbol
        
        # 헤더 심볼 라벨 업데이트
        self.entry_symbol_label.setText(symbol)
        
        print(f"[MAIN] selected_symbol 설정: {self.selected_symbol}")
        self._start_analysis()
    
    def _start_analysis(self):
        """분석 시작"""
        print(f"[MAIN] _start_analysis 호출됨")
        self._analysis_inflight = False
        if not self.analysis_timer.isActive():
            print(f"[MAIN] ⏰ analysis_timer 시작")
            self.analysis_timer.start()
        else:
            print(f"[MAIN] ⏰ analysis_timer 이미 실행 중")
        self._on_analyze_timing()
    
    def _on_analyze_timing(self):
        """타이밍 분석 실행"""
        if not self.selected_symbol:
            print(f"[MAIN] ❌ selected_symbol이 없어서 분석을 건너뜁니다.")
            return
        
        symbol = self.selected_symbol
        print(f"[MAIN] 📊 타이밍 분석 시작: {symbol}")
        
        def worker():
            try:
                self._analysis_inflight = True
                print(f"[MAIN] 🌐 API 호출: /api/v1/live/analysis/entry?symbol={symbol}")
                response = requests.get(
                    f"{BASE_URL}/api/v1/live/analysis/entry",
                    params={"symbol": symbol},
                    timeout=5
                )
                if response.ok:
                    data = response.json().get("data", {})
                    print(f"[MAIN] ✅ API 응답 수신: {len(data)} keys")
                else:
                    print(f"[MAIN] ⚠️ API 실패 (status={response.status_code}), 기본 데이터 사용")
                    data = self._get_default_analysis_data(symbol)
            except Exception as e:
                print(f"[MAIN] ❌ API 오류: {e}, 기본 데이터 사용")
                data = self._get_default_analysis_data(symbol)
            finally:
                # Signal을 통해 UI 스레드에서 업데이트 (Qt 규칙 준수!)
                try:
                    print(f"[MAIN] 📡 analysis_ready Signal 발생")
                    self.analysis_ready.emit(data)
                except Exception as e:
                    print(f"[MAIN] ❌ Signal 발생 오류: {e}")
                self._analysis_inflight = False
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _get_default_analysis_data(self, symbol: str) -> dict:
        """기본 분석 데이터 (API 실패 시)"""
        return {
            "symbol": symbol,
            "score": 0,
            "series": {
                "close": [], "ema20": [], "ema50": [], 
                "vwap": [], "bpr": [], "vss": []
            },
            "trend_analysis": {
                "5m": {
                    "direction": "연결중", "strength": 0, 
                    "predicted_upside": 0.0, 
                    "price_status": {"status": "대기"}
                },
                "15m": {
                    "direction": "연결중", "strength": 0, 
                    "predicted_upside": 0.0, 
                    "price_status": {"status": "대기"}
                },
                "overall": "바이낸스 API 연결 중"
            },
            "levels": {"entry_zone": {}, "stop": None, "tp1": None, "tp2": None}
        }
    
    def _on_add_blacklist(self):
        """랭킹 테이블에서 선택된 심볼을 블랙리스트에 추가 (Binance Live vs1 패턴)"""
        try:
            symbols = self.ranking_table.get_checked_symbols()
            if not symbols:
                return
            
            response = requests.post(
                f"{BASE_URL}/api/v1/live/blacklist/add",
                json={"symbols": symbols},
                timeout=5
            )
            
            if response.status_code == 200:
                self.ranking_table.clear_all_checks()
                self._refresh_blacklist_tab()  # 헬퍼 메서드 사용
        except Exception as e:
            self.logger.error(f"블랙리스트 추가 실패: {e}")
    
    def _on_add_settling_blacklist(self):
        """SETTLING 테이블에서 선택된 심볼을 블랙리스트에 추가 (Binance Live vs1 패턴)"""
        try:
            symbols = self.settling_table.get_checked_symbols()
            if not symbols:
                return
            
            response = requests.post(
                f"{BASE_URL}/api/v1/live/blacklist/add",
                json={"symbols": symbols, "status": "SETTLING"},
                timeout=5
            )
            
            if response.status_code == 200:
                self.settling_table.clear_all_checks()
                self._refresh_blacklist_tab()  # 헬퍼 메서드 사용
        except Exception as e:
            self.logger.error(f"SETTLING 블랙리스트 추가 실패: {e}")
    
    def _on_remove_blacklist(self):
        """블랙리스트에서 선택된 심볼 제거 (Binance Live vs1 패턴)"""
        try:
            symbols = self.blacklist_table.get_checked_symbols()
            if not symbols:
                return
            
            response = requests.post(
                f"{BASE_URL}/api/v1/live/blacklist/remove",
                json={"symbols": symbols},
                timeout=5
            )
            
            if response.status_code == 200:
                self.blacklist_table.clear_all_checks()
                self._refresh_blacklist_tab()  # 헬퍼 메서드 사용
        except Exception as e:
            self.logger.error(f"블랙리스트 제거 실패: {e}")
    
    def _on_tab_changed(self, index: int):
        """탭 변경 시 호출"""
        if not self._app_started:
            return
        if index == 1:  # 블랙리스트 탭
            self._load_blacklist_data()
    
    def _load_blacklist_data(self):
        """블랙리스트 데이터 로딩 (Binance Live vs1 패턴)"""
        if self._blacklist_loading:
            return
        
        def worker():
            try:
                self._blacklist_loading = True
                response = requests.get(f"{BASE_URL}/api/v1/live/blacklist", timeout=5)
                
                if response.status_code == 200:
                    data = response.json().get("data", [])
                    # UI 스레드에서 업데이트 - Signal 방식으로 변경 (스레드 안전)
                    self.blacklist_data_received.emit(data)
            except Exception as e:
                self.logger.error(f"블랙리스트 로딩 실패: {e}")
            finally:
                self._blacklist_loading = False
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _update_blacklist_table(self, data):
        """블랙리스트 테이블 업데이트 (Signal 수신 핸들러)"""
        try:
            self.blacklist_table.populate(data)
            self.logger.info(f"블랙리스트 테이블 업데이트 완료: {len(data)}개 항목")
        except Exception as e:
            self.logger.error(f"블랙리스트 테이블 업데이트 실패: {e}")
    
    def _refresh_blacklist_tab(self):
        """블랙리스트 탭 새로고침 (Binance Live vs1 패턴)"""
        QTimer.singleShot(500, self._load_blacklist_data)

    def _on_time_fix_clicked(self) -> None:
        """시간 고정 버튼 클릭 이벤트 처리"""
        if self.fixed_time is None:
            # 시간 고정 시작
            self.fixed_time = datetime.utcnow()
            self.time_fix_button.setText("[고정해제]")
            threading.Thread(target=self._send_fixed_time, args=(self.fixed_time,), daemon=True).start()
            self.fixed_time_timer.start(1000)  # 1초마다 경과 시간 업데이트
            self.logger.info(f"시간 고정 시작: {self.fixed_time}")
        else:
            # 시간 고정 해제
            self.fixed_time = None
            self.time_fix_button.setText("[시간고정]")
            threading.Thread(target=self._send_fixed_time, args=(None,), daemon=True).start()
            self.fixed_time_timer.stop()
            self.fixed_time_label.setText("[--:--:--]")
            self.logger.info("시간 고정 해제")

    def _update_fixed_time_display(self) -> None:
        """시간 고정 후 경과 시간을 표시"""
        if self.fixed_time:
            elapsed = datetime.utcnow() - self.fixed_time
            hours, remainder = divmod(elapsed.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.fixed_time_label.setText(f"[{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}]")

    def _send_fixed_time(self, fixed_time: Optional[datetime] = None) -> None:
        """백엔드에 시간 고정 설정 전송"""
        try:
            data = {"fixed_time": fixed_time.isoformat() if fixed_time else None}
            response = requests.post(f"{BASE_URL}/api/v1/set-fixed-time", json=data, timeout=5)
            if response.status_code == 200:
                self.logger.info(f"시간 고정 설정 전송 완료: {data}")
            else:
                self.logger.warning(f"시간 고정 설정 실패: {response.status_code}")
        except Exception as e:
            self.logger.error(f"시간 고정 설정 전송 오류: {e}")
    
    def _on_reset_initial_investment(self):
        """Initial Investment 버튼 클릭 처리"""
        try:
            response = requests.post(f"{BASE_URL}/api/v1/account/initial/reset", timeout=8)
            response.raise_for_status()
            data = response.json().get("data", {})
            amount = data.get("initial_investment", 0.0)
            QMessageBox.information(
                self,
                "Initial Investment",
                f"초기 투자금이 {amount:,.2f} USDT로 설정되었습니다."
            )
            self.logger.info(f"Initial Investment 재설정 완료: {amount:.2f} USDT")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Initial Investment 재설정 실패: {e}")
            QMessageBox.warning(
                self,
                "설정 실패",
                "Binance 계좌 정보를 불러올 수 없습니다.\n네트워크 상태를 확인해 주세요."
            )

    def handle_critical_error(self, title: str, message: str):
        self.logger.critical(f"GUI - 치명적인 오류: [{title}] {message}")
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event):
        """메인 윈도우 종료 이벤트 처리"""
        self.logger.info("GUI 윈도우 종료 중...")
        
        # 타이머 정지
        if hasattr(self, 'analysis_timer'):
            self.analysis_timer.stop()
        if hasattr(self, 'fixed_time_timer'):
            self.fixed_time_timer.stop()
        
        # WebSocket 연결 종료
        if hasattr(self, 'ws_client'):
            self.ws_client.stop()
        
        event.accept()
    
    
    # ========================================
    # 백테스트 관련 핸들러
    # ========================================
    
    def _on_backtest_requested(self, symbol: str):
        """
        백테스트 시작 요청
        
        플로우:
        1. UI 상태 변경 (컬럼 1을 "분석중"으로)
        2. 백그라운드 스레드에서 API 호출
        3. 결과 수신 시 Signal로 UI 업데이트
        
        Args:
            symbol: 코인 심볼
        """
        print(f"[MAIN] 🔬 백테스트 시작: {symbol}")
        
        # 1. UI 상태 변경 (컬럼 1을 "분석중"으로)
        self._update_backtest_status(symbol, "분석중", 0)
        
        # 2. 백그라운드에서 백테스트 실행 (UI 블로킹 방지)
        def worker():
            try:
                print(f"[MAIN] 🌐 백테스트 API 호출: {symbol}")
                
                # API 호출 (타임아웃 30초 - 백테스트는 시간 소요)
                response = requests.get(
                    f"{BACKTEST_BASE_URL}/api/v1/backtest/suitability",
                    params={"symbol": symbol, "period": "1w"},
                    timeout=30
                )
                
                if response.ok:
                    data = response.json().get("data", {})
                    suitability = data.get("suitability", "부적합")
                    score = data.get("score", 0)
                    metrics = data.get("metrics", {})
                    cached = response.json().get("cached", False)
                    
                    cache_msg = "캐시" if cached else "신규"
                    print(f"[MAIN] ✅ 백테스트 완료 ({cache_msg}): {symbol} -> {suitability} ({score}점)")
                    
                    # UI 업데이트 (Signal 사용)
                    self.backtest_completed.emit(symbol, suitability, score, metrics)
                else:
                    error = f"API 오류 (status={response.status_code})"
                    print(f"[MAIN] ❌ 백테스트 실패: {symbol} -> {error}")
                    self.backtest_failed.emit(symbol, error)
            
            except requests.Timeout:
                error = "타임아웃 (30초 초과)"
                print(f"[MAIN] ⏱️ 백테스트 타임아웃: {symbol}")
                self.backtest_failed.emit(symbol, error)
            
            except Exception as e:
                error = str(e)
                print(f"[MAIN] ❌ 백테스트 예외: {symbol} -> {error}")
                self.backtest_failed.emit(symbol, error)
        
        # 데몬 스레드로 실행 (GUI 메인 스레드 블로킹 방지)
        threading.Thread(target=worker, daemon=True).start()
    
    def _update_backtest_status(self, symbol: str, status: str, score: float):
        """
        백테스트 상태 업데이트 (랭킹 테이블 컬럼 1)
        
        Args:
            symbol: 코인 심볼
            status: "대기" | "분석중" | "적합" | "부적합" | "주의 필요"
            score: 0~100 점수
        """
        # 테이블에서 해당 심볼 행 찾기
        for row in range(self.ranking_table.rowCount()):
            symbol_widget = self.ranking_table.cellWidget(row, 2)
            if symbol_widget and symbol_widget.property("symbol") == symbol:
                # 컬럼 1 (거래 적합성) 업데이트
                if status == "적합":
                    text = f"✅ 적합 ({score:.0f})"
                    color = "#03b662"
                elif status == "부적합":
                    text = f"❌ 부적합 ({score:.0f})"
                    color = "#e16476"
                elif status == "주의 필요":
                    text = f"⚠️ 주의 ({score:.0f})"
                    color = "#ff8c25"
                elif status == "분석중":
                    text = "⏳ 분석중..."
                    color = "#1e88e5"
                else:  # "대기"
                    text = "-"
                    color = "#3c3c3c"
                
                from PySide6.QtWidgets import QTableWidgetItem
                from PySide6.QtGui import QColor, QFont
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setForeground(QColor(color))
                font = QFont()
                font.setBold(True)
                item.setFont(font)
                self.ranking_table.setItem(row, 1, item)
                break
    
    def _on_backtest_completed(self, symbol: str, suitability: str, score: float, metrics: dict):
        """
        백테스트 완료 처리 (UI 스레드에서 실행)
        
        Args:
            symbol: 코인 심볼
            suitability: 적합성 ("적합" | "부적합" | "주의 필요")
            score: 점수 (0~100)
            metrics: 백테스트 메트릭 딕셔너리
        """
        print(f"[MAIN] 📊 백테스트 결과 UI 업데이트: {symbol} -> {suitability} ({score}점)")
        self._update_backtest_status(symbol, suitability, score)
    
    def _on_backtest_failed(self, symbol: str, error: str):
        """
        백테스트 실패 처리
        
        Args:
            symbol: 코인 심볼
            error: 에러 메시지
        """
        print(f"[MAIN] ❌ 백테스트 실패 UI 업데이트: {symbol} -> {error}")
        
        # 상태를 "대기"로 복원
        self._update_backtest_status(symbol, "대기", 0)
        
        # 사용자에게 경고 메시지
        QMessageBox.warning(
            self,
            "백테스트 실패",
            f"{symbol} 백테스트 실패:\n{error}"
        )
    
    # ========================================
    # 전략 분석 관련 핸들러
    # ========================================
    
    def _on_strategy_analysis_requested(self, symbol: str):
        """
        전략 분석 요청 처리
        
        플로우:
        1. 팝업창 표시 (로딩 인디케이터)
        2. 백그라운드 스레드에서 API 호출
        3. 결과 수신 시 팝업창 업데이트
        
        Args:
            symbol: 코인 심볼
        """
        print(f"[MAIN] 🔬 전략 분석 요청: {symbol}")

        # 팝업창 생성 (로딩 상태)
        dialog = StrategyAnalysisDialog(
            symbol=symbol,
            analysis_data={
                "best_engine": "분석중",
                "volatility": 0,
                "max_target_profit": {"alpha": 0, "beta": 0, "gamma": 0},
                "risk_management": {"stop_loss": 0, "trailing_stop": 0},
                "engine_results": {}
            },
            parent=self
        )

        # 엔진 배치 Signal 연결
        dialog.engine_assigned.connect(self._on_strategy_engine_assigned)

        # 팝업창 표시 (비동기 모달)
        dialog.show()

        # 버튼 상태: 요청 시작 (메인 스레드에서 LOADING -> RUNNING)
        try:
            # 이미 랭킹테이블 버튼은 클릭 시 LOADING으로 바뀌지만
            # 안전하게 RUNNING 상태로 전환하여 진행중 표기를 보장
            self.ranking_table.set_analysis_state(symbol, AnalysisState.RUNNING)
        except Exception:
            pass

        # 백그라운드에서 전략 분석 실행 (UI 블로킹 방지)
        def worker():
            try:
                print(f"[MAIN] 🌐 전략 분석 API 호출: {symbol}")

                # API 호출 (타임아웃 60초 - 3개 엔진 백테스팅은 시간 소요)
                response = requests.get(
                    f"{BACKTEST_BASE_URL}/api/v1/backtest/strategy-analysis",
                    params={"symbol": symbol, "period": "1w"},
                    timeout=60
                )

                if response.ok:
                    data = response.json().get("data", {})

                    print(f"[MAIN] ✅ 전략 분석 완료: {symbol} -> 추천 엔진: {data.get('best_engine', 'Unknown')}")

                    # 팝업창 업데이트: 워커 스레드에서 직접 UI를 조작하지 않고
                    # dialog.analysis_update 시그널을 emit 하여 메인 스레드에서 처리하게 함
                    try:
                        dialog.analysis_update.emit(data)
                    except Exception:
                        # If direct emit failed (rare), schedule a queued emit on main thread
                        try:
                            QTimer.singleShot(0, lambda d=data: dialog.analysis_update.emit(d))
                        except Exception:
                            # as a last resort, set data for later
                            dialog.analysis_data = data

                    # 버튼 상태: 완료 (마샬링)
                    try:
                        QTimer.singleShot(0, lambda s=symbol: self.ranking_table.set_analysis_state(s, AnalysisState.COMPLETED))
                    except Exception:
                        pass
                else:
                    error = f"API 오류 (status={response.status_code})"
                    print(f"[MAIN] ❌ 전략 분석 실패: {symbol} -> {error}")

                    # 에러 팝업 표시
                    QMessageBox.warning(
                        self,
                        "전략 분석 실패",
                        f"{symbol} 전략 분석 실패:\n{error}"
                    )
                    # 버튼 상태: 오류
                    try:
                        QTimer.singleShot(0, lambda s=symbol: self.ranking_table.set_analysis_state(s, AnalysisState.ERROR))
                    except Exception:
                        pass
                    dialog.reject()  # 팝업창 닫기

            except requests.Timeout:
                error = "타임아웃 (60초 초과)"
                print(f"[MAIN] ⏱️ 전략 분석 타임아웃: {symbol}")

                QMessageBox.warning(
                    self,
                    "전략 분석 타임아웃",
                    f"{symbol} 전략 분석 시간이 초과되었습니다.\n잠시 후 다시 시도해주세요."
                )
                dialog.reject()
                try:
                    QTimer.singleShot(0, lambda s=symbol: self.ranking_table.set_analysis_state(s, AnalysisState.ERROR))
                except Exception:
                    pass

            except Exception as e:
                error = str(e)
                print(f"[MAIN] ❌ 전략 분석 예외: {symbol} -> {error}")

                QMessageBox.warning(
                    self,
                    "전략 분석 오류",
                    f"{symbol} 전략 분석 중 오류 발생:\n{error}"
                )
                dialog.reject()
                try:
                    QTimer.singleShot(0, lambda s=symbol: self.ranking_table.set_analysis_state(s, AnalysisState.ERROR))
                except Exception:
                    pass

        # 데몬 스레드로 실행 (GUI 메인 스레드 블로킹 방지)
        threading.Thread(target=worker, daemon=True).start()
    
    def _on_strategy_engine_assigned(self, engine_name: str, strategy_data: dict):
        """
        전략 분석 후 엔진 배치 처리
        
        Args:
            engine_name: 엔진명 ("Alpha", "Beta", "Gamma")
            strategy_data: 전략 데이터 딕셔너리
        """
        symbol = strategy_data.get("symbol")
        analysis_data = strategy_data.get("analysis_data", {})

        # 중복 배치 방지: 동일 심볼이 이미 다른 엔진에 배치되어 있으면 경고 후 return
        alpha_symbol = self.middle_session_widget.alpha_engine.selected_symbol
        beta_symbol = self.middle_session_widget.beta_engine.selected_symbol
        gamma_symbol = self.middle_session_widget.gamma_engine.selected_symbol
        other_engines = []
        if engine_name != "Alpha" and alpha_symbol == symbol:
            other_engines.append("Alpha")
        if engine_name != "Beta" and beta_symbol == symbol:
            other_engines.append("Beta")
        if engine_name != "Gamma" and gamma_symbol == symbol:
            other_engines.append("Gamma")
        if other_engines:
            engine_list = ", ".join(other_engines)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "심볼 중복 배치 불가",
                f"⚠️ 동일한 코인을 여러 엔진에 배치할 수 없습니다!\n\n"
                f"선택한 심볼: {symbol}\n"
                f"이미 배치된 엔진: {engine_list}\n\n"
                f"다른 코인을 선택하거나, {engine_list} 엔진에서\n"
                f"해당 심볼을 먼저 제거한 후 다시 시도하세요."
            )
            return

        print(f"[MAIN] 🎯 엔진 배치: {symbol} -> {engine_name} 엔진")

        # engine key (alpha/beta/gamma)
        engine_key = engine_name.lower()
        engine_results = analysis_data.get("engine_results", {}) if isinstance(analysis_data, dict) else {}
        engine_result = engine_results.get(engine_key, {}) if isinstance(engine_results, dict) else {}

        # 추출 가능한 실행 파라미터
        # 우선: assign_payload(함수 인자 strategy_data) 탑-레벨의 executable_parameters 사용
        exec_params = {}
        if isinstance(strategy_data, dict):
            exec_params = strategy_data.get("executable_parameters") or {}
        # 폴백: analysis_data.engine_results[engine_key].executable_parameters
        if not exec_params:
            if isinstance(engine_result, dict):
                exec_params = engine_result.get("executable_parameters", {})

        # 최대 목표 수익률: analysis_data의 mapping 우선, 없으면 engine_result 내 값 사용
        max_profit = analysis_data.get("max_target_profit", {}).get(engine_key,
                                                                     engine_result.get("max_target_profit", 0) if isinstance(engine_result, dict) else 0)

        # 리스크 관리
        risk_mgmt = analysis_data.get("risk_management", {})

        # 하단 푸터의 해당 엔진에 전달 (exec_params 포함)
        if engine_name == "Alpha":
            self.middle_session_widget.alpha_engine.update_strategy_from_analysis(
                symbol, max_profit, risk_mgmt, exec_params
            )
            self._focus_engine_tab("Alpha")
        elif engine_name == "Beta":
            self.middle_session_widget.beta_engine.update_strategy_from_analysis(
                symbol, max_profit, risk_mgmt, exec_params
            )
            self._focus_engine_tab("Beta")
        elif engine_name == "Gamma":
            self.middle_session_widget.gamma_engine.update_strategy_from_analysis(
                symbol, max_profit, risk_mgmt, exec_params
            )
            self._focus_engine_tab("Gamma")

        # 버튼 상태: 분석 완료로 표시
        try:
            QTimer.singleShot(0, lambda s=symbol: self.ranking_table.set_analysis_state(s, AnalysisState.COMPLETED))
        except Exception:
            pass

        print(f"[MAIN] ✅ {engine_name} 엔진 전략 업데이트 완료: {symbol}")
    
    def _focus_engine_tab(self, engine_name: str):
        """
        해당 엔진 탭으로 포커스 이동
        
        Args:
            engine_name: 엔진명 ("Alpha", "Beta", "Gamma")
        """
        # 푸터 위젯의 해당 엔진 위젯 가져오기
        engine_widget = None
        if engine_name == "Alpha":
            engine_widget = self.middle_session_widget.alpha_engine
        elif engine_name == "Beta":
            engine_widget = self.middle_session_widget.beta_engine
        elif engine_name == "Gamma":
            engine_widget = self.middle_session_widget.gamma_engine
        
        if engine_widget:
            # 해당 엔진 위젯으로 포커스 이동
            engine_widget.setFocus()
            
            # 해당 엔진 위젯이 보이도록 스크롤 이동 (선택사항)
            # parent_widget = engine_widget.parentWidget()
            # if parent_widget:
            #     parent_widget.ensureWidgetVisible(engine_widget)
        
        print(f"[MAIN] 🎯 {engine_name} 엔진으로 포커스 이동")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = YONAMainWindow()
    window.show()
    sys.exit(app.exec())