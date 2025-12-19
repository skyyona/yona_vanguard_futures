"""전략 분석 결과 팝업창 위젯"""
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QTabWidget, QGridLayout,
    QScrollArea, QToolButton, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtWidgets import QCheckBox, QDialogButtonBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from datetime import datetime
from PySide6.QtWidgets import QMessageBox
import logging
import traceback
import json
from gui.utils.popup import show_confirmation


class StrategyAnalysisDialog(QDialog):
    """전략 분석 결과 팝업창"""
    
    # Signal 정의
    engine_assigned = Signal(str, dict)  # 엔진 배치 시 (engine_name, strategy_data)
    analysis_update = Signal(dict)  # 워커 스레드에서 전달된 분석 결과를 메인 스레드에서 처리
    
    def __init__(self, symbol: str, analysis_data: dict, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.analysis_data = analysis_data
        # Debug: log the raw analysis_data received for this dialog (help diagnose UI vs API)
        try:
            logging.getLogger(__name__).debug("StrategyAnalysisDialog: received analysis_data for symbol=%s -> %s",
                                             self.symbol,
                                             json.dumps(self.analysis_data, default=str, ensure_ascii=False))
        except Exception:
            try:
                print("[DEBUG] StrategyAnalysisDialog: failed to json.dumps analysis_data; repr below")
                print(repr(self.analysis_data))
            except Exception:
                pass
        # Also print a compact raw dump to stdout so headless tests capture it
        try:
            print(f"[DIALOG-RAW-INIT] symbol={self.symbol} data=" + json.dumps(self.analysis_data, default=str, ensure_ascii=False))
        except Exception:
            try:
                print("[DIALOG-RAW-INIT] symbol=%s data=<<unserializable>>" % getattr(self, 'symbol', '<unknown>'))
            except Exception:
                pass
        self.apply_risk_overrides = True
        
        self.setWindowTitle(f"전략 분석 결과 - {symbol}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(600)
        # 기본 다이얼로그 스타일 (단순한 다크 테마)
        self.setStyleSheet("""
            QDialog {
                background-color: #202020;
            }
            QLabel {
                color: #FFFFFF;
            }
        """)

        # 다이얼로그의 루트 레이아웃을 한 번만 생성해 두고,
        # 실제 컨텐츠는 _replace_content_widget() 으로 교체한다.
        self._base_layout = QVBoxLayout(self)
        self._base_layout.setContentsMargins(10, 10, 10, 10)
        self._base_layout.setSpacing(10)

        # 초기 분석 데이터를 기반으로 UI를 한 번 구성한다.
        self._content_widget: Optional[QWidget] = None
        self._init_ui()

        # 디버깅: 실제 로드된 파일 경로 출력
        import os
        print(f"[DEBUG] StrategyAnalysisDialog loaded from: {os.path.abspath(__file__)}")

    def _on_analysis_update(self, data: dict):
        """Slot: update analysis data and refresh UI in main thread"""
        try:
            # Debug: log the raw payload received via analysis_update signal
            try:
                logging.getLogger(__name__).debug("StrategyAnalysisDialog._on_analysis_update: received data for symbol=%s -> %s",
                                                 getattr(self, 'symbol', '<unknown>'),
                                                 json.dumps(data, default=str, ensure_ascii=False))
            except Exception:
                try:
                    print("[DEBUG] StrategyAnalysisDialog._on_analysis_update: cannot json.dumps data; repr below")
                    print(repr(data))
                except Exception:
                    pass
            self.analysis_data = data
            try:
                print(f"[DIALOG-RAW-UPDATE] symbol={getattr(self,'symbol','<unknown>')} data=" + json.dumps(data, default=str, ensure_ascii=False))
            except Exception:
                try:
                    print("[DIALOG-RAW-UPDATE] symbol=%s data=<<unserializable>>" % getattr(self,'symbol','<unknown>'))
                except Exception:
                    pass
            # Rebuild UI on main thread
            self._init_ui()
        except Exception as e:
            # Log full traceback so errors aren't silently swallowed
            try:
                import logging
                logging.exception("Exception in StrategyAnalysisDialog._on_analysis_update: %s", e)
            except Exception:
                import traceback
                traceback.print_exc()
    
    def _init_ui(self):
        print("[DEBUG] _init_ui 진입, analysis_data type:", type(self.analysis_data))
        # Build the new content widget and its layout off-widget, then swap
        # it into the dialog's persistent base layout. This is atomic from
        # the perspective of the dialog's widget tree and avoids QLayout
        # warnings about setting multiple layouts on the same widget.
        # Defensive: ensure analysis_data is a dict so UI code can assume
        # a mapping-like object (helps avoid AttributeError during builds).
        if not isinstance(self.analysis_data, dict):
            try:
                import logging
                logging.warning("StrategyAnalysisDialog: analysis_data not dict; coercing. value=%r", self.analysis_data)
            except Exception:
                pass
            # safe coercion: if None -> {}, otherwise try shallow copy
            try:
                self.analysis_data = {} if self.analysis_data is None else dict(self.analysis_data)
            except Exception:
                self.analysis_data = {}

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. 헤더
        header = QLabel(f"전략 분석 결과: {self.symbol}")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(14)
        header.setFont(header_font)
        header.setStyleSheet("color: #FFC107;")
        layout.addWidget(header)

        # 1-1. 신규 상장 안내 (백엔드 listing_meta 기반)
        listing_meta = self.analysis_data.get("listing_meta", {}) or {}
        is_new = bool(listing_meta.get("is_new_listing", False))
        try:
            days_since_listing = int(listing_meta.get("days_since_listing")) if listing_meta.get("days_since_listing") is not None else None
        except Exception:
            days_since_listing = None
        new_strategy_applied = bool(listing_meta.get("new_listing_strategy_applied", False))

        if is_new and days_since_listing is not None and days_since_listing < 999:
            label_text = f"new {days_since_listing}일 신규 상장 전용 전략 적용" if new_strategy_applied else f"new {days_since_listing}일 신규 상장 코인 (일반 전략 분석)"
            new_lbl = QLabel(label_text)
            new_lbl.setStyleSheet("color: #4DD0E1; font-size: 11px; font-weight: bold;")
            layout.addWidget(new_lbl)
		
        # 2. 상단 요약 행: 변동성 + 추천 레버리지 X
        #    두 정보를 한 눈에 볼 수 있도록 2열 컨테이너로 구성한다.
        metrics = self.analysis_data.get("performance", {}) or {}
        exec_params = self.analysis_data.get("best_parameters", {}) or {}
        if not isinstance(exec_params, dict):
            try:
                import logging
                logging.warning("StrategyAnalysisDialog: best_parameters is not a dict; coercing to {}. value=%r", exec_params)
            except Exception:
                pass
            exec_params = {}

        lev_info = self.analysis_data.get("leverage_recommendation", {}) or {}

        volatility = self.analysis_data.get("volatility", 0)
        header_row = QWidget()
        header_row_layout = QHBoxLayout(header_row)
        header_row_layout.setContentsMargins(0, 0, 0, 0)
        header_row_layout.setSpacing(15)

        volatility_label = QLabel(f"📊 변동성: {volatility:.2f}%")
        volatility_label.setStyleSheet("color: #FFC107; font-size: 11px;")
        header_row_layout.addWidget(volatility_label, 1)

        # Recommended leverage summary (short, 2열 표시)
        lev_summary_lines = []
        try:
            rec_x = lev_info.get("recommended_leverage_x")
            status = lev_info.get("status", "") or ""
            max_loss_limit = lev_info.get("max_equity_loss_limit_pct")
            est_loss = lev_info.get("estimated_equity_loss_pct_at_max_drawdown")
            if rec_x is not None:
                lev_summary_lines.append(f"추천 레버리지 X: {int(rec_x)}X")
                if isinstance(est_loss, (int, float)):
                    lev_summary_lines.append(f"과거 최대 낙폭 기준 예상 최대 손실: {float(est_loss):.1f}%")
                if isinstance(max_loss_limit, (int, float)):
                    lev_summary_lines.append(f"손실 한도 가정: 약 {float(max_loss_limit):.0f}% 이내")
            elif status == "insufficient_data":
                lev_summary_lines.append("추천 레버리지 X: N/A (데이터 부족)")
            elif status == "error":
                lev_summary_lines.append("추천 레버리지 X: N/A (계산 오류)")
            else:
                lev_summary_lines.append("추천 레버리지 X: N/A")
        except Exception:
            lev_summary_lines = ["추천 레버리지 X: N/A"]

        lev_label = QLabel("\n".join(lev_summary_lines))
        lev_label.setStyleSheet("color: #FFC107; font-size: 11px;")
        lev_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_row_layout.addWidget(lev_label, 1)

        layout.addWidget(header_row)
		
        # 3. 메인 컨텐츠 영역: 탭으로 구성
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)

        print("[DEBUG] _init_ui: 탭 생성 및 추가 직전")

        # --- 탭 1: 상세 전략 내용 ---
        tab_details = QWidget()
        details_layout = QVBoxLayout(tab_details)
        details_layout.setSpacing(10)
        details_layout.setContentsMargins(10, 10, 10, 10)

        # Strategy Performance box (공통)
        perf_lines = []
        total_trades = metrics.get("total_trades", "N/A")
        win_rate = metrics.get("win_rate")
        profit_pct = metrics.get("profit_percentage")
        max_dd = metrics.get("max_drawdown_pct")
        perf_lines.append(f"- 총 거래 수: {total_trades}")
        if isinstance(win_rate, (int, float)):
            perf_lines.append(f"- 승률: {win_rate:.2f}%")
        else:
            perf_lines.append("- 승률: N/A")
        if isinstance(profit_pct, (int, float)):
            perf_lines.append(f"- 총 수익률: {profit_pct:.2f}%")
        else:
            perf_lines.append("- 총 수익률: N/A")
        if isinstance(max_dd, (int, float)):
            perf_lines.append(f"- 최대 낙폭: {max_dd:.2f}%")
        else:
            perf_lines.append("- 최대 낙폭: N/A")
        if metrics.get("aborted_early"):
            perf_lines.append("- 경고: 시뮬레이션이 조기 종료되었습니다.")
        if metrics.get("insufficient_trades"):
            perf_lines.append("- 경고: 거래 수가 적어 신뢰도가 낮을 수 있습니다.")
        details_layout.addWidget(self._create_box_section("Strategy Performance", perf_lines, collapsible=True, initial_open=True))

        # Recommended Risk Parameters box (공통)
        rm_lines = []
        tp = exec_params.get("take_profit_pct")
        sl = exec_params.get("stop_loss_pct")
        ts = exec_params.get("trailing_stop_pct")
        lp = exec_params.get("liquidation_protection_pct")
        if tp is not None:
            try:
                rm_lines.append(f"- 익절률: {float(tp)*100:.2f}%")
            except Exception:
                rm_lines.append(f"- 익절률: {tp}")
        if sl is not None:
            try:
                rm_lines.append(f"- 손절률: {float(sl)*100:.2f}%")
            except Exception:
                rm_lines.append(f"- 손절률: {sl}")
        if ts is not None:
            try:
                rm_lines.append(f"- 트레일링 스톱: {float(ts)*100:.2f}%")
            except Exception:
                rm_lines.append(f"- 트레일링 스톱: {ts}")
        if lp is not None:
            try:
                rm_lines.append(f"- 청산 방지 여유(권장): {float(lp):.2f}%")
            except Exception:
                rm_lines.append(f"- 청산 방지 여유(권장): {lp}")
        if not rm_lines:
            rm_lines.append("- 표시할 리스크 파라미터가 없습니다.")
        details_layout.addWidget(self._create_box_section("Recommended Risk Parameters", rm_lines, collapsible=True, initial_open=False))

        # Applied Strategy Details / Entry Condition Details
        applied_lines = []
        entry_lines = []
        if is_new:
            # 신규 상장 전용 전략 설명
            new_strat = self.analysis_data.get("new_listing_strategy", {}) or {}
            applied_lines.append("- 신규 상장 전용 휴리스틱 기반 전략입니다.")
            triggered = new_strat.get("triggered_strategies") or []
            if triggered:
                applied_lines.append("- 활성화된 신규 상장 패턴:")
                for name in triggered:
                    applied_lines.append(f"  • {name}")
            notes = new_strat.get("notes") or []
            if notes:
                applied_lines.append("- 전략 메모:")
                for n in notes:
                    applied_lines.append(f"  • {n}")

            entry_lines.append("- 신규 상장 전용 휴리스틱(거래량 스파이크, 초기 눌림/되돌림, 라운드 넘버 돌파 등)을 기반으로 진입 조건을 생성합니다.")
            entry_lines.append("- 상위 타임프레임 EMA 추세와 볼륨/스토캐스틱 RSI 조건이 충족될 때만 진입 신호를 허용합니다.")
        else:
            # 일반 코인 전략 설명
            applied_lines.append("- EMA 9/21 골든크로스 기반 롱 스캘핑 전략입니다.")
            applied_lines.append("- 추세 필터, 세션 필터, 볼륨 모멘텀 옵션을 활용해 진입 조건을 정교하게 제한합니다.")

            entry_lines.append("- 직전 캔들에서 EMA_fast ≤ EMA_slow 이고 현재 EMA_fast > EMA_slow 일 때 롱 진입 시그널을 발생시킵니다.")
            entry_lines.append("- 추세 필터 활성 시 상위 타임프레임 EMA_fast > EMA_slow 인 구간에서만 진입합니다.")
            entry_lines.append("- 세션 필터 활성 시 허용된 세션(asia/europe/us) 에서만 진입합니다.")
            entry_lines.append("- 볼륨 모멘텀 활성 시 VolumeSpike=1 이고 VWAP 위에 있을 때만 롱 진입을 허용합니다.")

        details_layout.addWidget(self._create_collapsible_text_section("Applied Strategy Details", applied_lines or ["- 전략 설명 없음"]))
        details_layout.addWidget(self._create_collapsible_text_section("Entry Condition Details", entry_lines or ["- 진입 조건 설명 없음"]))

        details_layout.addStretch()
        tabs.addTab(tab_details, "상세 전략 내용")

        # --- 탭 2: 단계별 시뮬레이션 결과 ---
        tab_sims = QWidget()
        sims_layout = QVBoxLayout(tab_sims)
        sims_layout.setSpacing(10)
        sims_layout.setContentsMargins(10, 10, 10, 10)

        scenarios = self.analysis_data.get("scenarios", {}) or {}

        # 시나리오 정보가 전혀 없는 경우(구버전 응답 등)에는
        # 최소한 S1에 대해 현재 메인 메트릭/파라미터로부터 표를 생성한다.
        if not scenarios and metrics:
            from copy import copy
            scenarios = {
                "S1": {
                    "label": "base_window_from_performance",
                    "valid": True,
                    "parameters": copy(exec_params),
                    "performance": copy(metrics),
                }
            }

        def _get_scenario(key: str):
            sc = scenarios.get(key) or {}
            perf = sc.get("performance") or {}
            params = sc.get("parameters") or {}
            valid = sc.get("valid", True)
            return perf, params, valid

        def _add_simulation_block(title: str, key: str):
            perf, params, valid = _get_scenario(key)
            if not perf or (key != "S1" and not valid):
                msg = QLabel("유효한 시뮬레이션 결과가 없습니다 (데이터 부족 또는 계산 실패).")
                msg.setStyleSheet("color: #CCCCCC; font-size: 11px;")
                msg.setWordWrap(True)
                inner = QWidget()
                il = QVBoxLayout(inner)
                il.setContentsMargins(6, 6, 6, 6)
                il.setSpacing(4)
                il.addWidget(msg)
            else:
                inner = self._create_simulation_table(perf, params)

            initial_open = True if key == "S1" else False
            section = self._create_collapsible_simulation_section(title, inner, initial_open=initial_open)
            sims_layout.addWidget(section)

        # S1~S4: 공통 표 레이아웃 (모두 접을 수 있는 컨테이너)
        _add_simulation_block("Simulation 1 result (기본 기간 전체)", "S1")
        _add_simulation_block("Simulation 2 result (최근 24h)", "S2")
        _add_simulation_block("Simulation 3 result (고변동 구간)", "S3")
        _add_simulation_block("Simulation 4 result (저변동 구간)", "S4")

        # S5: 공격적 레버리지 가상 시나리오를 별도의 표 형태로 표시 (접기 가능)
        s5 = scenarios.get("S5") or {}
        s5_inner = self._create_aggressive_s5_table(s5)
        s5_section = self._create_collapsible_simulation_section("Simulation 5 result (공격적 레버리지 가상)", s5_inner, initial_open=False)
        sims_layout.addWidget(s5_section)

        sims_layout.addStretch()
        tabs.addTab(tab_sims, "단계별 시뮬레이션 결과")

        # --- 탭 3: 전략별 & 실거래 성과 내역 ---
        tab_perf = QWidget()
        perf_layout = QVBoxLayout(tab_perf)
        perf_layout.setSpacing(10)
        perf_layout.setContentsMargins(10, 10, 10, 10)

        # 전략 성과 테이블
        perf_table = QTableWidget()
        perf_table.setColumnCount(6)
        perf_table.setHorizontalHeaderLabels(["전략명", "종목", "기간", "수익률", "승률", "거래횟수"])
        perf_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        perf_data = self.analysis_data.get("strategy_performance", [])
        perf_table.setRowCount(len(perf_data))
        for r, row in enumerate(perf_data):
            perf_table.setItem(r, 0, QTableWidgetItem(str(row.get("strategy_name", "-"))))
            perf_table.setItem(r, 1, QTableWidgetItem(str(row.get("symbol", "-"))))
            perf_table.setItem(r, 2, QTableWidgetItem(str(row.get("period", "-"))))
            perf_table.setItem(r, 3, QTableWidgetItem(f"{row.get('profit_pct', 0):.2f}%"))
            perf_table.setItem(r, 4, QTableWidgetItem(f"{row.get('win_rate', 0):.2f}%"))
            perf_table.setItem(r, 5, QTableWidgetItem(str(row.get("trade_count", "-"))))
        perf_layout.addWidget(QLabel("전략별 실전 성과 대시보드"))
        perf_layout.addWidget(perf_table)

        # 실거래 로그 테이블
        log_table = QTableWidget()
        log_table.setColumnCount(6)
        log_table.setHorizontalHeaderLabels(["No", "진입시각", "진입가", "청산가", "수익률", "사유"])
        log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        log_data = self.analysis_data.get("trade_logs", [])
        log_table.setRowCount(len(log_data))
        for r, row in enumerate(log_data):
            log_table.setItem(r, 0, QTableWidgetItem(str(r+1)))
            log_table.setItem(r, 1, QTableWidgetItem(str(row.get("entry_time", "-"))))
            log_table.setItem(r, 2, QTableWidgetItem(str(row.get("entry_price", "-"))))
            log_table.setItem(r, 3, QTableWidgetItem(str(row.get("exit_price", "-"))))
            log_table.setItem(r, 4, QTableWidgetItem(f"{row.get('profit_pct', 0):.2f}%"))
            log_table.setItem(r, 5, QTableWidgetItem(str(row.get("reason", "-"))))
        perf_layout.addWidget(QLabel("실거래 로그 상세 내역"))
        perf_layout.addWidget(log_table)

        try:
            print(f"[DEBUG] _preview_and_assign complete. symbol={self.symbol} engine={engine_name} final_params_count={len(final_params)} analysis_keys={len(self.analysis_data) if isinstance(self.analysis_data, dict) else 0}")
        except Exception:
            print("[DEBUG] _preview_and_assign complete (debug print failed)")
        print("[DEBUG] 전략별 성과 데이터:", self.analysis_data.get("strategy_performance"))
        print("[DEBUG] 실거래 로그 데이터:", self.analysis_data.get("trade_logs"))
        tabs.addTab(tab_perf, "전략별 & 실거래 성과 내역")

        layout.addWidget(tabs)
        
        
        # (하단 액션 영역은 아래에서 구성)

        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setSpacing(10)
        action_layout.setContentsMargins(0, 10, 0, 0)

        action_layout.addStretch()

        assign_label = QLabel("Assign Trading Symbol:")
        assign_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #999;")
        action_layout.addWidget(assign_label)

        engines = [
            ("Alpha", "#4CAF50", "ALPHA"),
            ("Beta", "#2196F3", "BETA"),
            ("Gamma", "#FF9800", "GAMMA")
        ]

        for engine_name, color, label in engines:
            btn = QPushButton(label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    font-size: 11px;
                    border: none;
                    border-radius: 3px;
                    padding: 6px 15px;
                    min-width: 60px;
                }}
                QPushButton:hover {{
                    background-color: {self._lighten_color(color)};
                }}
                QPushButton:pressed {{
                    background-color: {self._darken_color(color)};
                }}
            """)

            btn.clicked.connect(lambda checked, e=engine_name: self._preview_and_assign(e))
            action_layout.addWidget(btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        action_layout.addWidget(cancel_btn)

        layout.addWidget(action_container)

        # Atomically replace the dialog's content widget. If replacement
        # fails for any reason, fall back to a minimal error widget so the
        # dialog never appears blank and logs contain the traceback.
        try:
            self._replace_content_widget(content_widget)
        except Exception:
            try:
                import logging
                logging.exception("StrategyAnalysisDialog: exception while replacing content widget")
            except Exception:
                pass
            fallback = QWidget()
            fl = QVBoxLayout(fallback)
            fl.setContentsMargins(12, 12, 12, 12)
            err_label = QLabel("Failed to build analysis UI. See application log for details.")
            err_label.setStyleSheet('color: #FFCDD2; font-weight: bold;')
            err_label.setWordWrap(True)
            fl.addWidget(err_label)
            try:
                self._replace_content_widget(fallback)
            except Exception:
                # Last resort: give up silently to avoid crash; log if possible
                try:
                    import logging
                    logging.exception("StrategyAnalysisDialog: also failed to set fallback widget")
                except Exception:
                    pass

    def _clear_layout(self, layout):
        """Recursively clear and delete a QLayout and its child widgets/layouts.

        This removes widgets from their parents and calls deleteLater on layouts
        to avoid 'QLayout: Attempting to add QLayout' warnings when rebuilding UI.
        """
        if layout is None:
            return

        # Remove all items
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                try:
                    widget.setParent(None)
                    widget.deleteLater()
                except Exception:
                    pass
            else:
                child_layout = item.layout()
                if child_layout is not None:
                    # recursive clear
                    try:
                        self._clear_layout(child_layout)
                    except Exception:
                        pass

        # schedule layout for deletion
        try:
            layout.deleteLater()
        except Exception:
            pass

    def _replace_content_widget(self, new_widget: QWidget):
        """Replace the current content widget with `new_widget` atomically.

        Removes and schedules deletion of the previous content widget and
        inserts the new one into the persistent base layout. This avoids
        calling setLayout on the dialog repeatedly.
        """
        try:
            old = getattr(self, '_content_widget', None)
            if old is not None:
                try:
                    # remove from layout and allow it to be deleted later
                    self._base_layout.removeWidget(old)
                    old.setParent(None)
                    old.deleteLater()
                except Exception:
                    pass
            # add the new widget into the base layout
            self._base_layout.addWidget(new_widget)
            self._content_widget = new_widget
        except Exception:
            try:
                import logging
                logging.exception('Failed to replace content widget')
            except Exception:
                pass
    
    def _create_section(self, title: str, content: str) -> QWidget:
        """섹션 위젯 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #FFC107;")
        layout.addWidget(title_label)
        
        content_label = QLabel(content)
        content_label.setStyleSheet("font-size: 10px; color: #CCCCCC;")
        content_label.setWordWrap(True)
        layout.addWidget(content_label)
        
        return widget

    def _create_box_section(self, title: str, lines: list, collapsible: bool = True, initial_open: bool = False) -> QWidget:
        """Create a simple boxed section used for strategy analysis.

        현재 구현에서는 대부분의 섹션을 항상 펼쳐진 상태로 보여주기 위해
        단순한 박스 레이아웃을 사용한다. 일부 섹션(예: Applied/Entry Details)은
        별도의 헬퍼(_create_collapsible_text_section)를 사용해 접기/펼치기 및
        스크롤 동작을 제공한다.
        """
        from PySide6.QtWidgets import QFrame

        container = QFrame()
        container.setStyleSheet("background-color: #2b2b2b; border-radius: 4px;")
        box_layout = QVBoxLayout(container)
        box_layout.setContentsMargins(8, 8, 8, 8)
        box_layout.setSpacing(6)

        # header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet('color: #FFC107; font-weight: bold;')
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        box_layout.addWidget(header)

        # content (always visible)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(4)
        for line in lines:
            lbl = QLabel(line)
            lbl.setStyleSheet('color: #CCCCCC; font-size: 11px;')
            lbl.setWordWrap(True)
            content_layout.addWidget(lbl)

        box_layout.addWidget(content_widget)

        return container

    def _create_collapsible_text_section(self, title: str, lines: list) -> QWidget:
        """텍스트 목록을 접기/펼치기 가능한 박스 섹션으로 생성.

        3줄을 초과하는 경우 내부에 QScrollArea 를 사용해 스크롤로 확인 가능하게 한다.
        """
        from PySide6.QtWidgets import QFrame

        container = QFrame()
        container.setStyleSheet("background-color: #2b2b2b; border-radius: 4px;")
        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(6)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        btn = QToolButton()
        btn.setCheckable(True)
        btn.setChecked(False)
        btn.setText("▶")
        btn.setStyleSheet("color: #FFC107; font-size: 11px; font-weight: bold;")

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet('color: #FFC107; font-weight: bold;')

        header_layout.addWidget(btn)
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        outer_layout.addWidget(header)

        # 본문 콘텐츠
        inner_widget = QWidget()
        inner_layout = QVBoxLayout(inner_widget)
        inner_layout.setContentsMargins(6, 6, 6, 6)
        inner_layout.setSpacing(4)
        for line in lines:
            lbl = QLabel(line)
            lbl.setStyleSheet('color: #CCCCCC; font-size: 11px;')
            lbl.setWordWrap(True)
            inner_layout.addWidget(lbl)

        if len(lines) > 3:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setWidget(inner_widget)
            # 너무 높지 않도록 기본 높이 제한
            scroll.setMinimumHeight(80)
            content_widget = scroll
        else:
            content_widget = inner_widget

        content_widget.setVisible(False)
        outer_layout.addWidget(content_widget)

        def _on_toggled(checked: bool):
            content_widget.setVisible(checked)
            btn.setText("▼" if checked else "▶")

        btn.toggled.connect(_on_toggled)

        return container

    def _create_collapsible_simulation_section(self, title: str, inner_widget: QWidget, initial_open: bool = False) -> QWidget:
        """시뮬레이션 결과 블록을 위한 접을 수 있는 컨테이너.

        S1~S5 결과를 모두 동일 UX(▶ 버튼)로 보여주기 위해 사용한다.
        """
        from PySide6.QtWidgets import QFrame

        container = QFrame()
        container.setStyleSheet("background-color: #2b2b2b; border-radius: 4px;")
        outer_layout = QVBoxLayout(container)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setSpacing(6)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        btn = QToolButton()
        btn.setCheckable(True)
        btn.setChecked(initial_open)
        btn.setText("▼" if initial_open else "▶")
        btn.setStyleSheet("color: #FFC107; font-size: 11px; font-weight: bold;")

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet('color: #FFC107; font-weight: bold;')

        header_layout.addWidget(btn)
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        outer_layout.addWidget(header)

        inner_widget.setVisible(initial_open)
        outer_layout.addWidget(inner_widget)

        def _on_toggled(checked: bool):
            inner_widget.setVisible(checked)
            btn.setText("▼" if checked else "▶")

        btn.toggled.connect(_on_toggled)

        return container

    def _create_simulation_table(self, perf: dict, params: dict) -> QWidget:
        """단계별 시뮬레이션 결과를 표 형태로 보여주는 위젯 생성.

        상단 행: 총 거래 수 / 승률 / 누적 수익률 / 최대 낙폭
        하단 행: TP / SL / TS
        """
        from PySide6.QtWidgets import QFrame

        table = QFrame()
        table.setStyleSheet("QFrame { border: 1px solid #444444; }")
        grid = QGridLayout(table)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        def _add_cell(row: int, col: int, text: str, header: bool = False):
            lbl = QLabel(text)
            style = "border: 1px solid #444444; padding: 4px;"
            if header:
                style += " font-weight: bold; color: #FFFFFF;"
            else:
                style += " color: #CCCCCC;"
            lbl.setStyleSheet(style)
            lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(lbl, row, col)

        # 1행: 헤더
        headers_top = ["총 거래 수", "승률", "누적 수익률", "최대 낙폭"]
        for c, text in enumerate(headers_top):
            _add_cell(0, c, text, header=True)

        # 2행: 값 (퍼센트 포맷은 모두 0.00% 형식 사용)
        total_trades = perf.get("total_trades")
        win_rate = perf.get("win_rate")
        profit_pct = perf.get("profit_percentage")
        max_dd = perf.get("max_drawdown_pct")
        vals_top = [
            str(int(total_trades)) if isinstance(total_trades, (int, float)) else "N/A",
            f"{win_rate:.2f}%" if isinstance(win_rate, (int, float)) else "0.00%",
            f"{profit_pct:.2f}%" if isinstance(profit_pct, (int, float)) else "0.00%",
            f"{max_dd:.2f}%" if isinstance(max_dd, (int, float)) else "0.00%",
        ]
        for c, text in enumerate(vals_top):
            _add_cell(1, c, text)

        # 3행: TP / SL / TS 헤더
        headers_bottom = ["TP", "SL", "TS", ""]
        for c, text in enumerate(headers_bottom):
            _add_cell(2, c, text, header=True)

        # 4행: TP / SL / TS 값 (없을 때도 0.00% 형식 유지)
        _tp = params.get("take_profit_pct")
        _sl = params.get("stop_loss_pct")
        _ts = params.get("trailing_stop_pct")
        vals_bottom = [
            f"{float(_tp)*100:.2f}%" if isinstance(_tp, (int, float)) else "0.00%",
            f"{float(_sl)*100:.2f}%" if isinstance(_sl, (int, float)) else "0.00%",
            f"{float(_ts)*100:.2f}%" if isinstance(_ts, (int, float)) else "0.00%",
            "",
        ]
        for c, text in enumerate(vals_bottom):
            _add_cell(3, c, text)

        return table

    def _create_aggressive_s5_table(self, s5: dict) -> QWidget:
        """S5 공격적 레버리지 가상 시나리오를 위한 간단한 표."""
        from PySide6.QtWidgets import QFrame

        table = QFrame()
        table.setStyleSheet("QFrame { border: 1px solid #444444; }")
        grid = QGridLayout(table)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        def _add_cell(row: int, col: int, text: str, header: bool = False):
            lbl = QLabel(text)
            style = "border: 1px solid #444444; padding: 4px;"
            if header:
                style += " font-weight: bold; color: #FFFFFF;"
            else:
                style += " color: #CCCCCC;"
            lbl.setStyleSheet(style)
            lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(lbl, row, col)

        # 헤더 행
        headers = ["공격적 가정 레버리지", "예상 최대 손실(계좌)", "손실 한도 가정"]
        for c, text in enumerate(headers):
            _add_cell(0, c, text, header=True)

        status = s5.get("status", "") or ""
        lev = s5.get("aggressive_leverage_x")
        loss = s5.get("estimated_equity_loss_pct_at_max_drawdown")
        max_limit = s5.get("max_equity_loss_limit_pct", 100.0)

        if lev is not None:
            vals = [
                f"{int(lev)}X",
                f"{float(loss):.2f}%" if isinstance(loss, (int, float)) else "0.00%",
                f"{float(max_limit):.2f}%",
            ]
        else:
            if status == "drawdown_too_high":
                msg = "과거 최대 낙폭 과도"
            elif status == "insufficient_data":
                msg = "데이터 부족"
            elif status == "error":
                msg = "계산 오류"
            else:
                msg = "정보 없음"
            vals = [msg, "0.00%", f"{float(max_limit):.2f}%"]

        for c, text in enumerate(vals):
            _add_cell(1, c, text)

        return table
    
    def _create_engine_section(self, engine_name: str, engine_data: dict) -> QWidget:
        """레거시: 엔진별 상세 섹션 생성기 (제거됨).

        이 함수는 현재 코드 경로에서 호출되지 않으며, 유지보수 부담을
        줄이기 위해 제거 상태로 표시합니다. 필요 시 Git 이력에서 복원하세요.
        """
        raise NotImplementedError("_create_engine_section() has been removed; see git history for prior implementation")
    
    def _lighten_color(self, color: str) -> str:
        """색상 밝게"""
        color_map = {
            "#4CAF50": "#66BB6A",  # Alpha
            "#2196F3": "#42A5F5",  # Beta
            "#FF9800": "#FFB74D"   # Gamma
        }
        return color_map.get(color, color)
    
    def _darken_color(self, color: str) -> str:
        """색상 어둡게"""
        color_map = {
            "#4CAF50": "#388E3C",  # Alpha
            "#2196F3": "#1976D2",  # Beta
            "#FF9800": "#F57C00"   # Gamma
        }
        return color_map.get(color, color)
    
    def _preview_and_assign(self, engine_name: str):
        """Show preview modal with final params and emit assign_payload on confirmation."""
        # 단일 전략 파라미터(best_parameters)를 그대로 사용
        base_params = self.analysis_data.get('best_parameters', {}) or {}
        if not isinstance(base_params, dict):
            try:
                import logging
                logging.warning("StrategyAnalysisDialog: best_parameters is not a dict; coercing to {}. value=%r", base_params)
            except Exception:
                pass
            base_params = {}

        # leverage / position_size 는 엔진 푸터에서 직접 설정하므로 여기서는 건드리지 않음
        final_params = dict(base_params)

        applied_overrides = {}

        # Build assign payload
        assign_payload = {
            'symbol': self.symbol,
            'engine_name': engine_name,
            'analysis_data': self.analysis_data,
            'executable_parameters': final_params,
            'applied_risk_overrides': applied_overrides,
            'ui_meta': {
                'confirmed_by_user': False,
                'confirmed_at': None,
                'source': 'strategy_analysis_dialog_v2'
            }
        }

        # Prepare preview text
        def param_line(k, v):
            if k.endswith('_pct') and isinstance(v, float):
                return f"{k}: {v*100:.2f}%"
            if k == 'position_size' and isinstance(v, float) and v <= 1:
                return f"{k}: {v*100:.2f}%"
            return f"{k}: {v}"

        lines = [f"Symbol: {self.symbol}", f"Engine: {engine_name}", "", "Final Parameters:"]
        for k, v in final_params.items():
            lines.append(param_line(k, v))
        if applied_overrides:
            lines.append("")
            lines.append("Applied Risk Overrides:")
            for k, v in applied_overrides.items():
                lines.append(param_line(k, v))

        preview_text = "\n".join(lines)

        # Show confirmation dialog
        try:
            ret = show_confirmation(
                self,
                "Assign Preview",
                "Assign the following strategy parameters to %s?" % engine_name,
                detailed=preview_text,
                buttons=QMessageBox.Cancel | QMessageBox.Ok,
                default=QMessageBox.Ok,
            )
        except Exception:
            # fallback to safe default
            ret = QMessageBox.Ok
        if ret == QMessageBox.Ok:
            assign_payload['ui_meta']['confirmed_by_user'] = True
            assign_payload['ui_meta']['confirmed_at'] = datetime.utcnow().isoformat() + 'Z'
            # emit signal to main
            try:
                self.engine_assigned.emit(engine_name, assign_payload)
            except Exception:
                pass
            # close dialog
            self.accept()

        print("[DEBUG] addTab(tab_perf, '전략별 & 실거래 성과 내역') 실행됨. perf_data rows:", len(perf_data), "/ log_data rows:", len(log_data))


