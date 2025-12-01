# 🎯 전략 백테스팅 기능 재설계 설계 보고서 (수정본)

**설계 일시**: 2025-11-20 (수정)  
**작업 상태**: 설계 완료 (구현 대기)  
**목적**: 백테스팅 기능을 전략 분석 기반 자동매매 시스템으로 재설계

---

## 📋 사용자 의도 재확인

### ✅ 정확한 데이터 흐름 및 이벤트 처리

#### 1. 전략 분석 시작
- 사용자가 랭킹 테이블에서 코인 심볼 확인
- "전략 분석" 버튼 클릭
- 해당 코인 심볼의 전략 백테스팅 분석 실행
- 팝업창에 결과 표시 ✅

#### 2. 팝업창에서 엔진 배치
- 팝업창 하단에 **'Assign Trading Symbol: [알파], [베타], [감마]'** 버튼 구현 ✅
- 기존 중단 세션 2열 상단 우측에 배치된 'Assign Trading Symbol' 버튼은 **삭제** ✅

#### 3. Designated Funds, Applied Leverage 설정
- ❌ 팝업창에서 설정하는 것이 아님
- ✅ 기존과 동일하게 각 엔진의 하단 푸터 위젯에서 진행 ✅

#### 4. 설정 적용 및 거래 활성화
- ❌ 팝업창에 추가하는 것이 아님
- ✅ 기존과 동일하게 각 엔진의 하단 푸터 위젯에서 진행 ✅

---

## 🔄 정확한 작업 흐름

### 1. 사용자 작업 흐름 (수정)

```
1. 랭킹 테이블에서 코인 확인
   ↓
2. "전략 분석" 버튼 클릭
   ↓
3. 팝업창 표시 (분석 진행 중 표시)
   ↓
4. 백엔드 API 호출 (3개 엔진별 백테스팅)
   ↓
5. 분석 완료 → 결과 표시
   - 추천 엔진
   - 변동성
   - 최대 목표 수익률%
   - 리스크 관리
   - 엔진별 상세 결과
   ↓
6. 팝업창 하단에서 'Assign Trading Symbol: [알파], [베타], [감마]' 버튼 중 선택
   ↓
7. 팝업창 닫기
   ↓
8. 선택한 엔진의 전략 업데이트
   - 심볼 설정
   - 전략 파라미터 업데이트 (익절/손절 등)
   ↓
9. 하단 푸터의 해당 엔진 위젯으로 자동 이동/포커스
   (또는 사용자가 직접 해당 엔진 탭 클릭)
   ↓
10. 기존과 동일하게 Designated Funds 설정 (하단 푸터 위젯)
   ↓
11. 기존과 동일하게 Applied Leverage 설정 (하단 푸터 위젯)
   ↓
12. 기존과 동일하게 "설정 적용" 버튼 클릭 (하단 푸터 위젯)
    - 바이낸스 API로 레버리지 설정
   ↓
13. 기존과 동일하게 "거래 활성화" 버튼 클릭 (하단 푸터 위젯)
    - 실제 자동매매 거래 시작
```

### 2. 시스템 작업 흐름 (수정)

```
1. GUI: "전략 분석" 버튼 클릭
   ↓
2. GUI: 팝업창 표시 (로딩 인디케이터 표시)
   ↓
3. API: GET /api/v1/backtest/strategy-analysis
   ↓
4. 백엔드:
   - 변동성 계산
   - 3개 엔진별 백테스팅 실행
   - 적합성 평가
   - 최대 목표 수익률% 계산
   - 가장 적합한 엔진 선택
   ↓
5. 응답 반환
   ↓
6. GUI: 팝업창에 결과 표시
   ↓
7. 사용자: 'Assign Trading Symbol: [알파], [베타], [감마]' 버튼 중 선택
   ↓
8. GUI: 팝업창 닫기
   ↓
9. GUI: 선택한 엔진의 전략 업데이트
   - 심볼 설정
   - 전략 파라미터 업데이트
   ↓
10. GUI: 해당 엔진의 하단 푸터 위젯으로 포커스 이동
   ↓
11. 사용자: Designated Funds 설정 (하단 푸터 위젯)
   ↓
12. 사용자: Applied Leverage 설정 (하단 푸터 위젯)
   ↓
13. 사용자: "설정 적용" 버튼 클릭 (하단 푸터 위젯)
   ↓
14. API: POST /api/v1/engine/prepare-symbol (레버리지 설정)
   ↓
15. 사용자: "거래 활성화" 버튼 클릭 (하단 푸터 위젯)
   ↓
16. API: POST /api/v1/engine/start
   ↓
17. 백엔드: 자동매매 거래 시작
```

---

## 📋 요구사항 정리 (수정)

### 1. 타이틀 변경
- **기존**: "거래 적합성"
- **변경**: "전략 백테스팅"
- **위치**: 중단 세션 1열 'Real-time Ranking List'의 2번째 컬럼

### 2. 전략 분석 버튼 추가
- **위치**: 각 코인 심볼 행의 "전략 백테스팅" 컬럼에 버튼 추가
- **버튼 텍스트**: "전략 분석"
- **기능**: 클릭 시 해당 코인 심볼에 대한 전략 분석 실행

### 3. 전략 분석 기능
- 우리 앱 엔진에 구현된 전략 지표 사용
- 3개 엔진 (Alpha, Beta, Gamma) 각각에 대한 백테스팅
- 가장 적합한 전략 자동 선택
- 변동성 기반 최대 목표 수익률% 계산
- 리스크 관리 정보 포함

### 4. 팝업창 표시 (수정)
- 분석 결과를 팝업창에 표시
- 표시 내용:
  - 적용할 전략 (Alpha/Beta/Gamma)
  - 변동성에 따른 최대 목표 수익률%
  - 리스크 관리 정보
  - 엔진별 백테스트 결과 요약
- **하단 버튼**: 'Assign Trading Symbol: [알파], [베타], [감마]' ✅
- ❌ Designated Funds, Applied Leverage 설정 제거
- ❌ 설정 적용, 거래 활성화 버튼 제거

### 5. 기존 2열 상단 우측 버튼 삭제 (수정)
- 기존 중단 세션 2열 상단 우측에 배치된 'Assign Trading Symbol' 버튼 삭제 ✅

### 6. 전략 업데이트 (수정)
- 팝업창에서 엔진 선택 시 해당 엔진의 전략 업데이트
- 백테스팅 분석 결과를 엔진 설정에 반영
- 심볼, 레버리지, 익절/손절 설정 업데이트
- **해당 엔진의 하단 푸터 위젯으로 포커스 이동** ✅

### 7. 엔진 설정 (기존 유지)
- **Designated Funds**: 기존과 동일하게 각 엔진의 하단 푸터 위젯에서 설정 ✅
- **Applied Leverage**: 기존과 동일하게 각 엔진의 하단 푸터 위젯에서 설정 ✅
- **설정 적용** 버튼: 기존과 동일하게 각 엔진의 하단 푸터 위젯에서 진행 ✅

### 8. 거래 활성화 (기존 유지)
- **거래 활성화** 버튼: 기존과 동일하게 각 엔진의 하단 푸터 위젯에서 진행 ✅

---

## 🎯 기능 설계 (수정)

### 1. GUI 변경사항 (수정)

#### 1.1 랭킹 테이블 헤더 변경

**파일**: `gui/widgets/ranking_table_widget.py`

**변경 내용:**
```python
# Line 28
# 기존
self.setHorizontalHeaderLabels(["선택", "거래 적합성", "코인 심볼", "상승률%", "누적", "상승 유형"])

# 변경 후
self.setHorizontalHeaderLabels(["선택", "전략 백테스팅", "코인 심볼", "상승률%", "누적", "상승 유형"])
```

#### 1.2 전략 분석 버튼 추가

**파일**: `gui/widgets/ranking_table_widget.py`

**변경 내용:**
```python
# Line 117-146 수정
# 기존: 텍스트 아이템 표시
# 변경 후: 버튼 위젯 표시

def _create_strategy_analysis_button(self, symbol: str) -> QPushButton:
    """전략 분석 버튼 생성"""
    button = QPushButton("전략 분석")
    button.setProperty("symbol", symbol)
    
    # 버튼 스타일
    button.setStyleSheet("""
        QPushButton {
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            font-size: 9px;
            border: none;
            border-radius: 3px;
            padding: 4px 8px;
            min-width: 60px;
        }
        QPushButton:hover {
            background-color: #66BB6A;
        }
        QPushButton:pressed {
            background-color: #388E3C;
        }
    """)
    
    # 클릭 이벤트 연결
    button.clicked.connect(lambda: self._on_strategy_analysis_clicked(symbol))
    
    return button

def _on_strategy_analysis_clicked(self, symbol: str):
    """전략 분석 버튼 클릭"""
    self.strategy_analysis_requested.emit(symbol)

# Signal 추가
strategy_analysis_requested = Signal(str)  # 전략 분석 요청 시
```

**테이블 populate 메서드 수정:**
```python
# Line 117-146 수정
# 기존
suitability_item = QTableWidgetItem(text)
self.setItem(i, 1, suitability_item)

# 변경 후
# 버튼 위젯으로 변경
button = self._create_strategy_analysis_button(symbol)
button_widget = QWidget()
button_layout = QHBoxLayout(button_widget)
button_layout.addWidget(button)
button_layout.setAlignment(Qt.AlignCenter)
button_layout.setContentsMargins(0, 0, 0, 0)
self.setCellWidget(i, 1, button_widget)
```

#### 1.3 기존 2열 상단 우측 버튼 삭제 (수정)

**파일**: `gui/main.py`

**변경 내용:**
```python
# Line 195-245 수정
# 기존: 'Assign Trading Symbol' 버튼 있음
# 변경 후: 삭제

# 기존 코드 삭제:
# assign_label = QLabel("Assign Trading Symbol:")
# self.alpha_assign_btn = QPushButton("[알파]")
# self.beta_assign_btn = QPushButton("[베타]")
# self.gamma_assign_btn = QPushButton("[감마]")
# ... (버튼 스타일, 이벤트 연결 등 모두 삭제)
# entry_header.addWidget(assign_label)
# entry_header.addWidget(self.alpha_assign_btn)
# entry_header.addWidget(self.beta_assign_btn)
# entry_header.addWidget(self.gamma_assign_btn)

# 변경 후:
# entry_header.addStretch()만 유지
entry_header.addStretch()
```

#### 1.4 팝업창 구현 (수정)

**새 파일**: `gui/widgets/strategy_analysis_dialog.py`

**구현 내용:**
```python
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

class StrategyAnalysisDialog(QDialog):
    """전략 분석 결과 팝업창"""
    
    # Signal 정의
    engine_assigned = Signal(str, dict)  # 엔진 배치 시 (engine_name, strategy_data)
    
    def __init__(self, symbol: str, analysis_data: dict, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.analysis_data = analysis_data
        
        self.setWindowTitle(f"전략 분석 결과 - {symbol}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(600)
        
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. 헤더
        header = QLabel(f"전략 분석 결과: {self.symbol}")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(14)
        header.setFont(header_font)
        layout.addWidget(header)
        
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
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 4-1. 최대 목표 수익률%
        max_profit = self.analysis_data.get("max_target_profit", {})
        profit_section = self._create_section(
            "🎯 최대 목표 수익률%",
            f"Alpha: {max_profit.get('alpha', 0):.2f}%\n"
            f"Beta: {max_profit.get('beta', 0):.2f}%\n"
            f"Gamma: {max_profit.get('gamma', 0):.2f}%"
        )
        scroll_layout.addWidget(profit_section)
        
        # 4-2. 리스크 관리
        risk_mgmt = self.analysis_data.get("risk_management", {})
        risk_section = self._create_section(
            "⚠️ 리스크 관리",
            f"손절: {risk_mgmt.get('stop_loss', 0):.2f}%\n"
            f"트레일링 스톱: {risk_mgmt.get('trailing_stop', 0):.2f}%"
        )
        scroll_layout.addWidget(risk_section)
        
        # 4-3. 엔진별 상세 결과
        engine_results = self.analysis_data.get("engine_results", {})
        for engine_name in ["alpha", "beta", "gamma"]:
            engine_data = engine_results.get(engine_name, {})
            engine_section = self._create_engine_section(engine_name, engine_data)
            scroll_layout.addWidget(engine_section)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # 5. 엔진 배치 버튼 (하단) - 수정됨
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(10)
        
        # 'Assign Trading Symbol:' 라벨
        assign_label = QLabel("Assign Trading Symbol:")
        assign_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #999;")
        button_layout.addWidget(assign_label)
        
        # 엔진별 버튼
        engines = [
            ("Alpha", "#4CAF50", "[알파]"),
            ("Beta", "#2196F3", "[베타]"),
            ("Gamma", "#FF9800", "[감마]")
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
            
            # 클릭 이벤트
            btn.clicked.connect(
                lambda checked, e=engine_name: self._on_engine_assigned(e)
            )
            
            button_layout.addWidget(btn)
        
        button_layout.addStretch()
        layout.addWidget(button_container)
    
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
        """엔진별 상세 결과 섹션"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        suitability = engine_data.get("suitability", "부적합")
        score = engine_data.get("score", 0)
        expected_profit = engine_data.get("expected_profit", 0)
        win_rate = engine_data.get("win_rate", 0)
        
        title = f"🔧 {engine_name.upper()} 엔진"
        content = (
            f"적합성: {suitability} ({score:.0f}점)\n"
            f"예상 수익률: {expected_profit:.2f}%\n"
            f"승률: {win_rate:.1f}%"
        )
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #2196F3;")
        layout.addWidget(title_label)
        
        content_label = QLabel(content)
        content_label.setStyleSheet("font-size: 10px; color: #CCCCCC;")
        layout.addWidget(content_label)
        
        return widget
    
    def _lighten_color(self, color: str) -> str:
        """색상 밝게"""
        # 간단한 색상 밝게 처리
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
    
    def _on_engine_assigned(self, engine_name: str):
        """엔진 배치 버튼 클릭"""
        # 전략 데이터 준비
        strategy_data = {
            "symbol": self.symbol,
            "engine_name": engine_name,
            "analysis_data": self.analysis_data
        }
        
        # Signal 발송
        self.engine_assigned.emit(engine_name, strategy_data)
        
        # 팝업창 닫기
        self.accept()
```

### 2. 전략 업데이트 기능 (수정)

#### 2.1 엔진 전략 업데이트 및 포커스 이동

**파일**: `gui/main.py`

**구현 내용:**
```python
def _on_strategy_engine_assigned(self, engine_name: str, strategy_data: dict):
    """전략 분석 후 엔진 배치"""
    symbol = strategy_data.get("symbol")
    analysis_data = strategy_data.get("analysis_data", {})
    
    # 엔진별 전략 설정 추출
    engine_results = analysis_data.get("engine_results", {})
    engine_key = engine_name.lower()
    engine_result = engine_results.get(engine_key, {})
    
    # 최대 목표 수익률%
    max_profit = analysis_data.get("max_target_profit", {}).get(engine_key, 0)
    
    # 리스크 관리
    risk_mgmt = analysis_data.get("risk_management", {})
    
    # 엔진에 전략 설정 적용
    # 1. 심볼 설정
    # 2. 레버리지 설정 (엔진별 기본값)
    # 3. 익절/손절 설정 (분석 결과 기반)
    
    # 하단 푸터의 해당 엔진에 전달
    if engine_name == "Alpha":
        self.footer_widget.alpha_engine.update_strategy_from_analysis(
            symbol, max_profit, risk_mgmt
        )
        # 해당 엔진 탭으로 포커스 이동
        self._focus_engine_tab("Alpha")
        
    elif engine_name == "Beta":
        self.footer_widget.beta_engine.update_strategy_from_analysis(
            symbol, max_profit, risk_mgmt
        )
        # 해당 엔진 탭으로 포커스 이동
        self._focus_engine_tab("Beta")
        
    elif engine_name == "Gamma":
        self.footer_widget.gamma_engine.update_strategy_from_analysis(
            symbol, max_profit, risk_mgmt
        )
        # 해당 엔진 탭으로 포커스 이동
        self._focus_engine_tab("Gamma")

def _focus_engine_tab(self, engine_name: str):
    """해당 엔진 탭으로 포커스 이동"""
    # 푸터 위젯의 엔진 탭 인덱스 확인
    engine_tab_map = {
        "Alpha": 0,
        "Beta": 1,
        "Gamma": 2
    }
    
    tab_index = engine_tab_map.get(engine_name, 0)
    
    # 푸터 위젯의 탭 위젯 가져오기
    if hasattr(self.footer_widget, 'engine_tabs'):
        self.footer_widget.engine_tabs.setCurrentIndex(tab_index)
        
        # 해당 엔진 위젯으로 스크롤 이동 (선택사항)
        # self.footer_widget.scroll_area.ensureWidgetVisible(self.footer_widget.engine_tabs.widget(tab_index))
```

#### 2.2 엔진 위젯 전략 업데이트 메서드

**파일**: `gui/widgets/footer_engines_widget.py`

**구현 내용:**
```python
def update_strategy_from_analysis(
    self,
    symbol: str,
    max_target_profit: float,
    risk_management: dict
):
    """전략 분석 결과로 엔진 설정 업데이트"""
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
    
    # 3. 리스크 관리 업데이트 (참고용, 실제 적용은 Orchestrator에서)
    stop_loss = risk_management.get("stop_loss", 0.5)
    trailing_stop = risk_management.get("trailing_stop", 0.3)
    
    # 4. 엔진 설정 업데이트 (Orchestrator에 반영)
    # 이 부분은 API를 통해 백엔드로 전달되어 처리됨
    # 실제 전략 파라미터 업데이트는 백엔드 API 호출 시 진행
```

### 3. 백엔드 전략 업데이트 API (기존 유지)

**기존 엔드포인트 활용**: `POST /api/v1/engine/prepare-symbol`

**파일**: `backend/api/routes.py`

**기존 구현 활용:**
- 심볼 설정
- 레버리지 설정
- 바이낸스 API로 레버리지 설정

**추가 필요 사항:**
- 전략 파라미터 업데이트 (익절/손절 등)
- 이 부분은 Orchestrator 구조 확인 후 구현

---

## 📋 파일 변경 목록 (수정)

### 1. GUI 파일

#### 1.1 수정 파일
- `gui/widgets/ranking_table_widget.py`
  - 헤더 레이블 변경: "거래 적합성" → "전략 백테스팅"
  - 컬럼 1을 텍스트 아이템에서 버튼 위젯으로 변경
  - "전략 분석" 버튼 추가
  - Signal 추가: `strategy_analysis_requested`

- `gui/main.py`
  - **기존 2열 상단 우측 'Assign Trading Symbol' 버튼 삭제** ✅
  - 전략 분석 요청 핸들러 추가: `_on_strategy_analysis_requested`
  - 팝업창 표시 로직 추가
  - 엔진 배치 핸들러 수정: `_on_strategy_engine_assigned`
  - 엔진 탭 포커스 이동 함수 추가: `_focus_engine_tab`
  - Signal 연결 추가

- `gui/widgets/footer_engines_widget.py`
  - 전략 업데이트 메서드 추가: `update_strategy_from_analysis`
  - (Designated Funds, Applied Leverage, 설정 적용, 거래 활성화는 기존 유지)

#### 1.2 신규 파일
- `gui/widgets/strategy_analysis_dialog.py`
  - 전략 분석 결과 팝업창 위젯
  - 하단에 'Assign Trading Symbol: [알파], [베타], [감마]' 버튼만 포함

### 2. 백엔드 파일

#### 2.1 수정 파일
- `backend/api/routes.py`
  - 새로운 엔드포인트 추가: `/backtest/strategy-analysis`
  - 변동성 계산 함수 추가
  - 최대 목표 수익률% 계산 함수 추가
  - (기존 `/engine/prepare-symbol` 엔드포인트는 유지)

---

## ✅ 구현 체크리스트 (수정)

### Phase 1: GUI 변경
- [ ] 랭킹 테이블 헤더 변경: "거래 적합성" → "전략 백테스팅"
- [ ] "전략 분석" 버튼 추가
- [ ] 버튼 클릭 이벤트 구현
- [ ] Signal 연결
- [ ] **기존 2열 상단 우측 'Assign Trading Symbol' 버튼 삭제** ✅

### Phase 2: 전략 분석 API
- [ ] 변동성 계산 함수 구현
- [ ] 엔진별 백테스팅 실행 로직
- [ ] 최대 목표 수익률% 계산 함수
- [ ] 가장 적합한 엔진 선택 로직
- [ ] API 엔드포인트 구현

### Phase 3: 팝업창
- [ ] 팝업창 위젯 생성
- [ ] 결과 표시 UI 구현
- [ ] **하단에 'Assign Trading Symbol: [알파], [베타], [감마]' 버튼만 구현** ✅
- [ ] Signal 연결

### Phase 4: 전략 업데이트
- [ ] 엔진 전략 업데이트 메서드 구현
- [ ] 엔진 탭 포커스 이동 함수 구현
- [ ] Orchestrator 설정 업데이트 로직 (필요 시)

### Phase 5: 기존 기능 유지 확인
- [ ] Designated Funds 설정 (기존 유지) ✅
- [ ] Applied Leverage 설정 (기존 유지) ✅
- [ ] 설정 적용 버튼 (기존 유지) ✅
- [ ] 거래 활성화 버튼 (기존 유지) ✅

### Phase 6: 테스트
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] 사용자 시나리오 테스트

---

## ⚠️ 주의사항 (수정)

### 1. 기존 기능 유지
- ❌ Designated Funds, Applied Leverage를 팝업창에 추가하지 않음
- ❌ 설정 적용, 거래 활성화 버튼을 팝업창에 추가하지 않음
- ✅ 기존과 동일하게 하단 푸터 위젯에서 진행

### 2. 버튼 위치 변경
- ✅ 기존 2열 상단 우측 'Assign Trading Symbol' 버튼 삭제
- ✅ 팝업창 하단에 'Assign Trading Symbol: [알파], [베타], [감마]' 버튼 추가

### 3. 엔진 포커스 이동
- 팝업창에서 엔진 선택 시 해당 엔진의 하단 푸터 위젯으로 자동 포커스 이동
- 사용자가 바로 Designated Funds, Applied Leverage 설정 가능하도록

### 4. Orchestrator 구조 확인 필요
- Orchestrator 내부 전략 파라미터 업데이트 방법 확인
- 익절/손절 설정 변경 방법 확인

---

**설계 완료일**: 2025-11-20 (수정)  
**다음 단계**: 사용자 승인 후 구현 작업 시작


