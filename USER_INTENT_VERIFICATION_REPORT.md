# 사용자 의도 기반 기능 검증 보고서

## 📋 검증 목적

사용자가 의도한 각 기능의 구현 방식을 확인하고, 사용자 의도와의 일치 여부를 검증합니다.

---

## 🎯 사용자 의도 정리

### 1. Initial Investment (초기 투자금)
- **목적**: 바이낸스 선물 거래 자동 매매를 위한 초기 투입 자금
- **표시 방식**: 
  - 앱 실행 시 바이낸스 'USD s-M Futures'의 초기 자금을 **고정 표기**
  - 거래가 진행되는 동안에도 **변경되지 않고 초기값 유지**
  - 수익/손실과 무관하게 항상 초기 투자금만 표시

### 2. Account total balance (총 계좌 잔액)
- **초기 상태**: Initial Investment와 동일한 금액 표시
- **자금 배분 시**:
  - 각 엔진의 'Designated Funds' 슬라이더로 배분 설정 시
  - 배분된 금액만큼 **차감**되어 표시
  - 예: 10,000 USDT → Alpha 30% (3,000), Beta 30% (3,000), Gamma 30% (3,000) 배분
  - Account total balance = 10,000 - 3,000 - 3,000 - 3,000 = **1,000 USDT** 표시
- **거래 결과 반영**:
  - 각 엔진의 거래 결과(수익/손실) 확정 시
  - Account total balance에 **정확하고 올바르게 반영**
  - 실시간으로 업데이트

### 3. P&L % (수익/손실률)
- **계산 기준**: 모든 거래가 확정된 수익/손실을 기반으로 계산
- **계산 공식**: 
  ```
  P&L % = ((Account total balance - Initial Investment) / Initial Investment) * 100
  ```
- **표시 시점**: 거래가 확정되면 실시간으로 업데이트

---

## 🔍 현재 구현 검증

### 1. Initial Investment 구현 상태

#### 현재 구현 위치
- **백엔드**: `backend/core/account_manager.py`
  - `initial_capital`: 초기 자본 저장
  - `update_account_info()`: 첫 계좌 조회 시 `total_wallet_balance`를 `initial_capital`로 설정

```python
# AccountManager.__init__()
self.initial_capital: float = 0.0  # 투입 자금 (초기 자본)
self._initial_capital_set: bool = False

# update_account_info()
if not self._initial_capital_set and self.total_wallet_balance > 0:
    self.initial_capital = self.total_wallet_balance
    self._initial_capital_set = True
```

- **프론트엔드**: `gui/widgets/header_widget.py`
  - `_update_header_data()`: WebSocket으로 받은 `initial_capital` 표시

```python
initial_capital = data.get("initial_capital")
if initial_capital is not None:
    label.setText(f"$ {initial_capital:,.2f}")
```

#### 검증 결과
- ✅ **초기 설정**: 첫 계좌 조회 시 자동으로 초기 자본 설정
- ⚠️ **고정 유지**: `_initial_capital_set` 플래그로 한 번만 설정하지만, 재시작 시 다시 설정될 수 있음
- ⚠️ **문제점**: 
  - 앱 재시작 시 초기값이 변경될 수 있음 (사용자 의도: 항상 고정값 유지)
  - 바이낸스 잔고가 변경되어도 초기값은 유지되어야 하지만, 현재는 첫 조회 시점의 값 사용

**평가**: ⚠️ **부분 일치** - 초기 설정은 되지만 완전한 고정 메커니즘이 없음

---

### 2. Account total balance 구현 상태

#### 현재 구현 위치
- **백엔드**: `backend/core/account_manager.py`
  - `total_wallet_balance`: 바이낸스 API에서 가져온 총 지갑 잔액 (미실현 손익 포함)

```python
# update_account_info()
self.total_wallet_balance = float(account_info.get("totalWalletBalance", 0.0))

# get_header_data()
return {
    "total_balance": self.total_wallet_balance,  # 바이낸스 잔고 그대로 반환
    ...
}
```

- **프론트엔드**: `gui/widgets/header_widget.py`
  - 바이낸스 API에서 받은 `total_wallet_balance`를 그대로 표시

#### 검증 결과
- ❌ **자금 배분 차감 로직 없음**: 
  - Designated Funds 슬라이더로 배분 설정해도 Account total balance에서 차감되지 않음
  - 현재는 바이낸스 API에서 받은 값(`total_wallet_balance`)을 그대로 표시
- ✅ **거래 결과 반영**: 
  - 바이낸스 API에서 미실현 손익이 포함된 `totalWalletBalance`를 가져오므로 거래 결과는 자동 반영됨
- ❌ **문제점**: 
  - 배분된 자금 차감 로직이 전혀 없음
  - 예: 10,000 USDT에서 3개 엔진에 각각 3,000 USDT 배분해도 Account total balance는 여전히 10,000 USDT 표시

**평가**: ❌ **불일치** - 사용자 의도와 다름 (배분 차감 로직 필요)

---

### 3. Designated Funds 슬라이더 구현 상태

#### 현재 구현 위치
- **프론트엔드**: `gui/widgets/footer_engines_widget.py`

```python
def _on_funds_slider_changed(self, value):
    """투입 자금 슬라이더 값 변경"""
    # TODO: 실제 총 자금은 API에서 가져와야 함 (현재는 예시 값)
    total_balance = 10000  # ❌ 하드코딩
    allocated_amount = (value / 100) * total_balance
    
    self.funds_value_label.setText(f"{value}% (${allocated_amount:.2f})")
    self.designated_funds = allocated_amount
```

#### 검증 결과
- ⚠️ **슬라이더 UI**: 정상 작동 (10%~100%)
- ❌ **실제 잔고 연동**: 하드코딩된 10,000 USDT 사용
- ❌ **Account total balance 차감**: 배분 설정해도 차감되지 않음
- ❌ **문제점**: 
  - Account total balance와 연동되지 않음
  - 배분된 자금을 추적하는 메커니즘이 없음
  - 3개 엔진의 배분 합계를 계산하는 로직이 없음

**평가**: ❌ **불일치** - 사용자 의도와 다름 (배분 차감 및 추적 로직 필요)

---

### 4. P&L % 계산 구현 상태

#### 현재 구현 위치
- **백엔드**: `backend/core/account_manager.py`

```python
def get_header_data(self) -> Dict[str, Any]:
    pnl_percent = 0.0
    if self.initial_capital > 0:
        current_total_value = self.total_wallet_balance
        pnl_percent = ((current_total_value - self.initial_capital) / self.initial_capital) * 100.0
    
    return {
        "pnl_percent": pnl_percent
    }
```

#### 검증 결과
- ✅ **계산 공식**: 정확함 `((total_balance - initial_capital) / initial_capital) * 100`
- ⚠️ **계산 기준**: 
  - 현재: `total_wallet_balance` (바이낸스 API 값, 배분 차감 없음)
  - 사용자 의도: 배분 차감 후 잔액 기준
- ❌ **문제점**: 
  - Account total balance에 배분 차감이 반영되지 않으면 P&L 계산이 부정확함
  - 예: 초기 10,000 USDT, 9,000 USDT 배분 후 → Account total balance는 1,000 USDT여야 하는데
  - 현재는 바이낸스 잔고(예: 11,000 USDT)를 그대로 사용 → P&L 계산 오류

**평가**: ⚠️ **부분 일치** - 공식은 맞지만 계산 기준이 사용자 의도와 다름

---

## 🚨 발견된 모순점 및 문제점

### 문제점 1: Account total balance 배분 차감 로직 부재 ⚠️ **중요**

**사용자 의도**:
```
초기: Account total balance = 10,000 USDT
Alpha 30% 배분: 3,000 USDT
Beta 30% 배분: 3,000 USDT  
Gamma 30% 배분: 3,000 USDT
→ Account total balance = 10,000 - 9,000 = 1,000 USDT 표시
```

**현재 구현**:
```
초기: Account total balance = 10,000 USDT (바이낸스 API 값)
Alpha 30% 배분: 3,000 USDT (로컬 변수만 저장, 차감 안 됨)
Beta 30% 배분: 3,000 USDT (로컬 변수만 저장, 차감 안 됨)
Gamma 30% 배분: 3,000 USDT (로컬 변수만 저장, 차감 안 됨)
→ Account total balance = 10,000 USDT 그대로 표시 ❌
```

**영향**: 
- 사용자가 자금 배분을 설정해도 Account total balance가 차감되지 않음
- 실제 사용 가능한 잔액과 표시되는 잔액이 다름

---

### 문제점 2: Designated Funds 실제 잔고 연동 부재 ⚠️ **중요**

**사용자 의도**:
- 슬라이더가 실제 Account total balance를 기준으로 배분 금액 계산

**현재 구현**:
- 하드코딩된 10,000 USDT 사용
- 실제 Account total balance와 무관하게 계산

**영향**:
- 실제 잔고와 다른 기준으로 계산됨

---

### 문제점 3: 배분 자금 추적 메커니즘 부재 ⚠️ **중요**

**사용자 의도**:
- 각 엔진에 배분된 자금을 추적
- 3개 엔진의 배분 합계를 계산하여 Account total balance에서 차감

**현재 구현**:
- 각 엔진이 독립적으로 `designated_funds` 저장
- 배분 합계를 계산하는 로직이 없음
- Account total balance 차감 로직이 없음

**영향**:
- 배분 자금 추적 불가
- Account total balance 차감 불가

---

### 문제점 4: Initial Investment 고정 메커니즘 불완전 ⚠️ **보통**

**사용자 의도**:
- 앱 실행 시 초기값 설정 후 **항상 고정** (변경 불가)

**현재 구현**:
- 첫 계좌 조회 시 한 번만 설정 (`_initial_capital_set` 플래그 사용)
- 앱 재시작 시 다시 설정될 수 있음

**영향**:
- 앱 재시작 시 초기값이 변경될 수 있음
- 완전한 고정 메커니즘이 아님

---

### 문제점 5: P&L % 계산 기준 불일치 ⚠️ **중요**

**사용자 의도**:
```
P&L % = ((Account total balance(배분 차감 후) - Initial Investment) / Initial Investment) * 100
```

**현재 구현**:
```
P&L % = ((total_wallet_balance(바이낸스 API 값) - initial_capital) / initial_capital) * 100
```

**차이점**:
- 현재: 바이낸스 API 값(배분 차감 없음) 사용
- 사용자 의도: 배분 차감 후 잔액 사용

**영향**:
- Account total balance에 배분 차감이 반영되지 않으면 P&L 계산이 부정확함

---

## 📊 종합 평가

| 기능 | 사용자 의도 | 현재 구현 | 일치 여부 | 우선순위 |
|------|------------|----------|----------|---------|
| **Initial Investment 고정** | 항상 고정값 유지 | 부분 고정 (재시작 시 변경 가능) | ⚠️ 부분 일치 | 보통 |
| **Account total balance 배분 차감** | 배분 시 차감 후 표시 | 차감 로직 없음 | ❌ 불일치 | **높음** |
| **Designated Funds 실제 잔고 연동** | 실제 Account total balance 기준 | 하드코딩된 값 사용 | ❌ 불일치 | **높음** |
| **배분 자금 추적** | 3개 엔진 배분 합계 추적 | 추적 메커니즘 없음 | ❌ 불일치 | **높음** |
| **P&L % 계산 기준** | 배분 차감 후 잔액 기준 | 바이낸스 API 값 기준 | ⚠️ 부분 일치 | **높음** |
| **거래 결과 반영** | 거래 확정 시 Account total balance 업데이트 | 바이낸스 API로 자동 반영 | ✅ 일치 | - |

---

## ✅ 사용자 의도에 맞는 구현 방안

### 1. Initial Investment 고정 메커니즘 강화

**구현 방안**:
- 초기값 설정 시 DB 또는 설정 파일에 저장
- 앱 재시작 시 저장된 값 사용
- 설정 변경 기능 추가 (선택 사항)

---

### 2. Account total balance 배분 차감 로직 구현

**구현 방안**:
- **메인 윈도우**에서 모든 엔진의 배분 자금 추적
- 각 엔진의 Designated Funds 변경 시 배분 합계 재계산
- Account total balance = 바이낸스 잔고 - 배분 합계
- 헤더에 배분 차감 후 잔액 표시

**예시 로직**:
```python
# 메인 윈도우 또는 AccountManager에서
def calculate_available_balance(self):
    total_allocated = (
        alpha_engine.designated_funds +
        beta_engine.designated_funds +
        gamma_engine.designated_funds
    )
    binance_balance = self.account_manager.get_total_balance()
    available_balance = binance_balance - total_allocated
    return available_balance
```

---

### 3. Designated Funds 실제 잔고 연동

**구현 방안**:
- 메인 윈도우에서 Account total balance를 각 엔진 위젯으로 전달
- WebSocket을 통해 Account total balance 업데이트 시 엔진 위젯에도 전달
- 슬라이더 변경 시 실제 잔고 기준으로 계산

---

### 4. 배분 자금 추적 메커니즘 구현

**구현 방안**:
- **메인 윈도우** 또는 **AccountManager**에서 배분 자금 집중 관리
- 각 엔진의 배분 변경 시 시그널 발송
- 배분 합계를 실시간 계산하여 Account total balance에 반영

---

### 5. P&L % 계산 기준 수정

**구현 방안**:
- Account total balance가 배분 차감 후 잔액이므로
- P&L 계산은 현재 방식 유지하되, Account total balance를 배분 차감 후 값으로 사용

---

## 🔧 수정 필요 파일 목록

### 우선순위 1 (필수)

1. **`backend/core/account_manager.py`**
   - 배분 자금 추적 기능 추가
   - Account total balance 계산 로직 수정 (배분 차감)

2. **`gui/main.py`**
   - 모든 엔진의 배분 자금 집중 관리
   - Account total balance 계산 및 전달

3. **`gui/widgets/footer_engines_widget.py`**
   - 실제 Account total balance 연동
   - 배분 변경 시 시그널 발송

4. **`gui/widgets/header_widget.py`**
   - 배분 차감 후 Account total balance 표시

### 우선순위 2 (권장)

5. **`backend/core/yona_service.py`**
   - Account total balance 계산 로직 수정

6. **설정 파일 또는 DB**
   - Initial Investment 고정값 저장

---

## ✅ 결론

### 현재 상태 요약

1. **Initial Investment**: ⚠️ 부분 구현 (고정 메커니즘 불완전)
2. **Account total balance**: ❌ 불일치 (배분 차감 로직 없음)
3. **Designated Funds**: ❌ 불일치 (실제 잔고 연동 및 배분 추적 없음)
4. **P&L %**: ⚠️ 부분 일치 (계산 기준 불일치)

### 주요 문제점

1. ❌ **Account total balance 배분 차감 로직 부재** (가장 중요)
2. ❌ **Designated Funds 실제 잔고 연동 부재**
3. ❌ **배분 자금 추적 메커니즘 부재**
4. ⚠️ **P&L % 계산 기준 불일치**

### 권장 사항

**즉시 수정 필요**:
- Account total balance 배분 차감 로직 구현
- Designated Funds 실제 잔고 연동
- 배분 자금 추적 메커니즘 구현

**향후 개선**:
- Initial Investment 고정 메커니즘 강화
- P&L % 계산 기준 수정

---

**검증 일시**: 2025-01-XX  
**검증자**: AI Assistant  
**검증 범위**: Initial Investment, Account total balance, Designated Funds, P&L %


