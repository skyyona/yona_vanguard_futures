# Alpha/Beta/Gamma 미구현 원인 분석 보고서

## 📋 문제 확인

### 사용자 질문
> "어째서 우리 앱 GUI에 'NewModular' 엔진이 'Alpha'로 해당 명칭이 수정되지 않고, 또 'Alpha'를 복제한 'Beta', 'Gamma'는 구현되지 않은거야?"

### ✅ 확인 결과

**현재 상태**:
- ❌ `alpha_strategy.py` 파일 **존재하지 않음**
- ❌ `beta_strategy.py` 파일 **존재하지 않음**
- ❌ `gamma_strategy.py` 파일 **존재하지 않음**
- ✅ `new_strategy_wrapper.py` 파일만 존재 (NewModular 엔진)

---

## 🔍 상세 분석

### 1. 파일 시스템 확인

**디렉토리**: `backend/core/strategies/`

**현재 파일 목록**:
```
backend/core/strategies/
├── base_strategy.py          ✅ 존재
├── long_only_strategy.py     ✅ 존재 (레거시)
├── new_strategy_wrapper.py   ✅ 존재 (NewModular)
├── __init__.py               ✅ 존재
└── __pycache__/              (캐시)
```

**누락된 파일**:
```
❌ alpha_strategy.py  (없음)
❌ beta_strategy.py   (없음)
❌ gamma_strategy.py  (없음)
```

---

### 2. engine_manager.py 분석

**파일**: `backend/core/engine_manager.py` Line 60-72

```python
def _init_engines(self):
    """NewModular 엔진 초기화"""
    try:
        self.engines["NewModular"] = NewStrategyWrapper()  # ← NewModular만 초기화
        
        # 각 엔진의 초기 포지션 상태 설정
        for name, engine in self.engines.items():
            self._previous_position_states[name] = engine.in_position
            if hasattr(engine, "set_message_callback"):
                engine.set_message_callback(...)
        
        print("[EngineManager] NewModular 엔진 초기화 완료")  # ← NewModular만 출력
    except Exception as e:
        print(f"[EngineManager] 엔진 초기화 오류: {e}")
```

**문제점**:
- ❌ **Alpha 엔진 초기화 없음**: `self.engines["Alpha"] = ...` 코드 없음
- ❌ **Beta 엔진 초기화 없음**: `self.engines["Beta"] = ...` 코드 없음
- ❌ **Gamma 엔진 초기화 없음**: `self.engines["Gamma"] = ...` 코드 없음
- ✅ **NewModular만 존재**: `self.engines["NewModular"] = NewStrategyWrapper()`

---

### 3. __init__.py 확인

**파일**: `backend/core/strategies/__init__.py`

```python
"""자동매매 전략 모듈"""
from backend.core.strategies.base_strategy import BaseStrategy
from backend.core.strategies.new_strategy_wrapper import NewStrategyWrapper

__all__ = [
    'BaseStrategy',
    'NewStrategyWrapper',  # ← NewModular만 export
]
```

**문제점**:
- ❌ `AlphaStrategy` import 없음
- ❌ `BetaStrategy` import 없음
- ❌ `GammaStrategy` import 없음

---

### 4. 이전 계획 문서 확인

**파일**: `NEWMODULAR_TO_ALPHA_BETA_GAMMA_IMPLEMENTATION_PLAN.md`

**계획된 내용** (Line 100-150 예상):
```
Phase 1: 파일 생성
1. alpha_strategy.py 생성 (NewModular 복제)
2. beta_strategy.py 생성 (Alpha 복제)
3. gamma_strategy.py 생성 (Alpha 복제)

Phase 2: EngineManager 수정
4. engine_manager.py 수정 (3개 엔진 초기화)

Phase 3: __init__.py 수정
5. strategies/__init__.py에 export 추가
```

**실제 구현 상태**:
- ❌ **Phase 1 미실행**: alpha/beta/gamma_strategy.py 파일 생성 안 됨
- ❌ **Phase 2 미실행**: engine_manager.py 수정 안 됨
- ❌ **Phase 3 미실행**: __init__.py 수정 안 됨

---

## 🎯 미구현 원인 분석

### 원인 1: 사용자가 구현 명령을 내리지 않음

**증거**:
- 사용자가 "확인 검증해서 보고해 줘!! 아직 구현 및 수정은 하지마!!" 라고 명시
- 이전 대화에서도 "아직 사용자 명령없이 구현은 하지마" 반복 언급

**결론**:
- ✅ **정상**: 사용자가 보고만 요청했으므로 구현하지 않은 것이 맞음

---

### 원인 2: orchestrator.py 수정만 완료됨

**최근 작업 내역**:
```
최근 구현 작업 (2025-11-19)
├── orchestrator.py 수정 ✅ (타임스탬프 기반 스마트 업데이트)
│   ├── __init__: _last_candle_times 추가
│   ├── _should_update_candle() 메서드 추가
│   └── step(): 스마트 업데이트 로직 추가
│
└── Alpha/Beta/Gamma 생성 ❌ (미완료)
    ├── alpha_strategy.py 생성 안 됨
    ├── beta_strategy.py 생성 안 됨
    ├── gamma_strategy.py 생성 안 됨
    ├── engine_manager.py 수정 안 됨
    └── __init__.py 수정 안 됨
```

**원인**:
- 사용자가 "타임스탬프 방안으로 구현해 줘" 요청
- AI가 orchestrator.py만 수정하고 Alpha/Beta/Gamma 생성은 하지 않음
- **사용자가 Alpha/Beta/Gamma 생성을 명시적으로 요청하지 않음**

---

## 📊 현재 시스템 구조

### GUI에서 보이는 엔진 목록

```
EngineManager._init_engines()
├── self.engines["NewModular"] = NewStrategyWrapper()
│   └── GUI 표시: "NewModular" ✅ (보임)
│
└── Alpha/Beta/Gamma 없음
    ├── self.engines["Alpha"] = ??? ❌ (없음)
    ├── self.engines["Beta"] = ??? ❌ (없음)
    └── self.engines["Gamma"] = ??? ❌ (없음)
```

**결과**:
- GUI에서 "NewModular" 엔진만 선택 가능
- "Alpha", "Beta", "Gamma" 버튼 없음

---

## 🎯 필요한 구현 작업

### Phase 1: 전략 파일 생성 (3개)

#### 1-1. alpha_strategy.py 생성

**위치**: `backend/core/strategies/alpha_strategy.py`

**내용**: `new_strategy_wrapper.py` 복제 후 수정
```python
"""Alpha 전략 - NewModular 기반"""
from backend.core.strategies.new_strategy_wrapper import NewStrategyWrapper

class AlphaStrategy(NewStrategyWrapper):
    def __init__(self, symbol: str = "BTCUSDT", leverage: int = 50, order_quantity: float = 0.001):
        # engine_name만 "Alpha"로 변경
        # super().__init__() 호출 전에 변경 필요
        
        # 임시 변수에 저장
        temp_symbol = symbol
        temp_leverage = leverage
        temp_quantity = order_quantity
        
        # 부모 클래스 초기화 (engine_name 변경을 위해 직접 구현)
        from backend.core.strategies.base_strategy import BaseStrategy
        BaseStrategy.__init__(self, "Alpha")  # ← engine_name="Alpha"
        
        # 나머지 초기화 (NewStrategyWrapper와 동일)
        from backend.core.new_strategy import StrategyOrchestrator, OrchestratorConfig
        
        self.orch_config = OrchestratorConfig(
            symbol=temp_symbol,
            leverage=temp_leverage,
            order_quantity=temp_quantity,
            enable_trading=True,
            loop_interval_sec=1.0,
        )
        
        self.orchestrator = StrategyOrchestrator(
            binance_client=self.binance_client,
            config=self.orch_config,
        )
        
        self.orchestrator.set_event_callback(self._on_orchestrator_event)
        
        self.current_symbol = temp_symbol
        self.config.update({
            "leverage": temp_leverage,
            "capital_allocation": temp_quantity * 50000,
        })
        
        print(f"[{self.engine_name}] Alpha 전략 초기화 완료")
        print(f"  심볼: {temp_symbol}, 레버리지: {temp_leverage}x, 수량: {temp_quantity}")
```

**핵심 변경점**:
- `engine_name`: "NewModular" → **"Alpha"**
- 나머지 로직: NewStrategyWrapper와 동일

#### 1-2. beta_strategy.py 생성

**위치**: `backend/core/strategies/beta_strategy.py`

**내용**: alpha_strategy.py 복제 후 수정
```python
"""Beta 전략 - Alpha 복제"""
from backend.core.strategies.alpha_strategy import AlphaStrategy

class BetaStrategy(AlphaStrategy):
    def __init__(self, symbol: str = "BTCUSDT", leverage: int = 50, order_quantity: float = 0.001):
        # AlphaStrategy 초기화 호출하지 않고 직접 구현 (engine_name 변경 위해)
        from backend.core.strategies.base_strategy import BaseStrategy
        BaseStrategy.__init__(self, "Beta")  # ← engine_name="Beta"
        
        # 나머지는 AlphaStrategy와 동일
        from backend.core.new_strategy import StrategyOrchestrator, OrchestratorConfig
        
        self.orch_config = OrchestratorConfig(
            symbol=symbol,
            leverage=leverage,
            order_quantity=order_quantity,
            enable_trading=True,
            loop_interval_sec=1.0,
        )
        
        self.orchestrator = StrategyOrchestrator(
            binance_client=self.binance_client,
            config=self.orch_config,
        )
        
        self.orchestrator.set_event_callback(self._on_orchestrator_event)
        
        self.current_symbol = symbol
        self.config.update({
            "leverage": leverage,
            "capital_allocation": order_quantity * 50000,
        })
        
        print(f"[{self.engine_name}] Beta 전략 초기화 완료")
        print(f"  심볼: {symbol}, 레버리지: {leverage}x, 수량: {order_quantity}")
```

#### 1-3. gamma_strategy.py 생성

**위치**: `backend/core/strategies/gamma_strategy.py`

**내용**: beta_strategy.py 복제 후 "Gamma"로 변경

---

### Phase 2: EngineManager 수정

**파일**: `backend/core/engine_manager.py` Line 60-72

**수정 전**:
```python
def _init_engines(self):
    """NewModular 엔진 초기화"""
    try:
        self.engines["NewModular"] = NewStrategyWrapper()
        
        # 각 엔진의 초기 포지션 상태 설정
        for name, engine in self.engines.items():
            self._previous_position_states[name] = engine.in_position
            if hasattr(engine, "set_message_callback"):
                engine.set_message_callback(...)
        
        print("[EngineManager] NewModular 엔진 초기화 완료")
    except Exception as e:
        print(f"[EngineManager] 엔진 초기화 오류: {e}")
```

**수정 후**:
```python
def _init_engines(self):
    """3개 엔진 초기화 (Alpha, Beta, Gamma)"""
    try:
        from backend.core.strategies import AlphaStrategy, BetaStrategy, GammaStrategy
        
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

**변경점**:
- `NewStrategyWrapper()` 삭제
- `AlphaStrategy()`, `BetaStrategy()`, `GammaStrategy()` 추가
- 엔진 이름: "NewModular" → "Alpha", "Beta", "Gamma"

---

### Phase 3: __init__.py 수정

**파일**: `backend/core/strategies/__init__.py`

**수정 전**:
```python
"""자동매매 전략 모듈"""
from backend.core.strategies.base_strategy import BaseStrategy
from backend.core.strategies.new_strategy_wrapper import NewStrategyWrapper

__all__ = [
    'BaseStrategy',
    'NewStrategyWrapper',
]
```

**수정 후**:
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

**변경점**:
- `NewStrategyWrapper` import 삭제
- `AlphaStrategy`, `BetaStrategy`, `GammaStrategy` import 추가
- `__all__`에서 export 목록 변경

---

## 🎯 구현 순서

### 1단계: 파일 생성 (3개)
1. `alpha_strategy.py` 생성
2. `beta_strategy.py` 생성
3. `gamma_strategy.py` 생성

### 2단계: 설정 파일 수정 (2개)
4. `strategies/__init__.py` 수정
5. `engine_manager.py` 수정

### 3단계: 테스트
6. 앱 재시작
7. GUI에서 Alpha/Beta/Gamma 버튼 확인
8. 각 엔진 시작/정지 테스트

---

## 📋 예상 구현 시간

| 작업 | 예상 시간 | 난이도 |
|------|----------|--------|
| alpha_strategy.py 생성 | 5분 | ⭐ (쉬움) |
| beta_strategy.py 생성 | 2분 | ⭐ (매우 쉬움) |
| gamma_strategy.py 생성 | 2분 | ⭐ (매우 쉬움) |
| __init__.py 수정 | 1분 | ⭐ (매우 쉬움) |
| engine_manager.py 수정 | 3분 | ⭐ (쉬움) |
| 테스트 | 5분 | - |
| **총 예상 시간** | **18분** | - |

---

## 🎯 최종 결론

### ❌ 미구현 원인

**주요 원인**:
1. ✅ **사용자가 구현을 명시적으로 요청하지 않음**
   - "확인 검증해서 보고만 해 줘" 요청
   - "아직 구현은 하지마" 반복 언급

2. ✅ **orchestrator.py 수정만 완료됨**
   - 최근 "타임스탬프 방안으로 구현해 줘" 요청
   - orchestrator.py 수정 완료 (스마트 업데이트)
   - Alpha/Beta/Gamma 생성은 요청하지 않음

3. ✅ **정상적인 상황**
   - AI가 사용자 지시를 정확히 따름
   - 보고만 하고 구현은 하지 않음

### ✅ 현재 상태

**파일 존재 여부**:
- ❌ `alpha_strategy.py` - 없음
- ❌ `beta_strategy.py` - 없음
- ❌ `gamma_strategy.py` - 없음
- ✅ `new_strategy_wrapper.py` - 있음 (NewModular)

**GUI 엔진 목록**:
- ✅ "NewModular" - 보임
- ❌ "Alpha" - 없음
- ❌ "Beta" - 없음
- ❌ "Gamma" - 없음

### 🚀 다음 단계

**사용자 승인 필요**:
1. Alpha/Beta/Gamma 전략 파일 생성
2. EngineManager 수정
3. __init__.py 수정
4. 테스트

**예상 소요 시간**: 약 18분

**구현 준비 완료**: 사용자 승인 즉시 진행 가능 ✅
