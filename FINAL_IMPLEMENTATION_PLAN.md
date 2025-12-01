# 최종 구현 계획서

## 📋 목적

사용자의 최종 의도에 따라 '상단 헤더'의 'P&L %' 계산 방식을 명확히 정리하고, 전체 기능의 구현 계획을 수립합니다.

---

## 🎯 최종 사용자 의도 정리

### 1. Initial Investment (초기 투자금)

**사용자 의도**:
- 앱 실행 시 계좌 조회로 **자동 설정 후 고정**
- **앱 재시작 시 초기값이 변경되는 것으로 변경**
- 해당 세션 동안 고정 유지

**현재 구현 상태**: ✅ **완전 일치** - 추가 수정 불필요

---

### 2. Account total balance (총 계좌 잔액)

**사용자 의도**:
- **Designated Funds 슬라이더로 배분 시 차감 표기**
- 각 엔진이 거래를 마치고 '거래 종료' 상황이 되면, 해당 수익/손실이 Account total balance에 **추가**되는 것으로 구현

**계산 공식**:
```
Account total balance = 
  Initial Investment 
  - (Alpha 배분 + Beta 배분 + Gamma 배분)
  + (실현된 수익/손실 합계)
```

**동작 흐름**:
```
초기: Account total balance = 10,000 USDT (Initial Investment와 동일)

1. Alpha 슬라이더 30% 설정 → 10,000 × 30% = 3,000 USDT 배분
   Account total balance = 10,000 - 3,000 = 7,000 USDT 표시

2. Beta 슬라이더 30% 설정 → 7,000 × 30% = 2,100 USDT 배분
   Account total balance = 7,000 - 2,100 = 4,900 USDT 표시

3. Gamma 슬라이더 30% 설정 → 4,900 × 30% = 1,470 USDT 배분
   Account total balance = 4,900 - 1,470 = 3,430 USDT 표시

4. Alpha 거래 종료: +500 USDT 수익 실현
   Account total balance = 3,430 + 500 = 3,930 USDT 표시

5. Beta 거래 종료: -200 USDT 손실 실현
   Account total balance = 3,930 - 200 = 3,730 USDT 표시

6. Gamma 거래 종료: +300 USDT 수익 실현
   Account total balance = 3,730 + 300 = 4,030 USDT 표시
```

**현재 구현 상태**: ❌ **불일치** - 구현 필요

---

### 3. Designated Funds 슬라이더

**사용자 의도**:
- Account total balance 총 자금을 배분
- 배분 시 Account total balance에서 **차감되어 표기**
- 현재 Account total balance(배분 차감 후 잔액) 기준으로 계산

**동작**:
```
1. Account total balance = 10,000 USDT (초기)
2. Alpha 슬라이더 30% 설정 → 10,000 × 30% = 3,000 USDT 배분
   Account total balance = 10,000 - 3,000 = 7,000 USDT 표시
3. Beta 슬라이더 30% 설정 → 7,000 × 30% = 2,100 USDT 배분 (차감 후 잔액 기준)
   Account total balance = 7,000 - 2,100 = 4,900 USDT 표시
```

**계산 공식**:
```
배분 금액 = 현재 Account total balance × (슬라이더 퍼센트 / 100)
새로운 Account total balance = 현재 Account total balance - 배분 금액
```

**현재 구현 상태**: ❌ **불일치** - 구현 필요

---

### 4. P&L % (헤더 상단의 수익/손실률) - **최종 수정**

**사용자 의도** (최종 수정):
- 각 엔진들이 Account total balance 자금을 Designated Funds로 배분하여 거래를 실행하는 상황에서는:
  - **이전의 Account total balance 실현 자금의 P&L을 표기**
  - 즉, 배분된 자금에 대한 손익은 거래 종료 전까지 P&L %에 반영하지 않음
- 각 엔진 거래 종료 후 Account total balance에 추가된 수익/손실을 P&L %에 **추가하여 표기**

**계산 공식**:

**1단계: 미배분 잔액 계산**
```
미배분 잔액 = Initial Investment - (Alpha 배분 + Beta 배분 + Gamma 배분)
```

**2단계: 미배분 잔액의 손익 계산**
```
미배분 잔액 손익 = 현재 Account total balance - Initial Investment
미배분 잔액 손익률 = (미배분 잔액 손익 / Initial Investment) * 100
```

**3단계: 실현 손익률 계산**
```
실현 손익률 = (실현된 수익/손실 합계 / Initial Investment) * 100
```

**4단계: 최종 P&L % 계산**
```
P&L % = 미배분 잔액 손익률 + 실현 손익률
```

**또는 단순화**:
```
P&L % = ((Account total balance - Initial Investment) / Initial Investment) * 100

Account total balance = 
  Initial Investment 
  - (배분 합계)
  + (실현된 수익/손실 합계)
```

**예시**:
```
Initial Investment = 10,000 USDT
배분: Alpha 3,000 + Beta 2,100 + Gamma 1,470 = 6,570 USDT
미배분 잔액 = 10,000 - 6,570 = 3,430 USDT

거래 진행 중:
  Account total balance = 3,430 USDT (배분 차감 후 잔액)
  미배분 잔액 손익 = 3,430 - 10,000 = -6,570 USDT
  실현 손익 = 0 USDT (아직 거래 종료 안 됨)
  P&L % = ((-6,570 + 0) / 10,000) * 100 = -65.7%

Alpha 거래 종료: +500 USDT 수익 실현
  Account total balance = 3,430 + 500 = 3,930 USDT
  미배분 잔액 손익 = 3,430 - 10,000 = -6,570 USDT
  실현 손익 = +500 USDT
  P&L % = ((-6,570 + 500) / 10,000) * 100 = -60.7%

Beta 거래 종료: -200 USDT 손실 실현
  Account total balance = 3,930 - 200 = 3,730 USDT
  미배분 잔액 손익 = 3,430 - 10,000 = -6,570 USDT
  실현 손익 = +500 - 200 = +300 USDT
  P&L % = ((-6,570 + 300) / 10,000) * 100 = -62.7%

Gamma 거래 종료: +300 USDT 수익 실현
  Account total balance = 3,730 + 300 = 4,030 USDT
  미배분 잔액 손익 = 3,430 - 10,000 = -6,570 USDT
  실현 손익 = +500 - 200 + 300 = +600 USDT
  P&L % = ((-6,570 + 600) / 10,000) * 100 = -59.7%
```

**현재 구현 상태**: ❌ **불일치** - 수정 필요

---

### 5. 각 엔진의 Total Slot Gain/Loss 및 P&L %

**사용자 의도**:
- 각 엔진의 'Total Slot Gain/Loss'와 'P&L %'는 **해당 엔진의 투입 자금(Designated Funds) 기준**으로 표기
- **거래 진행 중**: 미실현 손익 표시
- **거래 종료 시**: 실현 손익 표시, Account total balance에 추가

**계산 공식**:

**Total Slot Gain/Loss**:
```
거래 진행 중: Total Slot Gain/Loss = 미실현 손익
거래 종료 시: Total Slot Gain/Loss = 실현 손익
```

**P&L % (엔진별)**:
```
거래 진행 중: P&L % = (미실현 손익 / Designated Funds) * 100
거래 종료 시: P&L % = (실현 손익 / Designated Funds) * 100
```

**예시 (Alpha 엔진)**:
```
Designated Funds = 3,000 USDT

거래 진행 중:
  미실현 손익 = +500 USDT
  Total Slot Gain/Loss = +500 USDT
  P&L % = (500 / 3,000) * 100 = +16.67%

거래 종료 시:
  실현 손익 = +500 USDT
  Total Slot Gain/Loss = +500 USDT
  P&L % = (500 / 3,000) * 100 = +16.67%
  → Account total balance에 +500 USDT 추가
  → 헤더 P&L %에 실현 손익률 추가
```

**현재 구현 상태**: ⚠️ **부분 일치** - Designated Funds 기준 계산 및 거래 종료 시 추가 로직 필요

---

## 🔍 현재 구현 상태 검증 (최종)

### 1. Initial Investment
- ✅ **완전 일치**: 추가 수정 불필요

### 2. Account total balance 배분 차감
- ❌ **불일치**: 차감 로직 없음 - 구현 필요

### 3. Account total balance 거래 종료 시 추가
- ❌ **불일치**: 수익/손실 추가 로직 없음 - 구현 필요

### 4. Designated Funds 실제 잔고 연동 및 차감
- ❌ **불일치**: 실제 잔고 연동 및 차감 로직 없음 - 구현 필요

### 5. P&L % (헤더) 계산 방식
- ❌ **불일치**: 
  - 현재: 바이낸스 API 값 기준
  - 의도: (Account total balance - Initial Investment) / Initial Investment * 100
  - Account total balance = Initial Investment - 배분 합계 + 실현 손익 합계
  - 구현 필요

### 6. 각 엔진 손익 추적
- ⚠️ **부분 일치**: Designated Funds 기준 계산 및 거래 종료 시 추가 로직 필요

---

## 📋 구현 필요 항목 (최종 정리)

### 우선순위 1 (필수)

#### 1. Account total balance 배분 차감 로직 구현 ⭐⭐⭐

**구현 내용**:
- 각 엔진의 Designated Funds 배분 추적
- 배분 합계 계산
- Account total balance = Initial Investment - 배분 합계

**구현 위치**:
- `backend/core/account_manager.py`: Account total balance 계산 로직 수정
- 또는 `backend/core/funds_allocation_manager.py` (신규): 배분 자금 추적

**구현 방법**:
```python
class FundsAllocationManager:
    def __init__(self):
        self.allocations = {
            "Alpha": 0.0,
            "Beta": 0.0,
            "Gamma": 0.0
        }
        self.realized_pnl = 0.0  # 실현 손익 합계
    
    def calculate_account_total_balance(self, initial_capital: float) -> float:
        total_allocated = sum(self.allocations.values())
        return initial_capital - total_allocated + self.realized_pnl
```

**예상 소요 시간**: 2시간

---

#### 2. Account total balance 거래 종료 시 수익/손실 추가 로직 구현 ⭐⭐⭐

**구현 내용**:
- 각 엔진의 거래 종료 감지
- 실현 손익 계산
- 실현 손익을 Account total balance에 추가

**구현 위치**:
- `backend/core/engine_manager.py`: 거래 종료 감지 및 실현 손익 전달
- `backend/core/strategies/base_strategy.py`: 거래 종료 시 실현 손익 계산
- `backend/core/funds_allocation_manager.py`: 실현 손익 추가

**구현 방법**:
```python
class EngineManager:
    def on_trade_closed(self, engine_name: str, realized_pnl: float):
        """거래 종료 시 호출"""
        funds_allocation_manager.add_realized_pnl(realized_pnl)
        # Account total balance 업데이트
        account_manager.update_account_total_balance()
```

**예상 소요 시간**: 2시간

---

#### 3. Designated Funds 실제 Account total balance 연동 및 차감 로직 구현 ⭐⭐⭐

**구현 내용**:
- Account total balance(배분 차감 후)를 엔진 위젯으로 전달
- 슬라이더 변경 시 실제 Account total balance 기준으로 계산
- 배분 설정 시 Account total balance에서 차감
- 배분 변경 시 Account total balance 즉시 업데이트

**구현 위치**:
- `gui/main.py`: Account total balance 전달 및 배분 집계
- `gui/widgets/footer_engines_widget.py`: 실제 잔고 기준 계산 및 차감

**구현 방법**:
```python
# gui/main.py
def update_account_total_balance(self, balance: float):
    """Account total balance 업데이트 시 엔진 위젯에 전달"""
    self.middle_session_widget.alpha_engine.set_total_balance(balance)
    self.middle_session_widget.beta_engine.set_total_balance(balance)
    self.middle_session_widget.gamma_engine.set_total_balance(balance)

# gui/widgets/footer_engines_widget.py
def set_total_balance(self, balance: float):
    """Account total balance 설정"""
    self._current_total_balance = balance
    self._update_funds_display()

def _on_funds_slider_changed(self, value):
    """슬라이더 변경 시 실제 Account total balance 기준으로 계산"""
    allocated_amount = (value / 100) * self._current_total_balance
    self.designated_funds = allocated_amount
    # 배분 변경 시그널 발송
    self.allocation_changed.emit(self.engine_name, allocated_amount)
```

**예상 소요 시간**: 2시간

---

#### 4. 각 엔진 손익 추적 메커니즘 구현 ⭐⭐⭐

**구현 내용**:
- 각 엔진의 실현 손익 추적 (거래 완료 시)
- 각 엔진의 미실현 손익 추적 (현재 포지션)
- Designated Funds 기준으로 P&L % 계산
- 거래 종료 시 실현 손익을 Account total balance에 추가

**구현 위치**:
- `backend/core/engine_manager.py`: 각 엔진의 손익 집계
- `backend/core/strategies/base_strategy.py`: 손익 계산 로직
- `backend/api_client/binance_client.py`: 포지션 정보 조회 (필요 시)

**구현 방법**:
```python
class BaseStrategy:
    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """미실현 손익 계산"""
        if not self.in_position or self.entry_price == 0:
            return 0.0
        return (current_price - self.entry_price) * self.position_quantity
    
    def close_position(self, exit_price: float) -> float:
        """포지션 청산 시 실현 손익 계산"""
        realized_pnl = (exit_price - self.entry_price) * self.position_quantity
        # Account total balance에 추가하도록 시그널 발송
        return realized_pnl
    
    def get_engine_pnl_percent(self) -> float:
        """Designated Funds 기준 P&L % 계산"""
        if self.designated_funds == 0:
            return 0.0
        total_pnl = self.unrealized_pnl + self.realized_pnl
        return (total_pnl / self.designated_funds) * 100
```

**예상 소요 시간**: 3시간

---

#### 5. 실현/미실현 손익 구분 구현 ⭐⭐⭐

**구현 내용**:
- 거래 완료(청산) 시 실현 손익 기록
- 현재 포지션의 미실현 손익 계산
- 구분하여 추적 및 표시
- 실현 손익만 Account total balance에 반영

**구현 위치**:
- `backend/core/strategies/base_strategy.py`: 손익 구분 로직
- `backend/core/engine_manager.py`: 손익 집계 및 전달

**구현 방법**:
```python
class BaseStrategy:
    def __init__(self):
        self.unrealized_pnl = 0.0  # 미실현 손익
        self.realized_pnl = 0.0    # 실현 손익 (누적)
    
    def update_unrealized_pnl(self, current_price: float):
        """미실현 손익 업데이트 (거래 진행 중)"""
        if self.in_position:
            self.unrealized_pnl = self.calculate_unrealized_pnl(current_price)
    
    def close_position(self, exit_price: float):
        """포지션 청산 (거래 종료)"""
        realized_pnl = self.calculate_unrealized_pnl(exit_price)
        self.realized_pnl += realized_pnl
        self.unrealized_pnl = 0.0
        # Account total balance에 실현 손익 추가
        return realized_pnl
```

**예상 소요 시간**: 2시간

---

#### 6. P&L % (헤더) 계산 기준 수정 ⭐⭐

**구현 내용**:
- Account total balance 계산 로직 수정
  - Account total balance = Initial Investment - 배분 합계 + 실현 손익 합계
- P&L % 계산 로직 수정
  - P&L % = ((Account total balance - Initial Investment) / Initial Investment) * 100

**구현 위치**:
- `backend/core/account_manager.py`: Account total balance 및 P&L % 계산 로직 수정

**구현 방법**:
```python
class AccountManager:
    def __init__(self, funds_allocation_manager):
        self.funds_allocation_manager = funds_allocation_manager
    
    def get_header_data(self) -> Dict[str, Any]:
        # Account total balance 계산
        total_balance = self.funds_allocation_manager.calculate_account_total_balance(
            self.initial_capital
        )
        
        # P&L % 계산
        pnl_percent = 0.0
        if self.initial_capital > 0:
            pnl_percent = ((total_balance - self.initial_capital) / self.initial_capital) * 100.0
        
        return {
            "initial_capital": self.initial_capital,
            "total_balance": total_balance,
            "pnl_percent": pnl_percent
        }
```

**예상 소요 시간**: 1시간

---

## 📊 구현 계획 요약

### 구현 항목 및 소요 시간

| 항목 | 우선순위 | 난이도 | 예상 시간 |
|------|---------|--------|----------|
| **Account total balance 배분 차감** | 높음 | ⭐⭐⭐ | 2시간 |
| **거래 종료 시 수익/손실 추가** | 높음 | ⭐⭐⭐ | 2시간 |
| **Designated Funds 실제 잔고 연동 및 차감** | 높음 | ⭐⭐⭐ | 2시간 |
| **각 엔진 손익 추적** | 높음 | ⭐⭐⭐ | 3시간 |
| **실현/미실현 손익 구분** | 높음 | ⭐⭐⭐ | 2시간 |
| **P&L % 계산 기준 수정** | 높음 | ⭐⭐ | 1시간 |

**총 예상 소요 시간**: 약 12시간

---

## 🔄 구현 순서 제안

### Phase 1: 기본 구조 (3시간)
1. **FundsAllocationManager 클래스 생성** (1시간)
   - 배분 자금 추적
   - 실현 손익 추적
   - Account total balance 계산 로직

2. **AccountManager 수정** (2시간)
   - FundsAllocationManager 통합
   - Account total balance 계산 로직 수정
   - P&L % 계산 로직 수정

### Phase 2: GUI 연동 (2시간)
3. **메인 윈도우 수정** (1시간)
   - Account total balance 전달 메커니즘
   - 배분 변경 시그널 처리

4. **엔진 위젯 수정** (1시간)
   - 실제 Account total balance 연동
   - 배분 차감 로직 구현

### Phase 3: 손익 추적 (5시간)
5. **BaseStrategy 수정** (2시간)
   - 미실현 손익 계산
   - 실현 손익 계산
   - 거래 종료 감지

6. **EngineManager 수정** (2시간)
   - 각 엔진 손익 집계
   - 거래 종료 시 실현 손익 전달

7. **실현/미실현 손익 구분** (1시간)
   - 손익 구분 로직
   - UI 업데이트

### Phase 4: 통합 및 테스트 (2시간)
8. **전체 통합** (1시간)
   - 모든 기능 연결
   - 데이터 흐름 확인

9. **테스트 및 검증** (1시간)
   - 배분 차감 테스트
   - 거래 종료 시 추가 테스트
   - P&L % 계산 테스트

---

## 📝 구현 세부 사항

### 1. FundsAllocationManager 클래스 (신규)

**파일**: `backend/core/funds_allocation_manager.py`

**기능**:
- 각 엔진의 배분 자금 추적
- 실현 손익 추적
- Account total balance 계산

**메서드**:
```python
class FundsAllocationManager:
    def set_allocation(self, engine_name: str, amount: float)
    def remove_allocation(self, engine_name: str)
    def add_realized_pnl(self, amount: float)
    def calculate_account_total_balance(self, initial_capital: float) -> float
    def get_total_allocated(self) -> float
    def get_realized_pnl(self) -> float
```

---

### 2. AccountManager 수정

**파일**: `backend/core/account_manager.py`

**수정 사항**:
- FundsAllocationManager 통합
- `get_header_data()` 메서드 수정
  - Account total balance 계산 로직 수정
  - P&L % 계산 로직 수정

---

### 3. 메인 윈도우 수정

**파일**: `gui/main.py`

**수정 사항**:
- Account total balance 전달 메커니즘 추가
- 배분 변경 시그널 처리
- Account total balance 업데이트 시 엔진 위젯에 전달

---

### 4. 엔진 위젯 수정

**파일**: `gui/widgets/footer_engines_widget.py`

**수정 사항**:
- `set_total_balance()` 메서드 추가
- `_on_funds_slider_changed()` 메서드 수정
  - 실제 Account total balance 기준으로 계산
- 배분 변경 시그널 추가
- 배분 차감 로직 구현

---

### 5. BaseStrategy 수정

**파일**: `backend/core/strategies/base_strategy.py`

**수정 사항**:
- `unrealized_pnl` 속성 추가
- `realized_pnl` 속성 추가
- `calculate_unrealized_pnl()` 메서드 추가
- `close_position()` 메서드 수정
- `get_engine_pnl_percent()` 메서드 추가

---

### 6. EngineManager 수정

**파일**: `backend/core/engine_manager.py`

**수정 사항**:
- 거래 종료 감지 로직 추가
- 실현 손익 집계 로직 추가
- FundsAllocationManager에 실현 손익 전달
- 각 엔진의 손익 정보 집계

---

## ✅ 검증 항목

### 구현 완료 후 검증할 항목

1. **Initial Investment**:
   - ✅ 앱 실행 시 자동 설정
   - ✅ 재시작 시 초기값 변경

2. **Account total balance 배분 차감**:
   - ✅ Alpha 배분 시 차감 확인
   - ✅ Beta 배분 시 차감 확인
   - ✅ Gamma 배분 시 차감 확인

3. **Account total balance 거래 종료 시 추가**:
   - ✅ Alpha 거래 종료 시 수익 추가 확인
   - ✅ Beta 거래 종료 시 손실 추가 확인
   - ✅ Gamma 거래 종료 시 수익 추가 확인

4. **Designated Funds 실제 잔고 연동**:
   - ✅ 실제 Account total balance 기준으로 계산 확인
   - ✅ Account total balance 업데이트 시 슬라이더 표시 업데이트 확인

5. **P&L % (헤더) 계산**:
   - ✅ 배분 후 P&L % 확인
   - ✅ 거래 종료 후 P&L % 확인
   - ✅ 계산 공식 정확성 확인

6. **각 엔진 손익 추적**:
   - ✅ Designated Funds 기준 계산 확인
   - ✅ 미실현 손익 표시 확인
   - ✅ 실현 손익 표시 확인

---

## ✅ 결론

### 구현 가능성
- ✅ **모든 기능 구현 가능**
- ✅ **기술적 제약 없음**
- ✅ **예상 총 소요 시간**: 약 12시간

### 주요 구현 포인트

1. **Account total balance 계산**:
   ```
   Account total balance = 
     Initial Investment 
     - (배분 합계)
     + (실현 손익 합계)
   ```

2. **P&L % 계산**:
   ```
   P&L % = ((Account total balance - Initial Investment) / Initial Investment) * 100
   ```

3. **거래 종료 시 처리**:
   - 실현 손익 계산
   - Account total balance에 추가
   - P&L % 업데이트

---

**작성 일시**: 2025-01-XX  
**작성자**: AI Assistant  
**문서 버전**: 최종 구현 계획 v1.0


