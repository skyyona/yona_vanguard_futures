"""급등 예상 코인 위젯"""
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtGui import QFont


class SurgeBarWidget(QWidget):
    """거래량 증가 게이지 바"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._level = 0
        self._color = "#888888"
        self.setMinimumHeight(12)
        self.setMaximumHeight(12)
    
    def setLevel(self, level: int):
        """레벨 설정 (0-100)"""
        self._level = max(0, min(int(level), 100))
        self.update()
    
    def setBarColor(self, color: str):
        """바 색상 설정"""
        self._color = color if color and color.startswith('#') else "#888888"
        self.update()
    
    def paintEvent(self, event):
        """페인트 이벤트"""
        from PySide6.QtGui import QPainter, QColor, QPen
        from PySide6.QtCore import QRectF
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 배경
        painter.fillRect(self.rect(), QColor("#1e1e1e"))
        
        # 게이지 바
        if self._level > 0:
            width = int(self.width() * (self._level / 100.0))
            painter.fillRect(0, 0, width, self.height(), QColor(self._color))
        
        # 테두리
        painter.setPen(QPen(QColor("#444444"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        
        painter.end()


class SurgePredictionWidget(QWidget):
    """금일 최고 상승 예상 코인 위젯"""
    
    # 시그널
    symbol_clicked = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._surge_symbol = ""
        self._init_ui()
    
    def _init_ui(self):
        """UI 초기화"""
        self.setStyleSheet("""
            QWidget {
                background-color: #2c2c2c;
                border: 1px solid #444444;
                border-radius: 8px;
                margin: 2px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(2)
        
        # 타이틀
        title = QLabel("금일 최고 상승 예상 코인")
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #ffffff; padding: 2px;")
        layout.addWidget(title)
        
        # 첫 번째 행: 심볼(좌), 현재 상승률(중), 예상률(우)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        
        # 심볼 버튼
        self.surge_symbol_button = QPushButton("-")
        self.surge_symbol_button.setStyleSheet("""
            QPushButton { 
                color: #ffffff; 
                font-weight: bold; 
                font-size: 12px; 
                background: transparent; 
                border: none; 
                text-align: left; 
                padding: 0px;
            } 
            QPushButton:hover { 
                color: #4caf50; 
                text-decoration: underline; 
            }
        """)
        self.surge_symbol_button.clicked.connect(self._on_symbol_clicked)
        
        # 현재 상승률
        self.surge_current_change_label = QLabel("")
        self.surge_current_change_label.setStyleSheet("color: #4caf50; font-weight: bold; font-size: 12px;")
        self.surge_current_change_label.setAlignment(Qt.AlignCenter)
        
        # 예상 상승률
        self.surge_predicted_label = QLabel("")
        self.surge_predicted_label.setStyleSheet("color: #888888; font-weight: bold; font-size: 12px;")
        self.surge_predicted_label.setAlignment(Qt.AlignRight)
        
        top_row.addWidget(self.surge_symbol_button, 1)
        top_row.addWidget(self.surge_current_change_label, 1)
        top_row.addWidget(self.surge_predicted_label, 1)
        layout.addLayout(top_row)
        
        # 두 번째 행: 거래대금
        self.surge_volume_label = QLabel("거래대금: -")
        self.surge_volume_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")
        layout.addWidget(self.surge_volume_label)
        
        # 세 번째 행: 거래량 증가 바
        self.surge_bar = SurgeBarWidget(self)
        self.surge_bar.setMinimumHeight(12)
        self.surge_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.surge_bar)
        
        # 네 번째 행: 메시지
        self.surge_message_label = QLabel("데이터수신중")
        self.surge_message_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")
        layout.addWidget(self.surge_message_label)
    
    def update_data(self, data: Dict[str, Any]):
        """급등 예상 데이터 업데이트"""
        try:
            symbol = data.get("symbol", "")
            current_change = data.get("current_change", 0.0)
            predicted_upside = data.get("predicted_upside", 0.0)
            volume = data.get("volume", 0.0)
            level = int(data.get("gauge_level", 0))
            msg = data.get("message", "데이터수신중")
            
            # 라벨 정보
            labels = []
            if data.get('is_volume_spike'):
                labels.append('이상 거래량 급증')
            if data.get('is_consecutive_bull'):
                labels.append('연속 양봉')
            if data.get('is_new_listing'):
                days = data.get('listing_days', 0)
                labels.append(f'신규 {days}일')
            label_text = ' '.join(f'[{l}]' for l in labels)
            
            # level 기반 색상
            if level >= 16:
                color = "#ff5722"
            elif level >= 12:
                color = "#4caf50"
            elif level >= 8:
                color = "#2196f3"
            elif level >= 4:
                color = "#ff9800"
            else:
                color = "#9e9e9e"
            
            # UI 업데이트
            self._surge_symbol = symbol or self._surge_symbol
            self.surge_symbol_button.setText(symbol or "-")
            
            # 현재 상승률
            if current_change > 0:
                self.surge_current_change_label.setText(f"+{current_change:.1f}%")
                self.surge_current_change_label.setStyleSheet("color: #4caf50; font-weight: bold; font-size: 12px;")
            elif current_change < 0:
                self.surge_current_change_label.setText(f"{current_change:.1f}%")
                self.surge_current_change_label.setStyleSheet("color: #f44336; font-weight: bold; font-size: 12px;")
            else:
                self.surge_current_change_label.setText("0.0%")
                self.surge_current_change_label.setStyleSheet("color: #888888; font-weight: bold; font-size: 12px;")
            
            # 예상 상승률
            if predicted_upside > 0:
                self.surge_predicted_label.setText(f"예상: +{predicted_upside:.0f}%")
            else:
                self.surge_predicted_label.setText("예상: 0%")
            
            # 거래대금
            if volume >= 1000000:
                volume_text = f"거래대금: {volume:,.0f} USDT"
            else:
                volume_text = f"거래대금: {volume:.0f} USDT"
            self.surge_volume_label.setText(volume_text)
            
            # 메시지 + 라벨
            if label_text:
                self.surge_message_label.setText(f"{msg} {label_text}")
            else:
                self.surge_message_label.setText(msg)
            
            # 게이지 바
            validated_level = max(0, min(int(level), 100))
            self.surge_bar.setLevel(validated_level)
            self.surge_bar.setBarColor(color)
            
        except Exception as e:
            print(f"[SURGE] 업데이트 오류: {e}")
    
    def _on_symbol_clicked(self):
        """심볼 버튼 클릭"""
        if self._surge_symbol:
            self.symbol_clicked.emit(self._surge_symbol)
            # 바이낸스 페이지 열기
            import webbrowser
            url = f"https://www.binance.com/en/futures/{self._surge_symbol}"
            webbrowser.open(url)
