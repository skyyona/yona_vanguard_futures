"""포지션 진입 분석 위젯 - 추세, 게이지, 차트"""
from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class TrendAnalysisWidget(QWidget):
    """추세 분석 위젯 (5분봉/15분봉 + 종합)"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                margin: 2px;
            }
        """)
        
        from PySide6.QtWidgets import QFrame
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(5)
        
        # Error message area (initially hidden)
        self.error_display = QLabel()
        self.error_display.setStyleSheet("""
            QLabel {
                color: #ff6b6b;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                background-color: #ffebee;
                border: 1px solid #ffcdd2;
                margin-bottom: 5px;
            }
        """)
        self.error_display.setAlignment(Qt.AlignCenter)
        self.error_display.setVisible(False)
        main_layout.addWidget(self.error_display)
        
        # Trend analysis content
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Trend labels
        self.trend_5m_label = QLabel("5분봉: 바이낸스 데이터 연결 중")
        self.trend_5m_label.setStyleSheet("color: #666; font-size: 12px;")
        
        self.trend_15m_label = QLabel("15분봉: 바이낸스 데이터 연결 중")
        self.trend_15m_label.setStyleSheet("color: #666; font-size: 12px;")
        
        self.overall_judgment = QLabel("종합: 바이낸스 API 연결 중")
        self.overall_judgment.setStyleSheet("color: #6c757d; font-size: 14px; font-weight: bold;")
        
        layout.addWidget(self.trend_5m_label)
        layout.addWidget(self.trend_15m_label)
        layout.addWidget(self.overall_judgment)
        
        main_layout.addWidget(content_widget)
    
    def show_order_error(self, message: str):
        """주문 관련 오류 메시지 표시"""
        if not message:
            self.error_display.setVisible(False)
            return
            
        self.error_display.setText(message)
        self.error_display.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                background-color: #ffebee;
                border: 1px solid #ffcdd2;
                margin-bottom: 5px;
            }
        """)
        self.error_display.setVisible(True)
        
        # Auto-hide after 10 seconds
        from PySide6.QtCore import QTimer
        QTimer.singleShot(10000, self.clear_order_error)
    
    def clear_order_error(self):
        """주문 오류 메시지 지우기"""
        if hasattr(self, 'error_display'):
            self.error_display.clear()
            self.error_display.setVisible(False)
    
    def update_trend(self, trend_data: Dict[str, Any]):
        """추세 데이터 업데이트 (Binance Live vs1 호환)"""
        try:
            # Clear any existing order errors when updating trend
            self.clear_order_error()
            
            if not isinstance(trend_data, dict):
                return
            
            trend_5m = trend_data.get("5m", {})
            trend_15m = trend_data.get("15m", {})
            overall = trend_data.get("overall", "대기")
            signal_status = trend_data.get("signal_status", "")
            active_signals = trend_data.get("active_signals", [])
            rsi = trend_data.get("rsi", 50)
            entry_score = trend_data.get("entry_signals_score", 0)
            
            if not isinstance(trend_5m, dict):
                trend_5m = {}
            if not isinstance(trend_15m, dict):
                trend_15m = {}
            
            # 5분봉 표시
            direction_5m = trend_5m.get("direction", "데이터수신중")
            strength_5m = trend_5m.get("strength", 0)
            predicted_5m = trend_5m.get("predicted_upside", 0)
            price_status_5m = trend_5m.get("price_status", {})
            status_5m = price_status_5m.get("status", "분석중")
            strength_gauge_5m = self._create_strength_gauge(strength_5m, predicted_5m)
            
            if predicted_5m > 0:
                self.trend_5m_label.setText(
                    f"5분봉: {direction_5m} ({status_5m}) - 상승 에너지: +{predicted_5m:.1f}% {strength_gauge_5m}"
                )
            elif predicted_5m < 0:
                self.trend_5m_label.setText(
                    f"5분봉: {direction_5m} ({status_5m}) - 하락 에너지: {predicted_5m:.1f}% {strength_gauge_5m}"
                )
            else:
                self.trend_5m_label.setText(
                    f"5분봉: {direction_5m} ({status_5m}) - 횡보 중 {strength_gauge_5m}"
                )
            
            # 15분봉 표시
            direction_15m = trend_15m.get("direction", "데이터수신중")
            strength_15m = trend_15m.get("strength", 0)
            predicted_15m = trend_15m.get("predicted_upside", 0)
            price_status_15m = trend_15m.get("price_status", {})
            status_15m = price_status_15m.get("status", "분석중")
            strength_gauge_15m = self._create_strength_gauge(strength_15m, predicted_15m)
            
            if predicted_15m > 0:
                self.trend_15m_label.setText(
                    f"15분봉: {direction_15m} ({status_15m}) - 상승 에너지: +{predicted_15m:.1f}% {strength_gauge_15m}"
                )
            elif predicted_15m < 0:
                self.trend_15m_label.setText(
                    f"15분봉: {direction_15m} ({status_15m}) - 하락 에너지: {predicted_15m:.1f}% {strength_gauge_15m}"
                )
            else:
                self.trend_15m_label.setText(
                    f"15분봉: {direction_15m} ({status_15m}) - 횡보 중 {strength_gauge_15m}"
                )
            
            # 종합 판단 (Binance Live vs1와 동일한 매핑)
            # overall 값에 따라 고정 문구와 색상 매핑
            if overall == "강상승":
                color = "#28a745"; judgment = "거래 권장 ✅ (예상 상승: +12-18%)"
            elif overall == "상승":
                color = "#20c997"; judgment = "거래 고려 🔸 (예상 상승: +5-12%)"
            elif overall == "횡보":
                color = "#ffc107"; judgment = "횡보 중 ⚖️ (가격 변동 미미)"
            elif overall == "하락":
                color = "#dc3545"; judgment = "거래 금지 ❌ (예상 하락: -3-8%)"
            elif overall == "강하락":
                color = "#6f42c1"; judgment = "거래 금지 ❌ (예상 하락: -8-15%)"
            else:
                color = "#6c757d"; judgment = "실시간 분석 중 ⏳"

            # Binance Live vs1 스타일의 핵심 문구 + 보조 정보(동일 행)에 함께 표기
            # RSI/신호/점수 보조 정보 조립
            rsi_desc = "(중립)"
            if isinstance(rsi, (int, float)):
                if rsi > 70: rsi_desc = "(과매수)"
                elif rsi < 30: rsi_desc = "(과매도)"
            signals_text = ", ".join(active_signals) if isinstance(active_signals, list) and active_signals else "신호 없음"
            aux = f"RSI: {float(rsi):.1f} {rsi_desc} | 신호: {signals_text} (점수: {int(entry_score) if isinstance(entry_score, (int, float)) else 0})"
            try:
                safe_color = color if isinstance(color, str) and color.startswith('#') and len(color) == 7 else "#6c757d"
                safe_judgment = judgment.replace(';', '').replace('"', '').replace("'", "")
                safe_aux = aux.replace(';', '').replace('"', '').replace("'", "")
                self.overall_judgment.setText(f"종합: {safe_judgment} | {safe_aux}")
                self.overall_judgment.setStyleSheet(f"color: {safe_color}; font-size: 13px; font-weight: bold;")
            except Exception as style_error:
                print(f"[STYLE] stylesheet error: {style_error}")
                self.overall_judgment.setStyleSheet("color: #6c757d; font-size: 13px; font-weight: bold;")
            
        except Exception as e:
            print(f"[TREND] 업데이트 오류: {e}")
            if not isinstance(trend_15m, dict):
                trend_15m = {}
            
            # 5분봉
            direction_5m = trend_5m.get("direction", "데이터수신중")
            strength_5m = trend_5m.get("strength", 0)
            predicted_5m = trend_5m.get("predicted_upside", 0)
            price_status_5m = trend_5m.get("price_status", {})
            status_5m = price_status_5m.get("status", "분석중")
            strength_gauge_5m = self._create_strength_gauge(strength_5m, predicted_5m)
            
            if predicted_5m > 0:
                self.trend_5m_label.setText(
                    f"5분봉: {direction_5m} ({status_5m}) - 상승 에너지: +{predicted_5m:.1f}% {strength_gauge_5m}"
                )
            elif predicted_5m < 0:
                self.trend_5m_label.setText(
                    f"5분봉: {direction_5m} ({status_5m}) - 하락 에너지: {predicted_5m:.1f}% {strength_gauge_5m}"
                )
            else:
                self.trend_5m_label.setText(
                    f"5분봉: {direction_5m} ({status_5m}) - 횡보 중 {strength_gauge_5m}"
                )
            
            # 15분봉
            direction_15m = trend_15m.get("direction", "데이터수신중")
            strength_15m = trend_15m.get("strength", 0)
            predicted_15m = trend_15m.get("predicted_upside", 0)
            price_status_15m = trend_15m.get("price_status", {})
            status_15m = price_status_15m.get("status", "분석중")
            strength_gauge_15m = self._create_strength_gauge(strength_15m, predicted_15m)
            
            if predicted_15m > 0:
                self.trend_15m_label.setText(
                    f"15분봉: {direction_15m} ({status_15m}) - 상승 에너지: +{predicted_15m:.1f}% {strength_gauge_15m}"
                )
            elif predicted_15m < 0:
                self.trend_15m_label.setText(
                    f"15분봉: {direction_15m} ({status_15m}) - 하락 에너지: {predicted_15m:.1f}% {strength_gauge_15m}"
                )
            else:
                self.trend_15m_label.setText(
                    f"15분봉: {direction_15m} ({status_15m}) - 횡보 중 {strength_gauge_15m}"
                )
            
            # 종합 판단 (backend에서 받은 overall 활용)
            # overall 형식: "강한 상승 추세 (위험도: 낮음, 신뢰도: 높음)"
            rsi = trend_data.get("rsi", 50)
            mom_5m = trend_data.get("momentum_5m", 0)
            mom_15m = trend_data.get("momentum_15m", 0)
            
            # overall 텍스트 색상 결정
            if "강한 상승" in overall:
                color = "#28a745"
            elif "상승" in overall and "약한" not in overall:
                color = "#20c997"
            elif "횡보" in overall:
                color = "#ffc107"
            elif "강한 하락" in overall:
                color = "#6f42c1"
            elif "하락" in overall:
                color = "#dc3545"
            else:
                color = "#6c757d"
            
            # 추가 정보 표시
            rsi_text = f"RSI: {rsi:.1f}"
            if rsi > 70:
                rsi_desc = "(과매수)"
            elif rsi < 30:
                rsi_desc = "(과매도)"
            else:
                rsi_desc = "(중립)"
            
            full_judgment = f"{overall} | {rsi_text} {rsi_desc}"
            
            self.overall_judgment.setText(f"종합: {full_judgment}")
            self.overall_judgment.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
            
        except Exception as e:
            print(f"[TREND] 업데이트 오류: {e}")
    
    def _create_strength_gauge(self, strength: int, predicted: float) -> str:
        """강도 게이지 문자열 생성"""
        gauge_length = 8
        filled_length = int((strength / 100.0) * gauge_length)
        
        if predicted > 0:
            if strength >= 80:
                filled_char, empty_char = "█", "▁"
            elif strength >= 60:
                filled_char, empty_char = "▆", "▁"
            elif strength >= 40:
                filled_char, empty_char = "▃", "▁"
            else:
                filled_char, empty_char = "▁", "▁"
        elif predicted < 0:
            if strength >= 80:
                filled_char, empty_char = "█", "▁"
            elif strength >= 60:
                filled_char, empty_char = "▆", "▁"
            elif strength >= 40:
                filled_char, empty_char = "▃", "▁"
            else:
                filled_char, empty_char = "▁", "▁"
        else:
            filled_char, empty_char = "▃", "▁"
        
        gauge = "".join(filled_char if i < filled_length else empty_char for i in range(gauge_length))
        return f"┌{gauge}┐ {strength}%"


class GaugeWidget(QWidget):
    """게이지 위젯 (0-100 점수 + BPR/VSS)"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._value = 0
        self._display_value = 0.0
        self._bpr = 0.0
        self._vss = 1.0
        self.setMinimumHeight(120)
        self.setMaximumHeight(120)
        
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_anim)
    
    def set_value(self, value: int):
        """점수 설정 (0-100)"""
        v = max(0, min(int(value), 100))
        if v == self._value:
            return
        self._value = v
        if not self._anim_timer.isActive():
            self._anim_timer.start()
        self.update()
    
    def set_metrics(self, bpr: float, vss: float):
        """BPR/VSS 메트릭 설정"""
        try:
            self._bpr = max(0.0, min(float(bpr), 1.0))
        except:
            self._bpr = 0.0
        try:
            self._vss = min(max(0.0, float(vss)), 2.5)
        except:
            self._vss = 1.0
        self.update()
    
    def _on_anim(self):
        """애니메이션 타이머"""
        target = float(self._value)
        curr = self._display_value
        next_val = curr + (target - curr) * 0.4
        
        if abs(next_val - target) < 0.1:
            next_val = target
            self._anim_timer.stop()
        
        self._display_value = next_val
        self.update()
    
    def paintEvent(self, event):
        """페인트 이벤트"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # 배경
        p.fillRect(self.rect(), QColor("#ffffff"))
        
        # 게이지 바 배경
        bar_h = 30
        bar_y = 20
        p.fillRect(10, bar_y, w - 20, bar_h, QColor("#e0e0e0"))
        
        # 게이지 바 (색상: 0-40 빨강, 40-70 주황, 70-100 초록)
        val = self._display_value
        if val > 0:
            bar_w = int((w - 20) * (val / 100.0))
            if val < 40:
                color = QColor("#e16476")
            elif val < 70:
                color = QColor("#ff8c25")
            else:
                color = QColor("#03b662")
            p.fillRect(10, bar_y, bar_w, bar_h, color)
        
        # 점수 텍스트
        p.setPen(QColor("#000000"))
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(0, bar_y, w, bar_h), Qt.AlignCenter, f"{int(val)}")
        
        # BPR/VSS 텍스트
        font.setPointSize(10)
        p.setFont(font)
        p.drawText(10, bar_y + bar_h + 20, f"BPR: {self._bpr:.2f}")
        p.drawText(10, bar_y + bar_h + 40, f"VSS: {self._vss:.2f}")
        
        p.end()


class TimingAnalysisView(QWidget):
    """타이밍 분석 차트 (가격선 + 지표 + 진입/손절/익절)"""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._data: Optional[Dict] = None
        self.setMinimumHeight(240)
    
    def set_data(self, data: Dict[str, Any]):
        """분석 데이터 설정"""
        self._data = data or {}
        QTimer.singleShot(0, self.update)
    
    def paintEvent(self, event):
        """페인트 이벤트"""
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#ffffff"))
        p.setRenderHint(QPainter.Antialiasing, True)
        
        w, h = self.width(), self.height()
        margin_left = 12
        margin_right = 12
        margin_top = 30  # 상단 여백 증가 (심볼 표시 공간)
        margin_bottom = 12
        
        rect = QRectF(margin_left, margin_top, 
                     w - margin_left - margin_right, 
                     h - margin_top - margin_bottom)
        
        if not self._data or not isinstance(self._data, dict) or self._data.get("score") is None:
            p.setPen(QColor("#999"))
            symbol = self._data.get("symbol", "") if self._data else ""
            if symbol:
                p.drawText(rect, int(Qt.AlignCenter), 
                          f"{symbol} 실시간 분석 중...\n바이낸스 API에서 데이터 수집 중")
            else:
                p.drawText(rect, int(Qt.AlignCenter), "심볼을 선택하세요")
            p.end()
            return
        
        series = self._data.get("series", {})
        close = series.get("close", []) if isinstance(series, dict) else []
        ema20 = series.get("ema20", [])
        ema50 = series.get("ema50", [])
        vwap = series.get("vwap", [])
        
        levels = self._data.get("levels", {})
        entry_zone = levels.get("entry_zone", {})
        stop = levels.get("stop")
        tp1 = levels.get("tp1")
        tp2 = levels.get("tp2")
        
        symbol = self._data.get("symbol", "")
        
        if not close or len(close) < 5:
            p.setPen(QColor("#666"))
            p.drawText(rect, int(Qt.AlignCenter), "분석 불가 (데이터 부족)")
            p.end()
            return
        
        # 가격 범위 계산
        vals: List[float] = []
        vals.extend(close)
        if ema20:
            vals.extend([x for x in ema20 if x])
        if ema50:
            vals.extend([x for x in ema50 if x])
        if vwap:
            vals.extend([x for x in vwap if x])
        if isinstance(stop, (int, float)):
            vals.append(float(stop))
        if isinstance(tp1, (int, float)):
            vals.append(float(tp1))
        if isinstance(tp2, (int, float)):
            vals.append(float(tp2))
        
        if not vals:
            p.end()
            return
        
        min_val, max_val = min(vals), max(vals)
        val_range = max_val - min_val
        if val_range == 0:
            val_range = 1
        
        # 좌표 변환 함수
        def xmap(i: int) -> float:
            return rect.left() + (i / max(1, len(close) - 1)) * rect.width()
        
        def ymap(v: float) -> float:
            return rect.bottom() - ((v - min_val) / val_range) * rect.height()
        
        # 선 그리기 함수
        def draw_line(data: List, color: str, width: int):
            if not data or len(data) < 2:
                return
            p.setPen(QPen(QColor(color), width))
            for i in range(len(data) - 1):
                if data[i] and data[i+1]:
                    p.drawLine(int(xmap(i)), int(ymap(float(data[i]))),
                             int(xmap(i+1)), int(ymap(float(data[i+1]))))
        
        # 가격선 및 지표 그리기
        draw_line(close, "#333333", 2)   # Close (검정)
        draw_line(ema20, "#e16476", 1)   # EMA20 (빨강)
        draw_line(ema50, "#2196F3", 1)   # EMA50 (파랑)
        draw_line(vwap, "#9C27B0", 1)    # VWAP (보라)
        
        # 진입존
        if entry_zone and "low" in entry_zone and "high" in entry_zone:
            low, high = float(entry_zone["low"]), float(entry_zone["high"])
            y1, y2 = ymap(high), ymap(low)
            p.fillRect(int(rect.left()), int(y1), int(rect.width()), int(y2 - y1), QColor(0, 255, 0, 30))
        
        # 손절/익절 레벨
        if isinstance(stop, (int, float)):
            y = ymap(float(stop))
            p.setPen(QPen(QColor("#e16476"), 2))
            p.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
        
        if isinstance(tp1, (int, float)):
            y = ymap(float(tp1))
            p.setPen(QPen(QColor("#03b662"), 1))
            p.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
        
        if isinstance(tp2, (int, float)):
            y = ymap(float(tp2))
            p.setPen(QPen(QColor("#03b662"), 1))
            p.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
        
        # 심볼 표시 (차트 위쪽, 여백 내부)
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.setPen(QColor("#333"))
        p.drawText(int(rect.left()), int(margin_top - 10), symbol)
        
        p.end()
