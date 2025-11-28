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
        except Exception:
            # avoid raising UI exceptions from the slot
            pass
    
    def _init_ui(self):
        # If there's an existing layout (e.g. when updating), clear it
        old_layout = self.layout()
        if old_layout is not None:
            try:
                self._clear_layout(old_layout)
            except Exception:
                # best-effort: ignore UI cleanup errors
                pass

        layout = QVBoxLayout(self)
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
        # --- 신규상장 배너 및 신뢰도 표시 ---
        try:
            engine_results = self.analysis_data.get("engine_results", {})
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
        
        
        
        # 4-1. 통합 전략 요약: metrics + single executable_parameters
        metrics = self.analysis_data.get("metrics", {})
        metrics_text = (
            f"총 수익률: {metrics.get('total_return_pct', 0):.2f}%\n"
            f"승률: {metrics.get('win_rate', 0):.2f}%\n"
            f"최대 낙폭: {metrics.get('max_drawdown_pct', 0):.2f}%\n"
            f"변동성: {metrics.get('volatility_pct', 0):.2f}%"
        )
        metrics_section = self._create_section("📈 전략 요약", metrics_text)
        scroll_layout.addWidget(metrics_section)

        # 4-2. 파라미터 개요 (human-friendly)
        exec_params = self.analysis_data.get('executable_parameters', {}) or {}
        overview_lines = []
        lev = exec_params.get('leverage')
        ps = exec_params.get('position_size')
        sl = exec_params.get('stop_loss_pct')
        no_comp = exec_params.get('no_compounding')
        overview_lines.append(f"권장 레버리지: {int(lev) if lev is not None else 'N/A'}x")
        if isinstance(ps, float) and ps <= 1:
            overview_lines.append(f"거래당 자본 비중: {ps*100:.2f}%")
        else:
            overview_lines.append(f"거래당 자본 비중: {ps if ps is not None else 'N/A'}")
        overview_lines.append(f"전략 권장 손절: {float(sl)*100:.2f}%" if sl is not None else "전략 권장 손절: N/A")
        overview_lines.append(f"복리: {'활성(전략 기본)' if no_comp is not True else '비활성(복리 사용하지 않음)'}")
        overview_section = self._create_section("🧾 파라미터 개요", "\n".join(overview_lines))
        scroll_layout.addWidget(overview_section)

        # 4-3. 상세 파라미터 테이블 (simple label list)
        try:
            params_widget = QWidget()
            params_layout = QVBoxLayout(params_widget)
            params_layout.setContentsMargins(0,0,0,0)
            params_layout.setSpacing(4)
            if exec_params:
                for k, v in exec_params.items():
                    display_val = v
                    if k.endswith('_pct') and isinstance(v, float):
                        display_val = f"{v*100:.2f}%"
                    elif k == 'position_size' and isinstance(v, float) and v <= 1:
                        display_val = f"{v*100:.2f}%"
                    params_layout.addWidget(QLabel(f"{k}: {display_val}"))
            else:
                params_layout.addWidget(QLabel("파라미터 없음"))
            scroll_layout.addWidget(self._create_section("🔧 상세 파라미터", ""))
            scroll_layout.addWidget(params_widget)
        except Exception:
            pass

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        
        # (하단 액션 영역은 아래에서 구성)

        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setSpacing(10)
        action_layout.setContentsMargins(0, 10, 0, 0)

        # Apply risk overrides checkbox
        self.risk_override_checkbox = QCheckBox("Apply risk overrides (권장)")
        self.risk_override_checkbox.setChecked(True if self.apply_risk_overrides else False)
        action_layout.addWidget(self.risk_override_checkbox)

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
        # Start from unified executable_parameters
        base_params = self.analysis_data.get('executable_parameters', {}) or {}
        final_params = dict(base_params)  # shallow copy

        applied_overrides = {}
        if getattr(self, 'risk_override_checkbox', None) and self.risk_override_checkbox.isChecked():
            # Apply risk management suggestions (if present) into final params
            rm = self.analysis_data.get('risk_management', {}) or {}
            # map known keys
            if 'stop_loss' in rm:
                final_params['stop_loss_pct'] = float(rm.get('stop_loss'))
                applied_overrides['stop_loss_pct'] = final_params['stop_loss_pct']
            if 'trailing_stop' in rm:
                final_params['trailing_stop_pct'] = float(rm.get('trailing_stop'))
                applied_overrides['trailing_stop_pct'] = final_params['trailing_stop_pct']
            # if backend marks new listing, we may suggest lower leverage via risk_management or presets
            if self.analysis_data.get('is_new_listing') and 'force_leverage' in rm:
                final_params['leverage'] = int(rm.get('force_leverage'))
                applied_overrides['force_leverage'] = final_params['leverage']

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
        msg = QMessageBox(self)
        msg.setWindowTitle("Assign Preview")
        msg.setText("Assign the following strategy parameters to %s?" % engine_name)
        msg.setDetailedText(preview_text)
        msg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
        msg.setDefaultButton(QMessageBox.Ok)
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


