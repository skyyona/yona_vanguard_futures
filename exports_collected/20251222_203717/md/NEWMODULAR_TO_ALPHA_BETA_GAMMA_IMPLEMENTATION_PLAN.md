# NewModular → Alpha/Beta/Gamma 재구성 구현 방안

## 📋 사용자 요구사항
**"NewModular 엔진을 Alpha로 만들고, Alpha를 복제해서 Beta, Gamma 모두 정확하게 구현"**

---

## 🎯 구현 목표

### 최종 결과물
```
3개 엔진 (모두 동일한 NewModular 기술 기반)
├── Alpha 엔진 (NewModular 이름 변경)
├── Beta 엔진 (Alpha 복제)
└── Gamma 엔진 (Alpha 복제)
```

### 핵심 전략
1. **NewStrategyWrapper → AlphaStrategy로 이름 변경**
2. **AlphaStrategy 복제 → BetaStrategy, GammaStrategy 생성**
3. **3개 엔진 동시 운영** (기존 GUI/API 구조 유지)

---

## 📂 Phase 1: 파일 구조 변경

### 1-1. 파일 이름 변경
```powershell
# new_strategy_wrapper.py → alpha_strategy.py
Rename-Item "backend/core/strategies/new_strategy_wrapper.py" "alpha_strategy.py"
```

### 1-2. 클래스 이름 변경
**파일**: `backend/core/strategies/alpha_strategy.py`

**Before:**
```python
class NewStrategyWrapper(BaseStrategy):
    """
    신규 모듈형 전략을 기존 BaseStrategy 인터페이스로 래핑
    
    기존 GUI/Backend API가 Alpha/Beta/Gamma 대신 새 전략을 사용하도록 함
    """
    
    def __init__(self, symbol: str = "BTCUSDT", leverage: int = 50, order_quantity: float = 0.001):
        # BaseStrategy 초기화 (engine_name="NewModular")
        super().__init__("NewModular")
```

**After:**
```python
class AlphaStrategy(BaseStrategy):
    """
    Alpha 자동매매 전략 - 모듈형 고도화 버전
    
    7개 모듈 기반:
    - DataFetcher: 실데이터
    - IndicatorEngine: 11개 지표
    - SignalEngine: 170점 점수 시스템
    - RiskManager: 손절/익절/트레일링
    - ExecutionAdapter: 재시도 로직
    - StrategyOrchestrator: 백그라운드 실행
    """
    
    def __init__(self, symbol: str = "BTCUSDT", leverage: int = 50, order_quantity: float = 0.001):
        # BaseStrategy 초기화 (engine_name="Alpha")
        super().__init__("Alpha")
```

**변경 사항**:
- 클래스명: `NewStrategyWrapper` → `AlphaStrategy`
- 엔진명: `"NewModular"` → `"Alpha"`
- Docstring: 모듈 설명 추가

---

### 1-3. Alpha 복제 → Beta, Gamma 생성

#### Beta Strategy
**파일**: `backend/core/strategies/beta_strategy.py` (신규 생성)

```python
"""Beta 자동매매 전략 - Alpha와 동일한 모듈형 구조"""
from typing import Dict, Any, Optional
import threading
import time
import asyncio

from backend.core.strategies.base_strategy import BaseStrategy
from backend.core.new_strategy import (
    StrategyOrchestrator,
    OrchestratorConfig,
)


class BetaStrategy(BaseStrategy):
    """
    Beta 자동매매 전략 - Alpha 복제본
    
    7개 모듈 기반 (Alpha와 100% 동일):
    - DataFetcher: 실데이터
    - IndicatorEngine: 11개 지표
    - SignalEngine: 170점 점수 시스템
    - RiskManager: 손절/익절/트레일링
    - ExecutionAdapter: 재시도 로직
    - StrategyOrchestrator: 백그라운드 실행
    """
    
    def __init__(self, symbol: str = "BTCUSDT", leverage: int = 50, order_quantity: float = 0.001):
        # BaseStrategy 초기화 (engine_name="Beta")
        super().__init__("Beta")
        
        # Orchestrator 설정 (Alpha와 동일)
        self.orch_config = OrchestratorConfig(
            symbol=symbol,
            leverage=leverage,
            order_quantity=order_quantity,
            enable_trading=True,
            loop_interval_sec=1.0,
        )
        
        # Orchestrator 초기화
        self.orchestrator = StrategyOrchestrator(
            binance_client=self.binance_client,
            config=self.orch_config,
        )
        
        # 이벤트 콜백 설정
        self.orchestrator.set_event_callback(self._on_orchestrator_event)
        
        # 설정 동기화
        self.current_symbol = symbol
        self.config.update({
            "leverage": leverage,
            "capital_allocation": order_quantity * 50000,
        })
        
        print(f"[{self.engine_name}] BetaStrategy 초기화 완료")
        print(f"  심볼: {symbol}, 레버리지: {leverage}x, 수량: {order_quantity}")
    
    # 나머지 메서드는 AlphaStrategy와 100% 동일
    # (복사-붙여넣기)
```

#### Gamma Strategy
**파일**: `backend/core/strategies/gamma_strategy.py` (신규 생성)

```python
"""Gamma 자동매매 전략 - Alpha와 동일한 모듈형 구조"""
# (BetaStrategy와 거의 동일, engine_name만 "Gamma"로 변경)
```

**차이점**:
- `engine_name`: "Alpha" / "Beta" / "Gamma"
- Docstring: 각 엔진 이름 반영
- 나머지 로직: **100% 동일**

---

## 📝 Phase 2: Import 및 __init__.py 수정

### 2-1. backend/core/strategies/__init__.py

**Before:**
```python
"""자동매매 전략 모듈"""
from backend.core.strategies.base_strategy import BaseStrategy
from backend.core.strategies.new_strategy_wrapper import NewStrategyWrapper

__all__ = [
    'BaseStrategy',
    'NewStrategyWrapper',
]
```

**After:**
```python
"""자동매매 전략 모듈"""
from backend.core.strategies.base_strategy import BaseStrategy
from backend.core.strategies.alpha_strategy import AlphaStrategy
from backend.core.strategies.beta_strategy import BetaStrategy
from backend.core.strategies.gamma_strategy import GammaStrategy

__all__ = [
    'BaseStrategy',
    'AlphaStrategy',
    'BetaStrategy',
    'GammaStrategy',
]
```

---

## 🔧 Phase 3: EngineManager 수정

### 3-1. backend/core/engine_manager.py

**Before:**
```python
from backend.core.strategies import NewStrategyWrapper

class EngineManager:
    def _init_engines(self):
        """NewModular 엔진 초기화"""
        try:
            self.engines["NewModular"] = NewStrategyWrapper()
            
            # 각 엔진의 초기 포지션 상태 설정
            for name, engine in self.engines.items():
                # ...
            
            print("[EngineManager] NewModular 엔진 초기화 완료")
```

**After:**
```python
from backend.core.strategies import AlphaStrategy, BetaStrategy, GammaStrategy

class EngineManager:
    def _init_engines(self):
        """3개 엔진 초기화 (모두 모듈형 구조)"""
        try:
            self.engines["Alpha"] = AlphaStrategy()
            self.engines["Beta"] = BetaStrategy()
            self.engines["Gamma"] = GammaStrategy()
            
            # 각 엔진의 초기 포지션 상태 설정
            for name, engine in self.engines.items():
                self._previous_position_states[name] = engine.in_position
                if hasattr(engine, "set_message_callback"):
                    engine.set_message_callback(lambda category, msg, engine_name=name: self._handle_strategy_message(engine_name, category, msg))
            
            print("[EngineManager] 3개 엔진 초기화 완료 (Alpha, Beta, Gamma - 모두 모듈형)")
        except Exception as e:
            print(f"[EngineManager] 엔진 초기화 오류: {e}")
```

**변경 사항**:
- Import: `NewStrategyWrapper` → `AlphaStrategy, BetaStrategy, GammaStrategy`
- 초기화: 1개 → 3개
- 로그: "NewModular" → "Alpha, Beta, Gamma - 모두 모듈형"

---

## 🌐 Phase 4: API Routes 수정

### 4-1. backend/api/routes.py

**Before (8개 위치):**
```python
# Line 12
engine: str  # "NewModular"

# Line 131
if request.engine not in ["NewModular"]:
    raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'NewModular'.")
```

**After:**
```python
# Line 12
engine: str  # "Alpha", "Beta", "Gamma"

# Line 131
if request.engine not in ["Alpha", "Beta", "Gamma"]:
    raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'Alpha', 'Beta', or 'Gamma'.")
```

**수정 위치 (8개)**:
1. Line 12: `EngineControlRequest` 주석
2. Line 127-132: `/engine/start` 검증 로직
3. Line 147-152: `/engine/stop` 검증 로직
4. Line 167-171: `/engine/status/{engine_name}` 검증 로직
5. Line 190-198: `FundsAllocationRequest`, `EngineLeverageRequest`, `EngineSymbolRequest` 주석
6. Line 207: `/funds/allocation/set` 예시
7. Line 221: `/funds/allocation/remove` 예시
8. Line 235-238: `/engine/symbol` 검증 로직

**변경 내용**:
- `["NewModular"]` → `["Alpha", "Beta", "Gamma"]`
- `"Must be 'NewModular'."` → `"Must be 'Alpha', 'Beta', or 'Gamma'."`

---

## 🎨 Phase 5: GUI (footer_engines_widget.py) 수정

### 5-1. 3개 위젯 생성

**Before:**
```python
# 1. NewModular 엔진
self.newmodular_engine = TradingEngineWidget("NewModular", "#9C27B0", self)
# ...
main_layout.addWidget(self.newmodular_engine)

# 엔진 너비 비율 (1)
main_layout.setStretchFactor(self.newmodular_engine, 1)
```

**After:**
```python
# 1. Alpha 엔진
self.alpha_engine = TradingEngineWidget("Alpha", "#4CAF50", self)
self.alpha_engine.setStyleSheet("""
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 #2E7D32, stop:1 #4CAF50);
        border: 2px solid #81C784;
        border-radius: 12px;
    }
""")
self.alpha_engine.start_signal.connect(self._on_engine_start)
self.alpha_engine.stop_signal.connect(self._on_engine_stop)
main_layout.addWidget(self.alpha_engine)

# 2. Beta 엔진
self.beta_engine = TradingEngineWidget("Beta", "#2196F3", self)
self.beta_engine.setStyleSheet("""
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 #1565C0, stop:1 #2196F3);
        border: 2px solid #64B5F6;
        border-radius: 12px;
    }
""")
self.beta_engine.start_signal.connect(self._on_engine_start)
self.beta_engine.stop_signal.connect(self._on_engine_stop)
main_layout.addWidget(self.beta_engine)

# 3. Gamma 엔진
self.gamma_engine = TradingEngineWidget("Gamma", "#FF9800", self)
self.gamma_engine.setStyleSheet("""
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 #E65100, stop:1 #FF9800);
        border: 2px solid #FFB74D;
        border-radius: 12px;
    }
""")
self.gamma_engine.start_signal.connect(self._on_engine_start)
self.gamma_engine.stop_signal.connect(self._on_engine_stop)
main_layout.addWidget(self.gamma_engine)

# 각 엔진의 너비 비율 동일 (1:1:1)
main_layout.setStretchFactor(self.alpha_engine, 1)
main_layout.setStretchFactor(self.beta_engine, 1)
main_layout.setStretchFactor(self.gamma_engine, 1)
```

**변경 사항**:
- 1개 위젯 → 3개 위젯
- NewModular (보라색) → Alpha (초록), Beta (파랑), Gamma (주황)
- Gradient 스타일 적용 (시각적 차별화)

---

### 5-2. 메시지 라우팅 수정

**Before:**
```python
if engine_name == "NewModular":
    self.newmodular_engine.update_energy_analysis(data)
```

**After:**
```python
if engine_name == "Alpha":
    self.alpha_engine.update_energy_analysis(data)
elif engine_name == "Beta":
    self.beta_engine.update_energy_analysis(data)
elif engine_name == "Gamma":
    self.gamma_engine.update_energy_analysis(data)
```

**수정 필요 메시지 타입 (9개)**:
1. `ENGINE_ENERGY_ANALYSIS`: 1개 → 3개 분기
2. `ENGINE_TRADE_MESSAGE`: 1개 → 3개 분기
3. `ENGINE_RISK_MESSAGE`: 1개 → 3개 분기
4. `ENGINE_TRADE_COMPLETED`: 1개 → 3개 분기
5. `ENGINE_STATS_UPDATE`: 1개 → 3개 분기
6. `ENGINE_STATUS_UPDATE`: 1개 → 3개 분기
7. `ENGINE_STATUS_MESSAGE`: 1개 → 3개 분기
8. `ENGINE_FUNDS_RETURNED`: 1개 → 3개 분기
9. `ENERGY_ANALYSIS_UPDATE`: NewModular → Alpha

**추가 수정**:
- `get_engine_status()`: 1개 → 3개 엔진
- `start_all_engines()`: 1개 → 3개 엔진
- `stop_all_engines()`: 1개 → 3개 엔진

---

## 📊 Phase 6: Database (선택 사항)

### 6-1. engine_settings 테이블

**현재 구조** (동적 저장):
```sql
CREATE TABLE IF NOT EXISTS engine_settings (
    engine_name TEXT PRIMARY KEY,  -- "NewModular"
    designated_funds REAL NOT NULL DEFAULT 0.0,
    applied_leverage INTEGER NOT NULL DEFAULT 1,
    funds_percent REAL NOT NULL DEFAULT 0.0,
    updated_at_utc TEXT NOT NULL,
    created_at_utc TEXT NOT NULL
)
```

**변경 후**:
- `engine_name`: "NewModular" → "Alpha", "Beta", "Gamma"
- 코드 수정 불필요 (동적 저장 방식)

**선택적 마이그레이션**:
```sql
-- NewModular → Alpha 데이터 마이그레이션 (선택)
UPDATE engine_settings SET engine_name = 'Alpha' WHERE engine_name = 'NewModular';

-- Beta, Gamma 초기 설정 (선택)
INSERT INTO engine_settings (engine_name, designated_funds, applied_leverage, funds_percent, updated_at_utc, created_at_utc)
VALUES 
    ('Beta', 0.0, 1, 0.0, datetime('now'), datetime('now')),
    ('Gamma', 0.0, 1, 0.0, datetime('now'), datetime('now'));
```

---

## 🧪 Phase 7: 테스트 파일 수정 (선택)

### 7-1. test_gui_integration.py

**Before:**
```python
assert hasattr(widget, 'newmodular_engine'), "NewModular 엔진 없음"
print(f"   - NewModular: {widget.newmodular_engine.engine_name}")
```

**After:**
```python
assert hasattr(widget, 'alpha_engine'), "Alpha 엔진 없음"
assert hasattr(widget, 'beta_engine'), "Beta 엔진 없음"
assert hasattr(widget, 'gamma_engine'), "Gamma 엔진 없음"
print(f"   - Alpha: {widget.alpha_engine.engine_name}")
print(f"   - Beta: {widget.beta_engine.engine_name}")
print(f"   - Gamma: {widget.gamma_engine.engine_name}")
```

---

## 📋 구현 순서 (Phase별 의존성)

```
Phase 1: 파일 구조 변경 (필수)
├── 1-1. new_strategy_wrapper.py → alpha_strategy.py 이름 변경
├── 1-2. AlphaStrategy 클래스 이름 변경
└── 1-3. beta_strategy.py, gamma_strategy.py 생성 (Alpha 복제)

Phase 2: Import 수정 (Phase 1 후)
└── 2-1. __init__.py 수정

Phase 3: EngineManager 수정 (Phase 2 후)
└── 3-1. engine_manager.py 수정 (Import + _init_engines)

Phase 4: API Routes 수정 (독립적)
└── 4-1. routes.py 8개 위치 수정

Phase 5: GUI 수정 (Phase 4와 병렬 가능)
├── 5-1. 3개 위젯 생성
└── 5-2. 메시지 라우팅 수정 (60+ 라인)

Phase 6: Database 마이그레이션 (선택)
└── 6-1. engine_settings 데이터 마이그레이션

Phase 7: 테스트 파일 수정 (선택)
└── 7-1. test_gui_integration.py 수정
```

**Critical Path**: Phase 1 → Phase 2 → Phase 3 → Phase 5

---

## 📊 수정 파일 요약

### 핵심 파일 (필수)
| 순번 | 파일 경로 | 작업 | 라인 수 | 난이도 |
|------|----------|------|---------|--------|
| 1 | `backend/core/strategies/alpha_strategy.py` | 이름 변경 (new_strategy_wrapper.py) | 전체 | 쉬움 |
| 2 | `backend/core/strategies/beta_strategy.py` | 신규 생성 (Alpha 복제) | 200+ | 쉬움 |
| 3 | `backend/core/strategies/gamma_strategy.py` | 신규 생성 (Alpha 복제) | 200+ | 쉬움 |
| 4 | `backend/core/strategies/__init__.py` | Import 수정 | 5줄 | 쉬움 |
| 5 | `backend/core/engine_manager.py` | Import + _init_engines 수정 | 10줄 | 쉬움 |
| 6 | `backend/api/routes.py` | 검증 로직 수정 (8개 위치) | 20줄 | 중간 |
| 7 | `gui/widgets/footer_engines_widget.py` | 위젯 생성 + 메시지 라우팅 | 80+ 줄 | 어려움 |

### 선택 파일
| 순번 | 파일 경로 | 작업 | 필요성 |
|------|----------|------|--------|
| 8 | `backend/database/migrations/*.py` | DB 마이그레이션 | 선택 |
| 9 | `test_gui_integration.py` | 테스트 수정 | 선택 |

---

## 🎯 최종 결과물

### 엔진 구조
```
YONA Vanguard Futures
├── Alpha 엔진 (모듈형)
│   ├── DataFetcher (실데이터)
│   ├── IndicatorEngine (11개 지표)
│   ├── SignalEngine (170점 점수)
│   ├── RiskManager (손절/익절/트레일링)
│   ├── ExecutionAdapter (재시도 3회)
│   ├── StrategyOrchestrator (백그라운드)
│   └── AlphaStrategy (BaseStrategy 래퍼)
│
├── Beta 엔진 (Alpha 복제 - 100% 동일)
│   └── (모든 모듈 Alpha와 공유)
│
└── Gamma 엔진 (Alpha 복제 - 100% 동일)
    └── (모든 모듈 Alpha와 공유)
```

### GUI 구조
```
Footer Engines Widget
├─ [Alpha 엔진]  (초록색 #4CAF50)
│   ├─ START/STOP 버튼
│   ├─ 에너지 분석 (Rising Energy)
│   ├─ 거래 메시지 (Trade Messages)
│   ├─ 리스크 메시지 (Risk Messages)
│   └─ 거래 기록 (Trade History)
│
├─ [Beta 엔진]   (파랑색 #2196F3)
│   └─ (Alpha와 동일)
│
└─ [Gamma 엔진]  (주황색 #FF9800)
    └─ (Alpha와 동일)
```

### API 엔드포인트
```
POST /api/v1/engine/start      {"engine": "Alpha"|"Beta"|"Gamma"}
POST /api/v1/engine/stop       {"engine": "Alpha"|"Beta"|"Gamma"}
GET  /api/v1/engine/status/{engine_name}
POST /api/v1/funds/allocation/set
POST /api/v1/engine/symbol
```

---

## ✅ 구현 전 체크리스트

### Phase 1 (파일 구조)
- [ ] `new_strategy_wrapper.py` → `alpha_strategy.py` 이름 변경
- [ ] `AlphaStrategy` 클래스명 변경 (engine_name="Alpha")
- [ ] `beta_strategy.py` 생성 (Alpha 복제)
- [ ] `gamma_strategy.py` 생성 (Alpha 복제)

### Phase 2 (Import)
- [ ] `__init__.py` Import 수정 (3개 전략)

### Phase 3 (EngineManager)
- [ ] `engine_manager.py` Import 수정
- [ ] `_init_engines()` 3개 엔진 초기화

### Phase 4 (API)
- [ ] `routes.py` 8개 위치 검증 로직 수정

### Phase 5 (GUI)
- [ ] `footer_engines_widget.py` 3개 위젯 생성
- [ ] 메시지 라우팅 9개 타입 수정 (60+ 라인)
- [ ] `get_engine_status()` 수정
- [ ] `start_all_engines()` 수정
- [ ] `stop_all_engines()` 수정

### Phase 6 (Database - 선택)
- [ ] `engine_settings` 데이터 마이그레이션

### Phase 7 (테스트 - 선택)
- [ ] `test_gui_integration.py` 수정

---

## 🚀 구현 후 테스트

### 1. 시스템 시작 테스트
```powershell
python system_manager.bat
```

**예상 결과**:
- ✅ `[EngineManager] 3개 엔진 초기화 완료 (Alpha, Beta, Gamma - 모두 모듈형)` 로그
- ✅ GUI Footer에 3개 위젯 표시 (초록/파랑/주황)

### 2. GUI 시각적 테스트
- ✅ Alpha 엔진 (초록색) 표시
- ✅ Beta 엔진 (파랑색) 표시
- ✅ Gamma 엔진 (주황색) 표시
- ✅ 각 엔진 START 버튼 클릭 시 정상 작동

### 3. API 테스트
```bash
# Alpha 엔진 시작
curl -X POST http://localhost:8000/engine/start -d '{"engine": "Alpha"}'

# Beta 엔진 시작
curl -X POST http://localhost:8000/engine/start -d '{"engine": "Beta"}'

# Gamma 엔진 시작
curl -X POST http://localhost:8000/engine/start -d '{"engine": "Gamma"}'
```

**예상 결과**:
- ✅ 모든 요청 200 OK
- ✅ 각 엔진 독립적으로 작동

### 4. 동시 실행 테스트
- ✅ 3개 엔진 동시 시작
- ✅ 각 엔진이 독립적으로 거래 실행
- ✅ GUI에서 3개 위젯 실시간 업데이트

---

## 📝 구현 우선순위

### 🔴 Critical (Phase 1-3)
1. **파일 구조 변경** (new_strategy_wrapper.py → alpha_strategy.py)
2. **Alpha 복제** (beta_strategy.py, gamma_strategy.py)
3. **EngineManager 수정** (3개 엔진 초기화)

### 🟡 High (Phase 4-5)
4. **API Routes 수정** (8개 위치)
5. **GUI 위젯 수정** (3개 위젯 + 메시지 라우팅)

### 🟢 Low (Phase 6-7)
6. **Database 마이그레이션** (선택)
7. **테스트 파일 수정** (선택)

---

## 🎁 추가 혜택

### 기존 NewModular 대비 장점
1. **사용자 익숙한 이름**: Alpha/Beta/Gamma (기존 UI 유지)
2. **3개 엔진 동시 운영**: 다양한 심볼/레버리지 조합 테스트 가능
3. **모듈형 기술 기반**: 모든 엔진이 고도화된 7개 모듈 사용
4. **기존 코드 재사용**: GUI/API 구조 변경 최소화

### 기존 Legacy Alpha/Beta/Gamma 대비 장점
1. **실데이터 사용**: 모든 엔진이 Binance API 연결
2. **고도화된 리스크 관리**: 트레일링, 본절 이동, 동적 익절
3. **재시도 로직**: 진입/청산 실패 시 최대 3회 재시도
4. **백그라운드 실행**: GUI 프리징 방지
5. **모듈 독립성**: 유지보수성 향상

---

## 🔒 리스크 및 주의사항

### 주의할 점
1. **3개 엔진 동시 실행 시 리소스 사용량 증가**
   - CPU: 3배 증가
   - 메모리: 3배 증가
   - API 호출: 3배 증가

2. **Binance API Rate Limit**
   - 3개 엔진 동시 실행 시 API 호출 횟수 증가
   - Weight Limit 초과 가능성 (1200 weight/min)

3. **데이터베이스 동시성**
   - 3개 엔진이 동시에 DB 쓰기 시 경합 발생 가능

### 완화 방안
1. **Loop Interval 조정**: 1초 → 2초 (API 호출 감소)
2. **선택적 실행**: 필요한 엔진만 시작
3. **Weight 모니터링**: API Weight 초과 시 자동 대기

---

## 📖 결론

### 사용자 의도 100% 반영
- ✅ **NewModular → Alpha로 이름 변경**
- ✅ **Alpha 복제 → Beta, Gamma 생성**
- ✅ **3개 엔진 모두 모듈형 기술 기반**

### 구현 난이도
- **쉬움**: Phase 1-3 (파일 구조, Import, EngineManager)
- **중간**: Phase 4 (API Routes)
- **어려움**: Phase 5 (GUI 60+ 라인)

### 예상 소요 시간
- Phase 1-3: 30분
- Phase 4: 20분
- Phase 5: 40분
- **총 90분** (테스트 포함 2시간)

### 최종 권고
**구현 가능하며, 사용자 의도에 완벽히 부합합니다.**

이제 3개 엔진(Alpha, Beta, Gamma)이 모두 **동일한 고도화된 모듈형 기술**을 사용하며, **기존 GUI/API 구조를 유지**할 수 있습니다.

**사용자 승인 후 구현을 시작하겠습니다!** 🚀
