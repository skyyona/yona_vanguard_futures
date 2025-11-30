"""전략 분석 결과 팝업창 위젯"""
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget
)
from PySide6.QtWidgets import QCheckBox, QDialogButtonBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from datetime import datetime
from PySide6.QtWidgets import QMessageBox


class StrategyAnalysisDialog(QDialog):
    """전략 분석 결과 팝업창"""
    
    # Signal 정의
    engine_assigned = Signal(str, dict)  # 엔진 배치 시 (engine_name, strategy_data)
    analysis_update = Signal(dict)  # 워커 스레드에서 전달된 분석 결과를 메인 스레드에서 처리
    
    def __init__(self, symbol: str, analysis_data: dict, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.analysis_data = analysis_data
        self.apply_risk_overrides = True
        
        self.setWindowTitle(f"전략 분석 결과 - {symbol}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(600)
        
        # 다이얼로그 스타일
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
        """)
        
        # create a stable base layout on the dialog and a replaceable content widget
        # this avoids repeatedly calling setLayout on the dialog itself which can
        # trigger QLayout warnings when updating from worker threads.
        self._base_layout = QVBoxLayout(self)
        self._base_layout.setContentsMargins(0, 0, 0, 0)
        self._base_layout.setSpacing(0)
        self._content_widget = None

        # build initial UI (on main thread)
        self._init_ui()
        # connect update signal to slot to safely update UI from worker threads
        # use queued connection to ensure handler runs on main thread when emitted from worker
        try:
            self.analysis_update.connect(self._on_analysis_update, Qt.QueuedConnection)
        except Exception:
            # fallback if connection with explicit type is not supported
            self.analysis_update.connect(self._on_analysis_update)

    def _on_analysis_update(self, data: dict):
        """Slot: update analysis data and refresh UI in main thread"""
        try:
            self.analysis_data = data
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
        # Simulation assumptions (explicitly shown)
        try:
            SIM_LEV_MIN = 1
            SIM_LEV_MAX = 50
            SIM_KRW = 100000
            SIM_USDT = 70.25
            sim_label = QLabel(f"시뮬레이션 가정 — 레버리지: {SIM_LEV_MIN}–{SIM_LEV_MAX}배 (시뮬레이션 전용), 투입자금: {SIM_KRW}원 (≈{SIM_USDT} USDT)")
            sim_label.setStyleSheet('color: #BBBBBB; font-size: 11px;')
            layout.addWidget(sim_label)
        except Exception:
            pass
        # --- 신규상장 배너 및 신뢰도 표시 ---
        try:
            engine_results = self.analysis_data.get("engine_results", {}) or {}
            if not isinstance(engine_results, dict):
                try:
                    import logging
                    logging.warning("StrategyAnalysisDialog: engine_results is not a dict; coercing to {}. value=%r", engine_results)
                except Exception:
                    pass
                engine_results = {}
            # is_new_listing / data_missing 판단: top-level 우선, 없으면 엔진별 OR
            is_new = bool(self.analysis_data.get("is_new_listing") or any(
                (engine.get("is_new_listing") is True) for engine in engine_results.values()
            ))
            data_missing = bool(self.analysis_data.get("data_missing") or any(
                (engine.get("data_missing") is True) for engine in engine_results.values()
            ))

            # 전반적 confidence 계산: top-level > heuristic.confidence > engine confidence max
            conf = None
            if isinstance(self.analysis_data.get("confidence"), (int, float)):
                conf = float(self.analysis_data.get("confidence"))
            elif isinstance(self.analysis_data.get("heuristic"), dict) and isinstance(self.analysis_data.get("heuristic").get("confidence"), (int, float)):
                conf = float(self.analysis_data.get("heuristic").get("confidence"))
            else:
                try:
                    conf = max(float(engine.get("confidence", 0)) for engine in engine_results.values()) if engine_results else None
                except Exception:
                    conf = None

            if is_new or data_missing:
                banner = QLabel()
                if is_new and data_missing:
                    banner.setText("🔔 신규 상장 코인 (데이터 부족) — 보수적 설정 권장")
                    banner.setStyleSheet('background-color: #FFA000; color: #1b1b1b; padding: 6px; border-radius:4px;')
                elif is_new:
                    banner.setText("🔔 신규 상장 코인 — 신규상장 전용 전략 적용")
                    banner.setStyleSheet('background-color: #FFF176; color: #1b1b1b; padding: 6px; border-radius:4px;')
                else:
                    banner.setText("⚠️ 데이터 부족 — 보수적 설정 사용")
                    banner.setStyleSheet('background-color: #FFE0B2; color: #1b1b1b; padding: 6px; border-radius:4px;')
                layout.addWidget(banner)

            # confidence 표시
            if conf is not None:
                try:
                    conf_pct = float(conf) * 100.0 if conf <= 1.0 else float(conf)
                except Exception:
                    conf_pct = float(conf)
                conf_label = QLabel(f"신뢰도: {conf_pct:.1f}%")
                # 색상: 높을수록 녹색, 낮을수록 빨강
                if conf_pct >= 75:
                    c_style = "color: #4CAF50; font-weight: bold;"
                elif conf_pct >= 40:
                    c_style = "color: #FFC107;"
                else:
                    c_style = "color: #F44336;"
                conf_label.setStyleSheet(c_style + " font-size: 11px;")
                layout.addWidget(conf_label)
        except Exception:
            # 안전망: UI 빌드 실패 시 무시
            pass
        
        # 2. 추천 엔진
        best_engine = self.analysis_data.get("best_engine", "Alpha")
        recommendation = QLabel(f"✅ 추천 엔진: {best_engine}")
        recommendation.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
        layout.addWidget(recommendation)
        
        # 3. 변동성 정보
        volatility = self.analysis_data.get("volatility", 0)
        volatility_label = QLabel(f"📊 변동성: {volatility:.2f}%")
        volatility_label.setStyleSheet("color: #FFC107; font-size: 11px;")
        layout.addWidget(volatility_label)
        
        # 4. 스크롤 영역 (상세 정보)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #333333;
                border-radius: 5px;
                background-color: #2a2a2a;
            }
        """)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        
        
        
        # 4-1 ~ 4-3: Reformat into boxed, collapsible sections to match requested design
        metrics = self.analysis_data.get("metrics", {}) or {}
        exec_params = self.analysis_data.get('executable_parameters', {}) or {}
        if not isinstance(exec_params, dict):
            try:
                import logging
                logging.warning("StrategyAnalysisDialog: executable_parameters is not a dict; coercing to {}. value=%r", exec_params)
            except Exception:
                pass
            exec_params = {}

        # Strategy Simulation Results
        sim_lines = []
        # Estimated trade count (fall back to metrics or N/A)
        sim_lines.append(f"- 예상 거래 횟수: {self.analysis_data.get('estimated_trade_count', metrics.get('estimated_trade_count', 'N/A'))}")
        # Optimal target profit
        try:
            engine_key = (self.analysis_data.get('best_engine') or 'alpha').lower()
            optimal = self.analysis_data.get('max_target_profit', {}).get(engine_key, metrics.get('expected_profit', 'N/A'))
        except Exception:
            optimal = metrics.get('expected_profit', 'N/A')
        sim_lines.append(f"- 최적 목표 수익률(엔진 권장): {optimal if optimal is not None else 'N/A'}")
        sim_lines.append(f"- 총 예상 수익률: {metrics.get('total_return_pct', 'N/A')}")
        # take profit / stop loss / liquidation prevention
        tp = exec_params.get('take_profit_pct')
        sl = exec_params.get('stop_loss_pct')
        sim_lines.append(f"- 익절 권장: {f'{tp*100:.2f}%' if isinstance(tp, float) else (tp if tp is not None else 'N/A')}")
        sim_lines.append(f"- 손절 권장: {f'{sl*100:.2f}%' if isinstance(sl, float) else (sl if sl is not None else 'N/A')}")
        sim_lines.append(f"- 청산 방지 관련: {self.analysis_data.get('liquidation_prevention', 'N/A')}")
        scroll_layout.addWidget(self._create_box_section("Strategy Simulation Results", sim_lines, collapsible=True, initial_open=True))

        # Risk Management box
        rm = self.analysis_data.get('risk_management', {}) or {}
        rm_lines = []
        rm_lines.append(f"- 손절 정책: {rm.get('stop_loss', 'N/A')}")
        rm_lines.append(f"- 트레일링 스톱 정책: {rm.get('trailing_stop', 'N/A')}")
        rm_lines.append(f"- 오늘의 예상 총 수익률: {metrics.get('total_return_pct', 'N/A')}")
        scroll_layout.addWidget(self._create_box_section("Risk Management for the Coin Symbol", rm_lines, collapsible=True, initial_open=False))

        # Detailed Parameters box
        det_lines = []
        if exec_params:
            for k, v in exec_params.items():
                display_val = v
                if k.endswith('_pct') and isinstance(v, float):
                    display_val = f"{v*100:.2f}%"
                elif k == 'position_size' and isinstance(v, float) and v <= 1:
                    display_val = f"{v*100:.2f}%"
                det_lines.append(f"- {k}: {display_val}")
        else:
            det_lines.append("- 상세 파라미터 없음")
        scroll_layout.addWidget(self._create_box_section("Detailed Parameters", det_lines, collapsible=True, initial_open=False))

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        
        # (하단 액션 영역은 아래에서 구성)

        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setSpacing(10)
        action_layout.setContentsMargins(0, 10, 0, 0)

        # Apply risk overrides checkbox (stop-loss & trailing-stop only)
        # Make label explicit that leverage/position_size are NOT included
        self.risk_override_checkbox = QCheckBox("Apply recommended stop-loss & trailing-stop (권장, 레버리지/투입자금 제외)")
        self.risk_override_checkbox.setChecked(True if self.apply_risk_overrides else False)
        action_layout.addWidget(self.risk_override_checkbox)

        # Explicit opt-in for leverage override (default off)
        self.leverage_override_checkbox = QCheckBox("Allow suggested leverage change (explicit opt-in)")
        self.leverage_override_checkbox.setChecked(False)
        # smaller visual weight
        try:
            self.leverage_override_checkbox.setStyleSheet('font-size: 9px; color: #CCCCCC;')
        except Exception:
            pass
        action_layout.addWidget(self.leverage_override_checkbox)

        # Informational subtext clarifying that leverage amplifies losses and
        # that leverage/position size are user-controlled and require explicit confirmation.
        try:
            lev_note = QLabel("※ 레버리지는 손실을 확대합니다. 레버리지 및 투입자금은 자동 적용되지 않으며, 체크 후 Confirm을 통해서만 적용됩니다.")
            lev_note.setStyleSheet('font-size: 10px; color: #FFD54F;')
            lev_note.setWordWrap(True)
            # place the note visually close to the leverage checkbox
            action_layout.addWidget(lev_note)
        except Exception:
            pass

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
        """Create a boxed section with optional collapsible content.

        - title: section title string
        - lines: list of strings to display inside the box
        - collapsible: whether the content can be toggled
        - initial_open: whether content is initially visible
        """
        from PySide6.QtWidgets import QToolButton, QFrame

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

        if collapsible:
            toggle = QToolButton()
            toggle.setArrowType(Qt.DownArrow if initial_open else Qt.RightArrow)
            toggle.setToolButtonStyle(Qt.ToolButtonIconOnly)
            toggle.setStyleSheet('color: #FFFFFF;')
            header_layout.addWidget(toggle)
        else:
            toggle = None

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet('color: #FFC107; font-weight: bold;')
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()

        box_layout.addWidget(header)

        # content
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

        # initial visibility
        if collapsible:
            content_widget.setVisible(initial_open)

            def _toggle():
                vis = not content_widget.isVisible()
                content_widget.setVisible(vis)
                try:
                    toggle.setArrowType(Qt.DownArrow if vis else Qt.RightArrow)
                except Exception:
                    pass

            toggle.clicked.connect(_toggle)

        return container
    
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
        # Start from unified executable_parameters and overlay engine-specific parameters
        base_params = self.analysis_data.get('executable_parameters', {}) or {}
        # engine keys in analysis_data are lowercase (e.g., 'alpha')
        engine_key = engine_name.lower()
        engine_results = self.analysis_data.get('engine_results', {}) or {}
        engine_params = (engine_results.get(engine_key, {}) or {}).get('executable_parameters', {}) or {}
        final_params = dict(base_params)  # shallow copy
        # overlay engine-specific executable parameters but DO NOT include
        # leverage or position_size by default (these are user-controlled)
        skip_keys = {'leverage', 'position_size'}
        for k, v in engine_params.items():
            if k in skip_keys:
                continue
            final_params.setdefault(k, v)

        applied_overrides = {}
        # Only apply stop-loss and trailing-stop from risk_management by default
        if getattr(self, 'risk_override_checkbox', None) and self.risk_override_checkbox.isChecked():
            rm = self.analysis_data.get('risk_management', {}) or {}
            if not isinstance(rm, dict):
                try:
                    import logging
                    logging.warning("StrategyAnalysisDialog: risk_management is not a dict; coercing to {}. value=%r", rm)
                except Exception:
                    pass
                rm = {}
            # apply only safe keys
            if 'stop_loss' in rm:
                final_params['stop_loss_pct'] = float(rm.get('stop_loss'))
                applied_overrides['stop_loss_pct'] = final_params['stop_loss_pct']
            if 'trailing_stop' in rm:
                final_params['trailing_stop_pct'] = float(rm.get('trailing_stop'))
                applied_overrides['trailing_stop_pct'] = final_params['trailing_stop_pct']
        # Leverage is simulation-only by default; allow explicit opt-in
        if getattr(self, 'leverage_override_checkbox', None) and self.leverage_override_checkbox.isChecked():
            rm = self.analysis_data.get('risk_management', {}) or {}
            if not isinstance(rm, dict):
                rm = {}
            if 'force_leverage' in rm:
                # require explicit confirm modal before applying leverage
                try:
                    confirm = QMessageBox(self)
                    confirm.setWindowTitle('Confirm Leverage Override')
                    confirm.setText('권고된 레버리지를 자동으로 적용하시겠습니까?\n레버리지는 손실을 확대합니다. 신중히 결정하세요.')
                    confirm.setInformativeText(f"Suggested leverage: {rm.get('force_leverage')}")
                    confirm.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
                    confirm.setDefaultButton(QMessageBox.Cancel)
                    if getattr(self, '_test_auto_confirm', False):
                        ret = QMessageBox.Ok
                    else:
                        ret = confirm.exec()
                    if ret == QMessageBox.Ok:
                        final_params['leverage'] = int(rm.get('force_leverage'))
                        applied_overrides['leverage'] = final_params['leverage']
                        # record explicit confirmation
                        assign_payload_leverage_meta = True
                    else:
                        assign_payload_leverage_meta = False
                except Exception:
                    assign_payload_leverage_meta = False
        else:
            assign_payload_leverage_meta = False

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
        # annotate leverage confirmation flag in ui_meta if applicable
        try:
            if assign_payload_leverage_meta:
                assign_payload['ui_meta']['leverage_user_confirmed'] = True
        except Exception:
            pass

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
        msg = QMessageBox(self)
        msg.setWindowTitle("Assign Preview")
        msg.setText("Assign the following strategy parameters to %s?" % engine_name)
        msg.setDetailedText(preview_text)
        msg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
        msg.setDefaultButton(QMessageBox.Ok)
        if getattr(self, '_test_auto_confirm', False):
            ret = QMessageBox.Ok
        else:
            ret = msg.exec()
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


