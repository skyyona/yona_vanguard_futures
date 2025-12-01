# 🎯 전략 백테스팅 기능 재설계 설계 보고서

**설계 일시**: 2025-11-20  
**작업 상태**: 설계 완료 (구현 대기)  
**목적**: 백테스팅 기능을 전략 분석 기반 자동매매 시스템으로 재설계

---

## 📋 요구사항 정리

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

### 4. 팝업창 표시
- 분석 결과를 팝업창에 표시
- 표시 내용:
  - 적용할 전략 (Alpha/Beta/Gamma)
  - 변동성에 따른 최대 목표 수익률%
  - 리스크 관리 정보
  - 엔진별 백테스트 결과 요약

### 5. 팝업창 하단 버튼
- **위치**: 팝업창 하단
- **버튼**: [알파], [베타], [감마]
- **기능**: 선택한 엔진에 전략 배치

### 6. 전략 업데이트
- 엔진 배치 버튼 클릭 시 해당 엔진의 전략 업데이트
- 백테스팅 분석 결과를 엔진 설정에 반영

### 7. 엔진 설정
- **Designated Funds**: 투입 자금 비율 설정
- **Applied Leverage**: 레버리지 설정
- **설정 적용** 버튼: 바이낸스 API로 설정 적용

### 8. 거래 활성화
- **거래 활성화** 버튼: 실제 자동매매 거래 시작

---

## 🎯 기능 설계

### 1. GUI 변경사항

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

def _create_strategy_analysis_button(self, symbol: str, status: str, score: float) -> QPushButton:
    """전략 분석 버튼 생성"""
    button = QPushButton("전략 분석")
    button.setProperty("symbol", symbol)
    button.setProperty("status", status)
    button.setProperty("score", score)
    
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
button = self._create_strategy_analysis_button(symbol, status, score)
button_widget = QWidget()
button_layout = QHBoxLayout(button_widget)
button_layout.addWidget(button)
button_layout.setAlignment(Qt.AlignCenter)
button_layout.setContentsMargins(0, 0, 0, 0)
self.setCellWidget(i, 1, button_widget)
```

### 2. 전략 분석 기능

#### 2.1 백엔드 API

**새로운 엔드포인트**: `GET /api/v1/backtest/strategy-analysis`

**파일**: `backend/api/routes.py`

**구현 내용:**
```python
@router.get("/backtest/strategy-analysis")
async def get_strategy_analysis(
    symbol: str,
    period: str = "1w"
):
    """
    코인 심볼에 대한 전략 분석 (3개 엔진별 백테스팅)
    
    Args:
        symbol: 코인 심볼 (예: "BTCUSDT")
        period: 백테스트 기간 ("1w" or "1m")
    
    Returns:
        {
            "success": true,
            "data": {
                "symbol": "BTCUSDT",
                "best_engine": "Alpha",  # 가장 적합한 엔진
                "volatility": 2.5,  # 변동성 (%)
                "max_target_profit": {
                    "alpha": 3.7,  # Alpha 최대 목표 수익률%
                    "beta": 5.0,   # Beta 최대 목표 수익률%
                    "gamma": 8.5   # Gamma 최대 목표 수익률%
                },
                "risk_management": {
                    "stop_loss": 0.5,  # 손절 (%)
                    "trailing_stop": 0.3  # 트레일링 스톱 (%)
                },
                "engine_results": {
                    "alpha": {
                        "suitability": "적합",
                        "score": 85.0,
                        "expected_profit": 3.2,
                        "win_rate": 65.0,
                        "metrics": {...}
                    },
                    "beta": {
                        "suitability": "주의 필요",
                        "score": 55.0,
                        "expected_profit": 4.5,
                        "win_rate": 50.0,
                        "metrics": {...}
                    },
                    "gamma": {
                        "suitability": "부적합",
                        "score": 30.0,
                        "expected_profit": 7.0,
                        "win_rate": 35.0,
                        "metrics": {...}
                    }
                }
            }
        }
    """
    # 1. 공유 BinanceClient 가져오기
    engine_manager = get_engine_manager()
    shared_binance_client = engine_manager._shared_binance_client
    
    # 2. 변동성 계산
    volatility = await calculate_volatility(symbol, shared_binance_client)
    
    # 3. 3개 엔진별 백테스팅 실행
    engine_results = {}
    
    for engine_name in ["Alpha", "Beta", "Gamma"]:
        # 엔진별 전략 설정
        from backend.core.new_strategy import StrategyOrchestrator, OrchestratorConfig
        
        # 엔진별 기본 설정
        engine_configs = {
            "Alpha": {"leverage": 5, "order_quantity": 0.001, "timeframe": "1m"},
            "Beta": {"leverage": 3, "order_quantity": 0.001, "timeframe": "5m"},
            "Gamma": {"leverage": 2, "order_quantity": 0.001, "timeframe": "1h"}
        }
        
        config = engine_configs[engine_name]
        orchestrator_config = OrchestratorConfig(
            symbol=symbol,
            leverage=config["leverage"],
            order_quantity=config["order_quantity"],
            enable_trading=False,
        )
        
        orchestrator = StrategyOrchestrator(
            binance_client=shared_binance_client,
            config=orchestrator_config
        )
        
        # 백테스트 실행
        from backend.core.new_strategy.backtest_adapter import BacktestAdapter, BacktestConfig
        
        end_date = datetime.now()
        if period == "1w":
            start_date = end_date - timedelta(days=7)
        elif period == "1m":
            start_date = end_date - timedelta(days=30)
        
        backtest_config = BacktestConfig(
            symbol=symbol,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            initial_balance=10000.0,
            leverage=config["leverage"],
            commission_rate=0.0004,
            slippage_rate=0.0001,
        )
        
        adapter = BacktestAdapter(shared_binance_client)
        results = adapter.run_backtest(orchestrator, backtest_config)
        
        # 적합성 평가
        suitability, score = evaluate_suitability(results)
        
        # 변동성 기반 최대 목표 수익률% 계산
        max_target_profit = calculate_max_target_profit(
            engine_name, volatility, results
        )
        
        engine_results[engine_name.lower()] = {
            "suitability": suitability,
            "score": score,
            "expected_profit": results.get("total_pnl_pct", 0),
            "win_rate": results.get("win_rate", 0),
            "metrics": results
        }
    
    # 4. 가장 적합한 엔진 선택
    best_engine = max(
        engine_results.items(),
        key=lambda x: x[1]["score"]
    )[0].capitalize()
    
    # 5. 최대 목표 수익률% 계산 (변동성 기반)
    max_target_profit = {
        "alpha": min(3.7, volatility * 1.5),  # 변동성의 1.5배, 최대 3.7%
        "beta": min(5.0, volatility * 2.0),   # 변동성의 2.0배, 최대 5.0%
        "gamma": min(8.5, volatility * 3.0)   # 변동성의 3.0배, 최대 8.5%
    }
    
    # 6. 리스크 관리 정보
    risk_management = {
        "stop_loss": 0.5,      # 손절 0.5% (모든 엔진 공통)
        "trailing_stop": 0.3   # 트레일링 스톱 0.3% (모든 엔진 공통)
    }
    
    return {
        "success": True,
        "data": {
            "symbol": symbol,
            "best_engine": best_engine,
            "volatility": volatility,
            "max_target_profit": max_target_profit,
            "risk_management": risk_management,
            "engine_results": engine_results
        }
    }
```

#### 2.2 변동성 계산 함수

**구현 내용:**
```python
async def calculate_volatility(symbol: str, binance_client) -> float:
    """
    코인의 변동성 계산 (24시간 기준)
    
    Returns:
        변동성 (%)
    """
    # 24시간 티커 데이터 조회
    ticker = binance_client.get_24hr_ticker(symbol)
    
    if "error" in ticker:
        return 0.0
    
    # 변동성 계산: (고가 - 저가) / 현재가 * 100
    high_price = float(ticker.get("highPrice", 0))
    low_price = float(ticker.get("lowPrice", 0))
    current_price = float(ticker.get("lastPrice", 0))
    
    if current_price == 0:
        return 0.0
    
    volatility = ((high_price - low_price) / current_price) * 100
    return round(volatility, 2)
```

#### 2.3 최대 목표 수익률% 계산 함수

**구현 내용:**
```python
def calculate_max_target_profit(
    engine_name: str,
    volatility: float,
    backtest_results: Dict[str, Any]
) -> float:
    """
    변동성 기반 최대 목표 수익률% 계산
    
    Args:
        engine_name: 엔진명 ("Alpha", "Beta", "Gamma")
        volatility: 변동성 (%)
        backtest_results: 백테스트 결과
    
    Returns:
        최대 목표 수익률%
    """
    # 엔진별 기본 익절률
    base_profit = {
        "Alpha": 3.7,
        "Beta": 5.0,
        "Gamma": 8.5
    }
    
    # 변동성 기반 조정
    volatility_multiplier = {
        "Alpha": 1.5,  # 변동성의 1.5배
        "Beta": 2.0,   # 변동성의 2.0배
        "Gamma": 3.0   # 변동성의 3.0배
    }
    
    base = base_profit.get(engine_name, 3.7)
    multiplier = volatility_multiplier.get(engine_name, 1.5)
    
    # 변동성 기반 계산 (최대 기본 익절률 제한)
    volatility_based = volatility * multiplier
    max_profit = min(base, volatility_based)
    
    # 백테스트 결과 반영 (예상 수익률의 80%를 안전 마진으로 설정)
    expected_profit = backtest_results.get("total_pnl_pct", 0)
    if expected_profit > 0:
        max_profit = min(max_profit, expected_profit * 0.8)
    
    return round(max_profit, 2)
```

### 3. 팝업창 구현

#### 3.1 팝업창 위젯

**새 파일**: `gui/widgets/strategy_analysis_dialog.py`

**구현 내용:**
```python
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QScrollArea, QWidget
)
from PySide6.QtCore import Qt
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
        self.setMinimumHeight(700)
        
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
        
        # 5. 엔진 배치 버튼 (하단)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
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
                    border-radius: 4px;
                    padding: 8px 20px;
                    min-width: 80px;
                }}
                QPushButton:hover {{
                    background-color: {self._lighten_color(color)};
                }}
            """)
            
            # 클릭 이벤트
            btn.clicked.connect(
                lambda checked, e=engine_name: self._on_engine_assigned(e)
            )
            
            button_layout.addWidget(btn)
        
        layout.addLayout(button_layout)
    
    def _create_section(self, title: str, content: str) -> QWidget:
        """섹션 위젯 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
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

### 4. 전략 업데이트 기능

#### 4.1 엔진 전략 업데이트

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
    elif engine_name == "Beta":
        self.footer_widget.beta_engine.update_strategy_from_analysis(
            symbol, max_profit, risk_mgmt
        )
    elif engine_name == "Gamma":
        self.footer_widget.gamma_engine.update_strategy_from_analysis(
            symbol, max_profit, risk_mgmt
        )
```

#### 4.2 엔진 위젯 전략 업데이트 메서드

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
    
    # 3. 리스크 관리 업데이트
    stop_loss = risk_management.get("stop_loss", 0.5)
    trailing_stop = risk_management.get("trailing_stop", 0.3)
    
    # 엔진 설정 업데이트 (Orchestrator에 반영)
    if hasattr(self, 'orchestrator') and self.orchestrator:
        # Orchestrator 설정 업데이트
        self.orchestrator.cfg.symbol = symbol
        # 익절/손절 설정 업데이트 (Orchestrator 내부 전략에 반영 필요)
        # 이 부분은 Orchestrator 구조에 따라 구현 필요
```

### 5. 백엔드 전략 업데이트 API

**새로운 엔드포인트**: `POST /api/v1/engine/update-strategy`

**파일**: `backend/api/routes.py`

**구현 내용:**
```python
class UpdateStrategyRequest(BaseModel):
    engine: str  # "Alpha", "Beta", "Gamma"
    symbol: str
    max_target_profit: float
    stop_loss: float
    trailing_stop: float
    leverage: int
    order_quantity: float

@router.post("/engine/update-strategy")
async def update_engine_strategy(request: UpdateStrategyRequest):
    """
    엔진 전략 설정 업데이트
    
    Args:
        engine: 엔진명
        symbol: 코인 심볼
        max_target_profit: 최대 목표 수익률%
        stop_loss: 손절%
        trailing_stop: 트레일링 스톱%
        leverage: 레버리지
        order_quantity: 주문 수량
    
    Returns:
        {"status": "success", "message": "..."}
    """
    engine_manager = get_engine_manager()
    
    if request.engine not in ["Alpha", "Beta", "Gamma"]:
        raise HTTPException(status_code=400, detail="Invalid engine name")
    
    engine = engine_manager.engines.get(request.engine)
    if not engine:
        raise HTTPException(status_code=404, detail="Engine not found")
    
    # 엔진 설정 업데이트
    if hasattr(engine, 'orchestrator') and engine.orchestrator:
        # Orchestrator 설정 업데이트
        engine.orchestrator.cfg.symbol = request.symbol
        engine.orchestrator.cfg.leverage = request.leverage
        engine.orchestrator.cfg.order_quantity = request.order_quantity
        
        # 전략 파라미터 업데이트 (Orchestrator 내부 전략에 반영)
        # 이 부분은 Orchestrator 구조에 따라 구현 필요
    
    return {
        "status": "success",
        "message": f"{request.engine} 엔진 전략이 업데이트되었습니다."
    }
```

---

## 📋 파일 변경 목록

### 1. GUI 파일

#### 1.1 수정 파일
- `gui/widgets/ranking_table_widget.py`
  - 헤더 레이블 변경: "거래 적합성" → "전략 백테스팅"
  - 컬럼 1을 텍스트 아이템에서 버튼 위젯으로 변경
  - "전략 분석" 버튼 추가
  - Signal 추가: `strategy_analysis_requested`

- `gui/main.py`
  - 전략 분석 요청 핸들러 추가: `_on_strategy_analysis_requested`
  - 팝업창 표시 로직 추가
  - 엔진 배치 핸들러 수정: `_on_strategy_engine_assigned`
  - Signal 연결 추가

#### 1.2 신규 파일
- `gui/widgets/strategy_analysis_dialog.py`
  - 전략 분석 결과 팝업창 위젯

### 2. 백엔드 파일

#### 2.1 수정 파일
- `backend/api/routes.py`
  - 새로운 엔드포인트 추가: `/backtest/strategy-analysis`
  - 새로운 엔드포인트 추가: `/engine/update-strategy`
  - 변동성 계산 함수 추가
  - 최대 목표 수익률% 계산 함수 추가

---

## 🔄 작업 흐름

### 1. 사용자 작업 흐름

```
1. 랭킹 테이블에서 코인 확인
   ↓
2. "전략 분석" 버튼 클릭
   ↓
3. 팝업창 표시 (분석 진행 중 표시)
   ↓
4. 분석 완료 → 결과 표시
   - 추천 엔진
   - 변동성
   - 최대 목표 수익률%
   - 리스크 관리
   - 엔진별 상세 결과
   ↓
5. [알파]/[베타]/[감마] 버튼 중 선택
   ↓
6. 선택한 엔진의 전략 업데이트
   ↓
7. 하단 푸터의 해당 엔진에서:
   - Designated Funds 설정
   - Applied Leverage 설정
   ↓
8. "설정 적용" 버튼 클릭
   - 바이낸스 API로 레버리지 설정
   ↓
9. "거래 활성화" 버튼 클릭
   - 실제 자동매매 거래 시작
```

### 2. 시스템 작업 흐름

```
1. GUI: "전략 분석" 버튼 클릭
   ↓
2. API: GET /api/v1/backtest/strategy-analysis
   ↓
3. 백엔드:
   - 변동성 계산
   - 3개 엔진별 백테스팅 실행
   - 적합성 평가
   - 최대 목표 수익률% 계산
   - 가장 적합한 엔진 선택
   ↓
4. 응답 반환
   ↓
5. GUI: 팝업창에 결과 표시
   ↓
6. 사용자: 엔진 선택
   ↓
7. GUI: 엔진에 전략 배치
   ↓
8. API: POST /api/v1/engine/update-strategy
   ↓
9. 백엔드: 엔진 설정 업데이트
   ↓
10. GUI: 하단 푸터 엔진 위젯 업데이트
```

---

## ⚠️ 주의사항 및 제약사항

### 1. 성능 고려사항
- 3개 엔진별 백테스팅 실행 시 시간 소요 (약 10-30초)
- 진행 중 표시 필요 (로딩 인디케이터)
- 타임아웃 설정 (30초)

### 2. 캐싱 전략
- 동일 심볼 + 기간 조합은 캐시 활용
- 분석 결과는 일정 시간 동안 유효 (예: 5분)

### 3. 오류 처리
- 백테스팅 실패 시 오류 메시지 표시
- API 오류 시 재시도 로직
- 네트워크 오류 처리

### 4. Orchestrator 구조 확인 필요
- Orchestrator 내부 전략 파라미터 업데이트 방법 확인
- 익절/손절 설정 변경 방법 확인

---

## ✅ 구현 체크리스트

### Phase 1: GUI 변경
- [ ] 랭킹 테이블 헤더 변경
- [ ] "전략 분석" 버튼 추가
- [ ] 버튼 클릭 이벤트 구현
- [ ] Signal 연결

### Phase 2: 전략 분석 API
- [ ] 변동성 계산 함수 구현
- [ ] 엔진별 백테스팅 실행 로직
- [ ] 최대 목표 수익률% 계산 함수
- [ ] 가장 적합한 엔진 선택 로직
- [ ] API 엔드포인트 구현

### Phase 3: 팝업창
- [ ] 팝업창 위젯 생성
- [ ] 결과 표시 UI 구현
- [ ] 엔진 배치 버튼 구현
- [ ] Signal 연결

### Phase 4: 전략 업데이트
- [ ] 엔진 전략 업데이트 메서드 구현
- [ ] 백엔드 API 엔드포인트 구현
- [ ] Orchestrator 설정 업데이트 로직

### Phase 5: 테스트
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] 사용자 시나리오 테스트

---

**설계 완료일**: 2025-11-20  
**다음 단계**: 사용자 승인 후 구현 작업 시작


