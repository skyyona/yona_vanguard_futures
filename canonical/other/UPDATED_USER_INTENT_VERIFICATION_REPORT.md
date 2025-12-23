# 수정된 사용자 의도 기반 기능 검증 및 구현 가능성 보고서

## 📋 검증 목적

수정된 사용자 의도에 따라 각 기능의 구현 방식을 정리하고, 구현 가능성을 검증합니다.

---

## 🎯 수정된 사용자 의도 정리

### 1. Initial Investment (초기 투자금)

**사용자 의도**:
- 앱 실행 시 계좌 조회로 **자동 설정 후 고정**
- **앱 재시작 시 초기값이 변경되는 것으로 변경** ✅ (이전 의도와 다름)
- 즉, 앱 재시작 시마다 현재 바이낸스 잔고를 새로운 Initial Investment로 설정
- 설정 후 해당 세션 동안 고정 유지

**동작 흐름**:
```
1. 앱 실행 → 바이낸스 계좌 조회
2. totalWalletBalance 값을 Initial Investment로 설정
3. 해당 세션 동안 고정 유지
4. 앱 재시작 → 다시 현재 잔고를 Initial Investment로 설정 (새로운 세션)
```

---

### 2. Account total balance (총 계좌 잔액)

**사용자 의도**:
- **초기**: Initial Investment와 동일한 금액 표시
- **자금 배분 시**: 
  - 각 엔진의 'Designated Funds' 슬라이더로 배분 설정 시
  - 배분된 금액만큼 **차감**되어 표시
  - 예: 10,000 USDT → Alpha 30% (3,000), Beta 30% (3,000), Gamma 30% (3,000) 배분
  - Account total balance = 10,000 - 3,000 - 3,000 - 3,000 = **1,000 USDT** 표시
- **거래 결과 반영**:
  - Initial Investment 기준으로 각 엔진 거래 실행 상황에서
  - 각 엔진의 수익/손실(실현/미실현) 금액을 Account total balance에 표기
  - 실시간으로 업데이트

**계산 공식**:
```
Account total balance = 
  바이낸스 API 잔고 
  - (Alpha 배분 + Beta 배분 + Gamma 배분)
  + (모든 엔진의 실현 손익 합계)
  + (모든 엔진의 미실현 손익 합계)
```

---

### 3. Designated Funds 슬라이더

**사용자 의도**:
- 슬라이더 작동은 **실제 Account total balance 기준으로 배분**
- 슬라이더 변경 시:
  - 현재 Account total balance(배분 차감 전)를 기준으로 퍼센트 계산
  - 배분 금액 = Account total balance × (슬라이더 퍼센트 / 100)
  - 배분 설정 시 Account total balance에서 차감

**동작 흐름**:
```
1. Account total balance = 10,000 USDT (초기)
2. Alpha 슬라이더 30% 설정 → 10,000 × 30% = 3,000 USDT 배분
3. Account total balance = 10,000 - 3,000 = 7,000 USDT 표시
4. Beta 슬라이더 30% 설정 → 7,000 × 30% = 2,100 USDT 배분 (현재 잔액 기준)
5. Account total balance = 7,000 - 2,100 = 4,900 USDT 표시
```

---

### 4. P&L % (헤더 상단의 수익/손실률)

**사용자 의도**:
- **Initial Investment 기준**으로 계산
- 각 엔진 거래 실행 상황에서 실현/미실현 수익/손실을 모두 포함
- **실시간으로 업데이트**

**계산 공식**:
```
P&L % = ((Account total balance - Initial Investment) / Initial Investment) * 100

Account total balance = 
  Initial Investment 
  - (배분 합계)
  + (모든 엔진의 실현 손익 합계)
  + (모든 엔진의 미실현 손익 합계)
```

**예시**:
```
Initial Investment = 10,000 USDT
배분: Alpha 3,000 + Beta 3,000 + Gamma 3,000 = 9,000 USDT
실현 손익: Alpha +500, Beta -200, Gamma +300 = +600 USDT
미실현 손익: Alpha +100, Beta -50, Gamma +200 = +250 USDT

Account total balance = 10,000 - 9,000 + 600 + 250 = 1,850 USDT
P&L % = ((1,850 - 10,000) / 10,000) * 100 = -81.5% ❌ (잘못된 계산)

올바른 계산:
Account total balance = 바이낸스 잔고 - 배분 = (10,000 + 600 + 250) - 9,000 = 1,850 USDT
P&L % = ((1,850 - 10,000) / 10,000) * 100 = -81.5%
```

---

### 5. 각 엔진의 Total Slot Gain/Loss 및 P&L %

**사용자 의도**:
- 각 엔진의 'Total Slot Gain/Loss'와 'P&L %'는 **해당 엔진의 투입 자금(Designated Funds) 기준**으로 표기
- 해당 엔진만의 수익/손실을 표시

**계산 공식**:

**Total Slot Gain/Loss**:
```
Total Slot Gain/Loss (USDT) = 
  해당 엔진의 실현 손익 + 해당 엔진의 미실현 손익
```

**P&L % (엔진별)**:
```
P&L % = ((Total Slot Gain/Loss) / Designated Funds) * 100
```

**예시 (Alpha 엔진)**:
```
Designated Funds = 3,000 USDT
실현 손익 = +500 USDT
미실현 손익 = +100 USDT

Total Slot Gain/Loss = 500 + 100 = +600 USDT
P&L % = (600 / 3,000) * 100 = +20.0%
```

---

## 🔍 현재 구현 상태 검증

### 1. Initial Investment 구현 상태

#### 현재 구현
- **위치**: `backend/core/account_manager.py`
- **동작**: 첫 계좌 조회 시 `total_wallet_balance`를 `initial_capital`로 설정
- **고정 메커니즘**: `_initial_capital_set` 플래그 사용

```python
if not self._initial_capital_set and self.total_wallet_balance > 0:
    self.initial_capital = self.total_wallet_balance
    self._initial_capital_set = True
```

#### 검증 결과
- ✅ **자동 설정**: 정상 작동
- ✅ **재시작 시 변경**: 현재 구현이 이미 의도와 일치 (재시작 시 플래그 초기화되어 새로운 값 설정)
- ✅ **세션 고정**: 플래그로 세션 동안 고정 유지

**평가**: ✅ **사용자 의도와 일치** - 추가 수정 불필요

---

### 2. Account total balance 구현 상태

#### 현재 구현
- **위치**: `backend/core/account_manager.py`
- **동작**: 바이낸스 API에서 받은 `total_wallet_balance`를 그대로 반환

```python
return {
    "total_balance": self.total_wallet_balance,  # 바이낸스 API 값 그대로
}
```

#### 검증 결과
- ❌ **배분 차감 로직 없음**: Designated Funds 배분 시 차감되지 않음
- ⚠️ **거래 결과 반영**: 바이낸스 API에서 미실현 손익 포함된 값 제공 (부분 반영)
- ❌ **문제점**: 
  - 배분된 자금 차감 로직 필요
  - 실현 손익 추적 메커니즘 필요

**평가**: ❌ **사용자 의도와 불일치** - 배분 차감 및 실현 손익 추적 로직 필요

---

### 3. Designated Funds 슬라이더 구현 상태

#### 현재 구현
- **위치**: `gui/widgets/footer_engines_widget.py`
- **동작**: 하드코딩된 10,000 USDT 기준으로 계산

```python
def _on_funds_slider_changed(self, value):
    total_balance = 10000  # ❌ 하드코딩
    allocated_amount = (value / 100) * total_balance
```

#### 검증 결과
- ❌ **실제 잔고 연동 없음**: 하드코딩된 값 사용
- ❌ **Account total balance 기준 계산 안 됨**: 실제 잔고 기준 아님

**평가**: ❌ **사용자 의도와 불일치** - 실제 Account total balance 연동 필요

---

### 4. P&L % (헤더) 구현 상태

#### 현재 구현
- **위치**: `backend/core/account_manager.py`

```python
pnl_percent = ((self.total_wallet_balance - self.initial_capital) / self.initial_capital) * 100.0
```

#### 검증 결과
- ✅ **계산 공식**: 정확함
- ⚠️ **계산 기준**: 
  - 현재: `total_wallet_balance` (바이낸스 API 값, 배분 차감 없음)
  - 사용자 의도: 배분 차감 후 잔액 기준
- ⚠️ **문제점**: 
  - Account total balance에 배분 차감이 반영되어야 함
  - 현재는 바이낸스 잔고 그대로 사용

**평가**: ⚠️ **부분 일치** - Account total balance 계산 로직 수정 필요

---

### 5. 각 엔진의 Total Slot Gain/Loss 및 P&L % 구현 상태

#### 현재 구현
- **위치**: `gui/widgets/footer_engines_widget.py`

```python
def update_stats(self, data: Dict[str, Any]):
    gain_loss = data.get("total_gain_loss", 0.0)
    pnl_percent = data.get("pnl_percent", 0.0)
    # UI 업데이트만 수행
```

#### 검증 결과
- ⚠️ **데이터 수신**: WebSocket으로 `total_gain_loss`, `pnl_percent` 수신
- ❌ **계산 기준 불명확**: Designated Funds 기준으로 계산되는지 확인 불가
- ❌ **실현/미실현 손익 구분**: 구분되지 않음
- ⚠️ **문제점**: 
  - 백엔드에서 Designated Funds 기준으로 계산해야 함
  - 실현/미실현 손익 구분 필요

**평가**: ⚠️ **부분 일치** - Designated Funds 기준 계산 로직 필요

---

## 🚨 발견된 문제점 및 구현 필요 사항

### 문제점 1: Account total balance 배분 차감 로직 부재 ⚠️ **높음**

**필요 기능**:
- 각 엔진의 Designated Funds 배분 추적
- 배분 합계 계산
- Account total balance = 바이낸스 잔고 - 배분 합계

**구현 필요 위치**:
- `backend/core/account_manager.py` 또는 새로운 `FundsAllocationManager` 클래스

---

### 문제점 2: Designated Funds 실제 잔고 연동 부재 ⚠️ **높음**

**필요 기능**:
- Account total balance(배분 차감 전)를 엔진 위젯으로 전달
- 슬라이더 변경 시 실제 잔고 기준 계산

**구현 필요 위치**:
- `gui/main.py`: Account total balance 전달
- `gui/widgets/footer_engines_widget.py`: 실제 잔고 기준 계산

---

### 문제점 3: 각 엔진의 손익 추적 메커니즘 부재 ⚠️ **높음**

**필요 기능**:
- 각 엔진의 실현 손익 추적
- 각 엔진의 미실현 손익 추적
- Designated Funds 기준으로 P&L % 계산

**구현 필요 위치**:
- `backend/core/engine_manager.py`: 각 엔진의 손익 추적
- `backend/core/strategies/base_strategy.py`: 손익 계산 로직

---

### 문제점 4: 실현/미실현 손익 구분 부재 ⚠️ **높음**

**필요 기능**:
- 거래 완료(청산) 시 실현 손익
- 현재 포지션의 미실현 손익
- 구분하여 추적 및 표시

**구현 필요 위치**:
- `backend/core/strategies/base_strategy.py`: 손익 구분 로직

---

### 문제점 5: Account total balance 계산 로직 통합 필요 ⚠️ **높음**

**필요 기능**:
- 바이낸스 잔고 + 실현 손익 + 미실현 손익 - 배분 합계
- 통합 계산 로직

**구현 필요 위치**:
- `backend/core/account_manager.py`: Account total balance 계산 로직 수정

---

## 📊 구현 가능성 분석

### ✅ 구현 가능한 기능

| 기능 | 구현 가능성 | 난이도 | 예상 소요 시간 |
|------|-----------|--------|---------------|
| **Account total balance 배분 차감** | ✅ 가능 | ⭐⭐⭐ | 2시간 |
| **Designated Funds 실제 잔고 연동** | ✅ 가능 | ⭐⭐ | 1시간 |
| **각 엔진 손익 추적** | ✅ 가능 | ⭐⭐⭐ | 3시간 |
| **실현/미실현 손익 구분** | ✅ 가능 | ⭐⭐⭐ | 2시간 |
| **엔진별 P&L % 계산** | ✅ 가능 | ⭐⭐ | 1시간 |
| **Account total balance 통합 계산** | ✅ 가능 | ⭐⭐⭐ | 2시간 |

---

## 🔧 구현 방안 요약

### 1. Initial Investment
- ✅ **현재 구현 유지**: 재시작 시 자동 설정 후 고정 (이미 의도와 일치)

### 2. Account total balance 배분 차감
- **새로운 클래스**: `FundsAllocationManager`
- **기능**: 배분 자금 추적, 차감 계산
- **위치**: `backend/core/funds_allocation_manager.py` (신규)

### 3. Designated Funds 실제 잔고 연동
- **메인 윈도우**: Account total balance(배분 차감 전) 전달
- **엔진 위젯**: 실제 잔고 기준으로 슬라이더 계산

### 4. 각 엔진 손익 추적
- **BaseStrategy**: 손익 계산 메서드 추가
- **EngineManager**: 각 엔진의 손익 집계
- **실현/미실현 구분**: 포지션 상태로 구분

### 5. P&L % 계산
- **헤더 P&L %**: Account total balance(배분 차감 후) 기준
- **엔진별 P&L %**: Designated Funds 기준

---

## ✅ 종합 평가

### 사용자 의도와의 일치 여부

| 기능 | 사용자 의도 | 현재 구현 | 일치 여부 | 구현 필요성 |
|------|------------|----------|----------|------------|
| **Initial Investment 재시작 시 변경** | ✅ 재시작 시 변경 | ✅ 이미 구현됨 | ✅ 일치 | 불필요 |
| **Account total balance 배분 차감** | 배분 시 차감 | 차감 로직 없음 | ❌ 불일치 | **필요** |
| **Designated Funds 실제 잔고 연동** | 실제 잔고 기준 | 하드코딩 | ❌ 불일치 | **필요** |
| **Account total balance 거래 결과 반영** | 실현/미실현 반영 | 부분 반영 | ⚠️ 부분 일치 | **필요** |
| **헤더 P&L % 계산 기준** | 배분 차감 후 기준 | API 값 기준 | ⚠️ 부분 일치 | **필요** |
| **엔진별 손익 추적** | Designated Funds 기준 | 기준 불명확 | ⚠️ 부분 일치 | **필요** |

---

## 📋 구현 필요 항목 요약

### 우선순위 1 (필수)

1. ✅ **Account total balance 배분 차감 로직 구현**
2. ✅ **Designated Funds 실제 잔고 연동**
3. ✅ **각 엔진 손익 추적 메커니즘 구현**

### 우선순위 2 (중요)

4. ✅ **실현/미실현 손익 구분**
5. ✅ **Account total balance 통합 계산 로직**
6. ✅ **엔진별 P&L % 계산 (Designated Funds 기준)**

---

## ✅ 결론

### 현재 상태 요약

1. **Initial Investment**: ✅ **사용자 의도와 일치** (재시작 시 변경 이미 구현됨)
2. **Account total balance 배분 차감**: ❌ **구현 필요**
3. **Designated Funds 실제 잔고 연동**: ❌ **구현 필요**
4. **각 엔진 손익 추적**: ⚠️ **부분 구현, 개선 필요**
5. **P&L % 계산 기준**: ⚠️ **부분 일치, 수정 필요**

### 구현 가능성

- ✅ **모든 기능 구현 가능**
- ✅ **기술적 제약 없음**
- ✅ **예상 총 소요 시간**: 약 11시간

### 권장 사항

**즉시 구현 시작 가능**:
- 모든 기능이 구현 가능하며, 기술적 제약 없음
- 순차적으로 구현 진행 가능

---

**검증 일시**: 2025-01-XX  
**검증자**: AI Assistant  
**검증 범위**: 수정된 사용자 의도 기반 전체 기능 검증


