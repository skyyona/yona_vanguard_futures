# Alpha/Beta/Gamma 안전 삭제 계획서

**작성일**: 2025-11-19  
**목적**: Alpha/Beta/Gamma 전략을 앱 정상 작동에 문제없이 안전하게 삭제  
**중요**: ⚠️ **사용자 명령 없이 삭제 금지** - 본 문서는 계획서일 뿐입니다

---

## 🎯 삭제 목표

**NewModular 엔진으로 완전 교체**
- Alpha/Beta/Gamma 3개 레거시 엔진 제거
- NewModular 단일 엔진으로 통합
- 기존 GUI/Backend 구조 유지

---

## 📊 현재 의존성 매핑

### 1. Backend 계층

#### 1.1 EngineManager (CRITICAL)
**파일**: `backend/core/engine_manager.py`

**의존성**:
```python
# Line 10: Import
from backend.core.strategies import AlphaStrategy, BetaStrategy, GammaStrategy

# Line 57-59: 초기화
self.engines["Alpha"] = AlphaStrategy()
self.engines["Beta"] = BetaStrategy()
self.engines["Gamma"] = GammaStrategy()
```

**영향도**: ⚠️ **CRITICAL** - 앱 전체 엔진 관리의 핵심
- 모든 엔진 시작/정지 제어
- GUI WebSocket 업데이트
- 거래 기록 DB 저장

---

#### 1.2 API Routes (HIGH)
**파일**: `backend/api/routes.py`

**의존성**:
```python
# Line 12, 190, 194: 스키마
engine: str  # "Alpha", "Beta", "Gamma"

# Line 131, 151, 171: 검증 로직
if request.engine not in ["Alpha", "Beta", "Gamma"]:
    raise HTTPException(...)
```

**영향도**: ⚠️ **HIGH** - API 호출 시 오류 발생
- `/api/v1/engine/start`
- `/api/v1/engine/stop`
- `/api/v1/engine/status/{engine_name}`
- `/api/v1/engine/settings`
- `/api/v1/engine/leverage`

---

#### 1.3 전략 패키지 (MEDIUM)
**파일**: `backend/core/strategies/__init__.py`

**의존성**:
```python
# Export
from .alpha_strategy import AlphaStrategy
from .beta_strategy import BetaStrategy
from .gamma_strategy import GammaStrategy

__all__ = ["AlphaStrategy", "BetaStrategy", "GammaStrategy", ...]
```

**영향도**: ⚠️ **MEDIUM** - Import 오류

---

### 2. GUI 계층

#### 2.1 FooterEnginesWidget (CRITICAL)
**파일**: `gui/widgets/footer_engines_widget.py`

**의존성**:
```python
# Line 938-948: Alpha 위젯
self.alpha_engine = TradingEngineWidget("Alpha", "#4CAF50", self)
self.alpha_engine.start_signal.connect(self._on_engine_start)
main_layout.addWidget(self.alpha_engine)

# Line 951-961: Beta 위젯
self.beta_engine = TradingEngineWidget("Beta", "#2196F3", self)
# ...

# Line 964-974: Gamma 위젯
self.gamma_engine = TradingEngineWidget("Gamma", "#FF9800", self)
# ...

# Line 1012-1029: WebSocket 메시지 처리
if engine_name == "Alpha":
    self.alpha_engine.update_energy_analysis(data)
elif engine_name == "Beta":
    self.beta_engine.update_energy_analysis(data)
elif engine_name == "Gamma":
    self.gamma_engine.update_energy_analysis(data)
```

**영향도**: ⚠️ **CRITICAL** - GUI Footer 표시 불가
- 3개 엔진 위젯 (TradingEngineWidget)
- 에너지 분석 차트
- 거래 기록 표시
- 시작/정지 버튼

---

### 3. Database 계층

#### 3.1 engine_settings 테이블
**스키마**:
```sql
CREATE TABLE engine_settings (
    id INTEGER PRIMARY KEY,
    engine_name TEXT UNIQUE,  -- "Alpha", "Beta", "Gamma"
    leverage INTEGER DEFAULT 1,
    designated_funds REAL DEFAULT 0.0,
    is_active INTEGER DEFAULT 0,
    updated_at TEXT
);
```

**영향도**: ⚠️ **LOW** - 데이터 보존 가능
- Alpha/Beta/Gamma 설정 레코드 삭제
- NewModular 설정 레코드 추가

---

## 🛠️ 안전 삭제 절차 (6단계)

### **Phase 1: NewModular 엔진 검증** ✅

**목적**: NewModular가 Alpha/Beta/Gamma를 대체 가능한지 확인

**작업**:
- [x] 7개 모듈 구현 완료 (DataFetcher, IndicatorEngine, SignalEngine, RiskManager, ExecutionAdapter, Orchestrator, Wrapper)
- [x] 실데이터 사용 확인 (Binance API)
- [x] 주문 실행 확인 (create_market_order, close_position_market)
- [x] GUI/Backend 통합 확인 (NewStrategyWrapper)

**결과**: ✅ **완료** (NEWMODULAR_VERIFICATION_REPORT.md 참고)

---

### **Phase 2: EngineManager 리팩토링**

**목적**: 3개 엔진 → 1개 엔진으로 변경

**파일**: `backend/core/engine_manager.py`

**변경 사항**:

#### 2.1 Import 수정
```python
# 변경 전
from backend.core.strategies import AlphaStrategy, BetaStrategy, GammaStrategy

# 변경 후
from backend.core.strategies import NewStrategyWrapper
```

#### 2.2 엔진 초기화 수정
```python
# 변경 전 (Line 57-59)
self.engines["Alpha"] = AlphaStrategy()
self.engines["Beta"] = BetaStrategy()
self.engines["Gamma"] = GammaStrategy()

# 변경 후
self.engines["NewModular"] = NewStrategyWrapper(
    symbol="BTCUSDT",
    leverage=50,
    order_quantity=0.001
)

# 또는 설정 가능하게
# self.engines["Strategy1"] = NewStrategyWrapper(symbol="BTCUSDT", leverage=10, order_quantity=0.001)
# self.engines["Strategy2"] = NewStrategyWrapper(symbol="ETHUSDT", leverage=20, order_quantity=0.002)
# self.engines["Strategy3"] = NewStrategyWrapper(symbol="SOLUSDT", leverage=15, order_quantity=0.01)
```

#### 2.3 엔진 이름 검증 로직 수정
```python
# 모든 하드코딩된 ["Alpha", "Beta", "Gamma"] 검증 제거
# 대신 self.engines.keys() 사용
```

**영향도**: ⚠️ **CRITICAL**
- 모든 엔진 제어 경로 영향
- WebSocket 메시지 타입 변경

---

### **Phase 3: API Routes 리팩토링**

**목적**: 엔진 이름 검증 로직 변경

**파일**: `backend/api/routes.py`

**변경 사항**:

#### 3.1 스키마 수정
```python
# 변경 전 (Line 12)
class EngineControlRequest(BaseModel):
    engine: str  # "Alpha", "Beta", "Gamma"

# 변경 후
class EngineControlRequest(BaseModel):
    engine: str  # "NewModular" 또는 동적 엔진 이름
```

#### 3.2 검증 로직 제거
```python
# 변경 전 (Line 131, 151, 171)
if request.engine not in ["Alpha", "Beta", "Gamma"]:
    raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'Alpha', 'Beta', or 'Gamma'.")

# 변경 후
# 하드코딩 검증 제거 - EngineManager에서 처리
# 또는 동적 검증
valid_engines = list(engine_manager.engines.keys())
if request.engine not in valid_engines:
    raise HTTPException(status_code=400, detail=f"Invalid engine name. Must be one of {valid_engines}.")
```

**영향도**: ⚠️ **HIGH**
- 모든 API 엔드포인트 수정
- 클라이언트(GUI) 호출 코드 영향 없음 (엔진 이름만 변경)

---

### **Phase 4: GUI 리팩토링**

**목적**: 3개 위젯 → 1개(또는 동적) 위젯으로 변경

**파일**: `gui/widgets/footer_engines_widget.py`

**변경 사항**:

#### 4.1 위젯 초기화 수정
```python
# 변경 전 (Line 938-974)
self.alpha_engine = TradingEngineWidget("Alpha", "#4CAF50", self)
self.beta_engine = TradingEngineWidget("Beta", "#2196F3", self)
self.gamma_engine = TradingEngineWidget("Gamma", "#FF9800", self)

# 변경 후 (옵션 A: 단일 위젯)
self.new_modular_engine = TradingEngineWidget("NewModular", "#4CAF50", self)
self.new_modular_engine.start_signal.connect(self._on_engine_start)
self.new_modular_engine.stop_signal.connect(self._on_engine_stop)
main_layout.addWidget(self.new_modular_engine)

# 또는 (옵션 B: 동적 위젯 - 권장)
self.engine_widgets = {}
engine_configs = [
    {"name": "Strategy1", "symbol": "BTCUSDT", "color": "#4CAF50"},
    {"name": "Strategy2", "symbol": "ETHUSDT", "color": "#2196F3"},
    {"name": "Strategy3", "symbol": "SOLUSDT", "color": "#FF9800"},
]

for config in engine_configs:
    widget = TradingEngineWidget(config["name"], config["color"], self)
    widget.start_signal.connect(self._on_engine_start)
    widget.stop_signal.connect(self._on_engine_stop)
    main_layout.addWidget(widget)
    self.engine_widgets[config["name"]] = widget
```

#### 4.2 WebSocket 메시지 처리 수정
```python
# 변경 전 (Line 1012-1029)
if engine_name == "Alpha":
    self.alpha_engine.update_energy_analysis(data)
elif engine_name == "Beta":
    self.beta_engine.update_energy_analysis(data)
elif engine_name == "Gamma":
    self.gamma_engine.update_energy_analysis(data)

# 변경 후 (동적)
if engine_name in self.engine_widgets:
    self.engine_widgets[engine_name].update_energy_analysis(data)
```

**영향도**: ⚠️ **CRITICAL**
- GUI Footer 전체 재설계
- 사용자 경험 변경

---

### **Phase 5: 전략 파일 삭제**

**목적**: 물리적 파일 삭제 및 Import 정리

**삭제 대상 파일**:
1. `backend/core/strategies/alpha_strategy.py` (453줄)
2. `backend/core/strategies/beta_strategy.py` (364줄)
3. `backend/core/strategies/gamma_strategy.py` (426줄)

**수정 파일**:
- `backend/core/strategies/__init__.py`

```python
# 변경 전
from .alpha_strategy import AlphaStrategy
from .beta_strategy import BetaStrategy
from .gamma_strategy import GammaStrategy
from .new_strategy_wrapper import NewStrategyWrapper

__all__ = ["AlphaStrategy", "BetaStrategy", "GammaStrategy", "NewStrategyWrapper"]

# 변경 후
from .new_strategy_wrapper import NewStrategyWrapper

__all__ = ["NewStrategyWrapper"]
```

**영향도**: ⚠️ **MEDIUM**
- Import 오류 발생 가능
- Phase 2-4 완료 후 안전

---

### **Phase 6: Database 정리**

**목적**: 레거시 설정 데이터 제거 및 NewModular 설정 추가

**작업**:

#### 6.1 기존 데이터 백업 (선택)
```sql
-- Alpha/Beta/Gamma 설정 백업
SELECT * FROM engine_settings WHERE engine_name IN ('Alpha', 'Beta', 'Gamma');
```

#### 6.2 레거시 데이터 삭제
```sql
DELETE FROM engine_settings WHERE engine_name IN ('Alpha', 'Beta', 'Gamma');
```

#### 6.3 NewModular 설정 추가
```sql
INSERT INTO engine_settings (engine_name, leverage, designated_funds, is_active, updated_at)
VALUES ('NewModular', 50, 1000.0, 0, datetime('now'));
```

**영향도**: ⚠️ **LOW**
- 데이터만 삭제, 테이블 구조 유지

---

## 📋 삭제 체크리스트

### Phase 1: 검증 ✅
- [x] NewModular 7개 모듈 구현
- [x] 실데이터 사용 확인
- [x] 주문 실행 확인
- [x] GUI/Backend 통합 확인

### Phase 2: EngineManager
- [ ] Import 수정 (`NewStrategyWrapper`)
- [ ] 엔진 초기화 로직 수정 (3개 → 1개)
- [ ] 엔진 이름 검증 로직 제거
- [ ] WebSocket 메시지 타입 변경
- [ ] 테스트: 엔진 시작/정지

### Phase 3: API Routes
- [ ] 스키마 주석 수정
- [ ] 하드코딩 검증 로직 제거 또는 동적화
- [ ] 모든 API 엔드포인트 테스트
- [ ] Swagger 문서 확인

### Phase 4: GUI
- [ ] FooterEnginesWidget 리팩토링
  - [ ] 위젯 초기화 (3개 → 1개 또는 동적)
  - [ ] WebSocket 메시지 처리 (동적)
  - [ ] 시작/정지 신호 연결
  - [ ] 에너지 분석 차트 업데이트
- [ ] 레이아웃 조정
- [ ] 색상 테마 적용
- [ ] GUI 테스트 (시작/정지/상태 표시)

### Phase 5: 파일 삭제
- [ ] `alpha_strategy.py` 삭제
- [ ] `beta_strategy.py` 삭제
- [ ] `gamma_strategy.py` 삭제
- [ ] `__init__.py` 수정
- [ ] Import 오류 확인 (전체 코드베이스)

### Phase 6: Database
- [ ] 기존 데이터 백업 (선택)
- [ ] Alpha/Beta/Gamma 설정 삭제
- [ ] NewModular 설정 추가
- [ ] DB 연결 테스트

### 최종 검증
- [ ] Backend 서버 실행 (오류 없음)
- [ ] GUI 실행 (표시 정상)
- [ ] NewModular 엔진 시작 (정상 작동)
- [ ] 실제 주문 실행 (테스트넷)
- [ ] WebSocket 메시지 수신 (GUI 업데이트)
- [ ] 거래 기록 DB 저장 (정상)
- [ ] 로그 파일 확인 (오류 없음)

---

## ⚠️ 위험 요소 및 대응

### 1. Import 오류
**위험**: Phase 5 파일 삭제 후 Import 오류
**대응**: Phase 2-4 완료 후 삭제, 전체 코드베이스 검색

### 2. GUI 표시 오류
**위험**: FooterEnginesWidget 리팩토링 중 UI 깨짐
**대응**: 단계별 테스트, 백업 코드 유지

### 3. WebSocket 메시지 불일치
**위험**: Backend ↔ GUI 메시지 타입 불일치
**대응**: 메시지 타입 명세 작성, 통합 테스트

### 4. Database 마이그레이션 실패
**위험**: 설정 데이터 손실
**대응**: 백업 우선, 트랜잭션 사용

### 5. 실전 거래 중 삭제
**위험**: 포지션 보유 중 엔진 삭제
**대응**: **모든 엔진 정지 후 삭제**, 포지션 청산 확인

---

## 🚀 권장 삭제 일정

### **Day 1: Phase 2-3 (Backend)**
- EngineManager 리팩토링
- API Routes 리팩토링
- Backend 서버 테스트

### **Day 2: Phase 4 (GUI)**
- FooterEnginesWidget 리팩토링
- GUI 테스트
- WebSocket 메시지 테스트

### **Day 3: Phase 5-6 (삭제 및 정리)**
- 파일 삭제
- Database 정리
- 통합 테스트

### **Day 4: 최종 검증**
- 테스트넷 실거래 테스트
- 로그 분석
- 성능 모니터링

---

## 📝 삭제 후 구조

### Backend
```
backend/core/
├── engine_manager.py         # NewModular만 관리
├── yona_service.py           # 변경 없음 (EngineManager 사용)
└── strategies/
    ├── __init__.py           # NewStrategyWrapper만 Export
    ├── base_strategy.py      # 유지
    ├── new_strategy_wrapper.py  # 유지
    └── [Alpha/Beta/Gamma 삭제]
```

### GUI
```
gui/widgets/
├── footer_engines_widget.py  # 단일 또는 동적 위젯
└── [3개 고정 위젯 → 1개 또는 동적]
```

### API
```
/api/v1/engine/start          # engine: "NewModular"
/api/v1/engine/stop           # engine: "NewModular"
/api/v1/engine/status/{name}  # name: "NewModular"
```

### Database
```sql
engine_settings:
- Alpha   [삭제]
- Beta    [삭제]
- Gamma   [삭제]
+ NewModular [추가]
```

---

## 🎯 최종 목표

**단일 통합 엔진 시스템**
- ✅ NewModular 1개 엔진으로 통합
- ✅ 레거시 코드 제거 (1,243줄 삭제)
- ✅ 유지보수성 향상 (모듈형 구조)
- ✅ 확장성 향상 (다중 심볼 지원 가능)
- ✅ 코드 품질 개선 (테스트 가능)

---

## ⚠️ 중요 공지

**본 문서는 삭제 계획서입니다.**

**실제 삭제는 사용자의 명시적 승인 후 진행됩니다.**

**삭제 전 필수 확인 사항**:
1. ✅ NewModular 엔진 완전 작동 확인
2. ✅ 테스트넷 검증 완료
3. ✅ 백업 완료 (코드 + Database)
4. ✅ 모든 엔진 정지 및 포지션 청산
5. ✅ 사용자 승인

---

**삭제 승인 대기 중...**
