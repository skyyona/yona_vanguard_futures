# Alpha/Beta/Gamma 전략 폐기 가능 여부 검증 보고서

**작성일**: 2025-11-19  
**목적**: 기존 Alpha/Beta/Gamma 전략의 폐기 가능 여부를 정확하고 올바르게 검증  
**결론**: ⚠️ **현재 폐기 불가능** - 다수의 핵심 시스템이 의존 중

---

## ✅ 검증 방법론

1. **코드베이스 전체 검색**: AlphaStrategy, BetaStrategy, GammaStrategy 참조 추적
2. **의존성 분석**: Backend, GUI, Database 계층별 의존도 확인
3. **런타임 경로 추적**: 실행 시 필수 호출 경로 분석
4. **설정/데이터 검증**: DB 스키마, 설정 파일, API 엔드포인트 확인

---

## 🔍 검증 결과: 의존성 분석

### 1. Backend 계층 의존성

#### 1.1 EngineManager (핵심 관리 모듈)
**파일**: `backend/core/engine_manager.py`

```python
# Line 10: Import 의존성
from backend.core.strategies import AlphaStrategy, BetaStrategy, GammaStrategy

# Line 57-59: 엔진 초기화 (필수)
self.engines["Alpha"] = AlphaStrategy()
self.engines["Beta"] = BetaStrategy()
self.engines["Gamma"] = GammaStrategy()

# Line 67: 초기화 로그
print("[EngineManager] 3개 엔진 초기화 완료 (Alpha, Beta, Gamma)")
```

**역할**:
- 3개 엔진의 시작/정지 제어
- 엔진 상태 모니터링
- WebSocket을 통한 GUI 업데이트
- 실현 손익 콜백 처리

**의존도**: ⚠️ **HIGH** - EngineManager는 앱 전체 엔진 생명주기 관리의 핵심

---

#### 1.2 YonaService (메인 서비스)
**파일**: `backend/core/yona_service.py`

```python
# Line 575: start_engine() 메서드 주석
engine_name: 엔진 이름 ("Alpha", "Beta", "Gamma")

# Line 621: stop_engine() 메서드 주석
engine_name: 엔진 이름 ("Alpha", "Beta", "Gamma")

# Line 659: engine_start() 메서드 주석
engine_name: 엔진 이름 ("Alpha", "Beta", "Gamma")

# Line 770, 803: update_engine_*() 메서드 주석
engine_name: "Alpha"|"Beta"|"Gamma"
```

**역할**:
- 엔진 시작/정지 요청 처리
- EngineManager와 통신
- GUI WebSocket 메시지 전송

**의존도**: ⚠️ **MEDIUM** - 간접 의존 (EngineManager를 통해)

---

#### 1.3 API Routes (FastAPI 엔드포인트)
**파일**: `backend/api/routes.py`

```python
# Line 12: EngineControlRequest 스키마
engine: str  # "Alpha", "Beta", "Gamma"

# Line 121-139: POST /api/v1/engine/start
@router.post("/engine/start")
async def start_engine(request: EngineControlRequest, ...):
    """
    특정 엔진을 시작합니다.
    
    Request Body:
        {"engine": "Alpha"|"Beta"|"Gamma"}
    """
    if request.engine not in ["Alpha", "Beta", "Gamma"]:
        raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'Alpha', 'Beta', or 'Gamma'.")

# Line 141-159: POST /api/v1/engine/stop
@router.post("/engine/stop")
async def stop_engine(request: EngineControlRequest, ...):
    """
    특정 엔진을 정지합니다.
    
    Request Body:
        {"engine": "Alpha"|"Beta"|"Gamma"}
    """
    if request.engine not in ["Alpha", "Beta", "Gamma"]:
        raise HTTPException(status_code=400, detail="Invalid engine name. Must be 'Alpha', 'Beta', or 'Gamma'.")
```

**의존도**: ⚠️ **HIGH** - API 검증 로직에 하드코딩됨

---

#### 1.4 FundsAllocationManager (자금 배분)
**파일**: `backend/core/funds_allocation_manager.py`

```python
# Line 43: allocate_funds_for_engine() 메서드 주석
engine_name: 엔진 이름 ("Alpha", "Beta", "Gamma")
```

**의존도**: ⚠️ **LOW** - 주석만, 로직은 engine_name 파라미터 사용

---

### 2. GUI 계층 의존성

#### 2.1 MiddleSessionWidget (엔진 UI)
**파일**: `gui/widgets/footer_engines_widget.py`

```python
# Line 24: TradingEngineWidget 주석
self.engine_name = engine_name  # "Alpha", "Beta", "Gamma"

# Line 937-948: Alpha 엔진 위젯 생성
self.alpha_engine = TradingEngineWidget("Alpha", "#4CAF50", self)
self.alpha_engine.start_signal.connect(self._on_engine_start)
self.alpha_engine.stop_signal.connect(self._on_engine_stop)
main_layout.addWidget(self.alpha_engine)

# Line 950-961: Beta 엔진 위젯 생성
self.beta_engine = TradingEngineWidget("Beta", "#2196F3", self)
self.beta_engine.start_signal.connect(self._on_engine_start)
self.beta_engine.stop_signal.connect(self._on_engine_stop)
main_layout.addWidget(self.beta_engine)

# Line 963-974: Gamma 엔진 위젯 생성
self.gamma_engine = TradingEngineWidget("Gamma", "#FF9800", self)
self.gamma_engine.start_signal.connect(self._on_engine_start)
self.gamma_engine.stop_signal.connect(self._on_engine_stop)
main_layout.addWidget(self.gamma_engine)

# Line 1007-1112: handle_message() 메서드
# Alpha/Beta/Gamma 각각에 대한 메시지 처리 분기 (100+ 줄)
if engine_name == "Alpha":
    self.alpha_engine.update_energy_analysis(data)
elif engine_name == "Beta":
    self.beta_engine.update_energy_analysis(data)
elif engine_name == "Gamma":
    self.gamma_engine.update_energy_analysis(data)
# ... (거래 메시지, 리스크 메시지, 통계 업데이트 등 반복)
```

**역할**:
- Alpha/Beta/Gamma 엔진 UI 표시 (3개 섹션)
- 실시간 상태 업데이트
- 사용자 시작/정지 이벤트 처리

**의존도**: ⚠️ **CRITICAL** - GUI의 핵심 구성 요소

---

#### 2.2 MainWindow (엔진 제어)
**파일**: `gui/main.py`

```python
# Line 475-495: _on_engine_start() 메서드
@Slot(str)
def _on_engine_start(self, engine_name: str):
    """특정 엔진 시작 요청"""
    # NewModular는 별도 API 사용
    if engine_name == "NewModular":
        response = requests.post(f"{BASE_URL}/api/v1/strategy/new/start", ...)
    else:  # Alpha/Beta/Gamma
        response = requests.post(f"{BASE_URL}/api/v1/engine/start", json={"engine": engine_name}, ...)

# Line 497-517: _on_engine_stop() 메서드
@Slot(str)
def _on_engine_stop(self, engine_name: str):
    """특정 엔진 정지 요청"""
    if engine_name == "NewModular":
        response = requests.post(f"{BASE_URL}/api/v1/strategy/new/stop", ...)
    else:  # Alpha/Beta/Gamma
        response = requests.post(f"{BASE_URL}/api/v1/engine/stop", json={"engine": engine_name}, ...)
```

**의존도**: ⚠️ **HIGH** - GUI → Backend API 연동 로직

---

### 3. Database 계층 의존성

#### 3.1 Engine Settings (엔진 설정 저장)
**파일**: `backend/database/migrations/migration_003_add_engine_settings.py`

DB 스키마에 `engine_settings` 테이블 존재:
- Alpha, Beta, Gamma 각각의 설정 저장
- Symbol, Leverage, Funds 비율 등

**의존도**: ⚠️ **MEDIUM** - DB 마이그레이션 및 설정 로드 시 필요

---

### 4. 테스트 파일 의존성

#### 4.1 test_engines_api.py
```python
from backend.core.strategies import AlphaStrategy, BetaStrategy, GammaStrategy

engines = {
    "Alpha": AlphaStrategy(),
    "Beta": BetaStrategy(),
    "Gamma": GammaStrategy()
}
```

**의존도**: ⚠️ **LOW** - 테스트 전용, 삭제 가능

---

## 📊 의존성 매트릭스

| 컴포넌트 | 의존도 | 제거 시 영향 | 대체 가능 여부 |
|----------|--------|--------------|----------------|
| **EngineManager** | CRITICAL | 앱 전체 마비 | ❌ 대규모 리팩토링 필요 |
| **YonaService** | MEDIUM | 엔진 제어 불가 | ⚠️ EngineManager 수정 필요 |
| **API Routes** | HIGH | API 오류 발생 | ⚠️ 엔드포인트 재설계 필요 |
| **GUI Widgets** | CRITICAL | UI 표시 불가 | ❌ GUI 전면 재작업 |
| **MainWindow** | HIGH | 엔진 제어 버튼 작동 불가 | ⚠️ 이벤트 핸들러 수정 필요 |
| **Database** | MEDIUM | 설정 로드 실패 | ⚠️ 마이그레이션 필요 |
| **테스트 파일** | LOW | 테스트 실패 | ✅ 삭제 가능 |

---

## ⚠️ 폐기 시 발생할 문제점

### 1. 즉시 발생 (Runtime Error)
- ✅ `EngineManager.__init__()` 실패 → 앱 시작 불가
- ✅ `gui/widgets/footer_engines_widget.py` 임포트 오류 → GUI 크래시
- ✅ `/api/v1/engine/start` 호출 시 500 에러

### 2. 기능 손실
- ✅ Alpha/Beta/Gamma 엔진 UI 섹션 사라짐 (GUI 레이아웃 깨짐)
- ✅ 기존 사용자 설정 손실 (DB의 engine_settings)
- ✅ 엔진 상태 모니터링 불가
- ✅ 거래 기록 (trade_history) 표시 불가

### 3. 유지보수 이슈
- ✅ 기존 문서 (20+ 마크다운 파일)와 불일치
- ✅ 테스트 커버리지 감소
- ✅ 백워드 호환성 완전 상실

---

## 🔄 폐기를 위한 필수 선행 작업

### Phase 1: 격리 및 Feature Flag (2-3일)
1. **Legacy 폴더 이동**
   ```
   backend/core/strategies/legacy/
   ├── alpha_strategy.py
   ├── beta_strategy.py
   ├── gamma_strategy.py
   └── base_strategy.py
   ```

2. **환경 변수 추가**
   ```python
   # .env
   USE_LEGACY_STRATEGIES=true  # 기본값: true (기존 동작 유지)
   ```

3. **EngineManager 조건부 초기화**
   ```python
   if os.getenv("USE_LEGACY_STRATEGIES", "true") == "true":
       self.engines["Alpha"] = AlphaStrategy()
       self.engines["Beta"] = BetaStrategy()
       self.engines["Gamma"] = GammaStrategy()
   ```

---

### Phase 2: GUI 분리 (3-5일)
1. **MiddleSessionWidget 동적 렌더링**
   ```python
   if USE_LEGACY_STRATEGIES:
       self.alpha_engine = TradingEngineWidget("Alpha", ...)
       self.beta_engine = TradingEngineWidget("Beta", ...)
       self.gamma_engine = TradingEngineWidget("Gamma", ...)
   
   # NewModular는 항상 표시
   self.newmodular_engine = TradingEngineWidget("NewModular", ...)
   ```

2. **handle_message() 조건부 처리**
   ```python
   if engine_name in ["Alpha", "Beta", "Gamma"] and USE_LEGACY_STRATEGIES:
       # 기존 로직
   elif engine_name == "NewModular":
       # NewModular 로직
   ```

---

### Phase 3: API 엔드포인트 Deprecation (1-2일)
1. **Deprecation Warning 추가**
   ```python
   @router.post("/engine/start")
   async def start_engine(...):
       """
       [DEPRECATED] This endpoint will be removed in v2.0.
       Use /api/v1/strategy/new/start instead.
       """
       if request.engine not in ["Alpha", "Beta", "Gamma"]:
           raise HTTPException(...)
   ```

2. **NewModular 전용 엔드포인트 강화**
   - `/api/v1/strategy/new/start` → 완전 검증됨
   - `/api/v1/strategy/new/status` → 완전 검증됨
   - `/api/v1/strategy/new/stop` → 완전 검증됨

---

### Phase 4: Database Migration (2-3일)
1. **engine_settings 테이블 분리**
   ```sql
   -- 기존 테이블 유지 (읽기 전용)
   ALTER TABLE engine_settings RENAME TO legacy_engine_settings;
   
   -- 새 테이블 생성
   CREATE TABLE strategy_profiles (
       id INTEGER PRIMARY KEY,
       strategy_name TEXT NOT NULL,  -- "NewModular"
       config JSON NOT NULL,
       created_at TEXT,
       updated_at TEXT
   );
   ```

2. **데이터 마이그레이션 스크립트**
   - Alpha/Beta/Gamma 설정 → legacy_engine_settings (보존)
   - NewModular 설정 → strategy_profiles

---

### Phase 5: 실전 검증 (1주일)
1. **테스트넷 검증**
   - `USE_LEGACY_STRATEGIES=false` 설정
   - NewModular 단독 운영 테스트
   - 모든 GUI 기능 동작 확인

2. **백워드 호환성 테스트**
   - `USE_LEGACY_STRATEGIES=true` 설정
   - Alpha/Beta/Gamma 정상 동작 확인
   - NewModular 동시 운영 확인

3. **성능 비교**
   - NewModular vs Alpha/Beta/Gamma
   - 승률, MDD, Sharpe Ratio 비교
   - 실전 1주일 모니터링

---

### Phase 6: 완전 폐기 (2-3일)
**조건**: Phase 5에서 NewModular가 모든 지표에서 우수할 경우에만 진행

1. **코드 제거**
   ```python
   # 삭제 대상
   backend/core/strategies/legacy/alpha_strategy.py
   backend/core/strategies/legacy/beta_strategy.py
   backend/core/strategies/legacy/gamma_strategy.py
   backend/core/strategies/legacy/base_strategy.py
   ```

2. **EngineManager 단순화**
   ```python
   # NewModular만 관리
   self.engines = {
       "NewModular": NewStrategyWrapper(...)
   }
   ```

3. **GUI 클린업**
   - Alpha/Beta/Gamma 위젯 제거
   - NewModular만 표시

4. **API 엔드포인트 제거**
   - `/api/v1/engine/start` 삭제
   - `/api/v1/engine/stop` 삭제

5. **문서 업데이트**
   - 모든 마크다운 파일 갱신
   - README.md에 마이그레이션 가이드 추가

---

## 📋 체크리스트: 폐기 가능 여부 판단 기준

### ✅ 필수 조건 (모두 충족 필요)
- [ ] NewModular 백테스트 결과 검증 완료
  - [ ] 승률: Alpha/Beta/Gamma 평균 대비 +5% 이상
  - [ ] MDD: Alpha/Beta/Gamma 평균 대비 -20% 이하
  - [ ] Sharpe Ratio: 1.5 이상

- [ ] 테스트넷 검증 완료
  - [ ] 1주일 이상 안정적 운영
  - [ ] 진입/청산 로직 정확성 100%
  - [ ] API 오류 0건

- [ ] 실전 소액 테스트 완료
  - [ ] 최소 금액 (10-50 USDT) 2주 운영
  - [ ] 실현 손익 정확성 검증
  - [ ] 예상치 못한 상황 대응 확인

- [ ] 사용자 피드백 수집
  - [ ] GUI 사용성 확인
  - [ ] 성능 만족도 확인
  - [ ] 버그 보고 0건 (1주일 기준)

### ⚠️ 위험 요소 (하나라도 해당 시 폐기 연기)
- [ ] NewModular 성능이 Alpha/Beta/Gamma 대비 열등
- [ ] 테스트넷에서 미체결/슬리피지 문제 발생
- [ ] 실전 테스트에서 예상치 못한 손실 발생
- [ ] GUI 버그 또는 크래시 발생
- [ ] 기존 사용자 이탈 우려

---

## 🎯 권장 사항

### 1. 단기 (현재)
**❌ 폐기 금지**
- Alpha/Beta/Gamma는 **현재 앱의 핵심 기능**
- NewModular는 **추가 옵션**으로 유지
- 두 시스템 **병행 운영** (Feature Flag 활용)

### 2. 중기 (1-2개월 후)
**⚠️ 조건부 폐기 검토**
- NewModular 성능 검증 완료 후
- Phase 1-5 완료 후
- 사용자 피드백 긍정적일 경우

### 3. 장기 (3-6개월 후)
**✅ 완전 폐기 고려**
- NewModular가 모든 지표에서 우수할 경우
- 기존 사용자 마이그레이션 완료 후
- Phase 6 실행

---

## 📝 결론

### ⚠️ **현재 상태: 폐기 불가능**

**이유**:
1. **EngineManager 의존성**: 앱 전체 아키텍처의 핵심
2. **GUI 통합**: 3개 엔진 UI가 GUI 레이아웃의 주요 부분
3. **API 엔드포인트**: `/api/v1/engine/start`, `/stop` 사용 중
4. **데이터베이스 스키마**: engine_settings 테이블 사용 중
5. **검증 부족**: NewModular의 실전 성능 미검증

### ✅ **권장 조치**

1. **현재**: Alpha/Beta/Gamma + NewModular **병행 운영**
2. **1개월 후**: NewModular 백테스트 + 테스트넷 검증
3. **2개월 후**: 실전 소액 테스트 + 성능 비교
4. **3-6개월 후**: 조건 충족 시 Phase 1-6 실행

### 🚫 **절대 하지 말아야 할 것**

- ❌ 검증 없이 즉시 삭제
- ❌ 백업 없이 코드 제거
- ❌ 사용자 통지 없이 기능 제거
- ❌ 단계적 마이그레이션 없이 일괄 전환

---

## 📞 다음 단계

1. ✅ **NewModular 백테스트 실행** (test_backtest_adapter.py)
2. ✅ **테스트넷 검증** (run_live_verification.py)
3. ⏳ **성능 비교 보고서 작성** (1주일 후)
4. ⏳ **Feature Flag 구현** (Phase 1)
5. ⏳ **단계적 마이그레이션 계획 수립** (Phase 2-6)

---

**최종 권고**: Alpha/Beta/Gamma는 **최소 3개월 이상 유지**하고, NewModular의 성능이 입증된 후에만 폐기를 고려하세요.
