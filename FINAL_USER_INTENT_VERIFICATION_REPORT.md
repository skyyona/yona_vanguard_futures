# 최종 사용자 의도 기반 기능 검증 및 구현 방안 보고서

## 📋 검증 목적

수정된 사용자 의도에 따라 각 기능의 구현 방식을 재정리하고, 구현 가능성을 검증합니다.

---

## 🎯 최종 사용자 의도 정리

### 1. Initial Investment (초기 투자금)

**사용자 의도**:
- 앱 실행 시 계좌 조회로 **자동 설정 후 고정**
- **앱 재시작 시 초기값이 변경되는 것으로 변경**
- 해당 세션 동안 고정 유지

**동작**:
```
1. 앱 실행 → 바이낸스 계좌 조회
2. totalWalletBalance 값을 Initial Investment로 설정
3. 해당 세션 동안 고정 유지
4. 앱 재시작 → 다시 현재 잔고를 Initial Investment로 설정
```

---

### 2. Account total balance (총 계좌 잔액)

**사용자 의도** (수정됨):
- **배분 차감하지 않고**, 바이낸스 API에서 받은 총 잔액을 **그대로 표시**
- 각 엔진의 Designated Funds 배분과 무관하게 전체 자금 표시
- 각 엔진의 실현/미실현 손익은 바이낸스 API가 자동으로 반영
- **단순 표기만 수행** (차감 계산 없음)

**동작**:
```
Account total balance = 바이낸스 API total_wallet_balance (그대로 표시)

- 배분 설정과 무관
- 실현/미실현 손익 자동 반영 (바이낸스 API 제공)
- 실시간 업데이트
```

**계산 공식**:
```
Account total balance = 바이낸스 API totalWalletBalance
(배분 차감 없음, 그대로 표시)
```

---

### 3. Designated Funds 슬라이더

**사용자 의도** (수정됨):
- Account total balance 내에서 비율로 배분하는 것
- **차감이 아닌**, 단순히 비율 설정
- 슬라이더 변경 시 Account total balance 기준으로 퍼센트 계산만 수행

**동작**:
```
1. Account total balance = 10,000 USDT (예시)
2. Alpha 슬라이더 30% 설정 → 10,000 × 30% = 3,000 USDT (단순 계산)
3. Account total balance = 여전히 10,000 USDT 표시 (차감 안 됨)
4. Beta 슬라이더 30% 설정 → 10,000 × 30% = 3,000 USDT (단순 계산)
5. Account total balance = 여전히 10,000 USDT 표시 (차감 안 됨)
```

**계산 공식**:
```
Designated Funds = Account total balance × (슬라이더 퍼센트 / 100)
(차감 없음, 단순 비율 계산)
```

---

### 4. P&L % (헤더 상단의 수익/손실률)

**사용자 의도**:
- **Initial Investment 기준**으로 계산
- **실시간으로 총 P&L**을 표기
- Account total balance는 바이낸스 API가 자동으로 실현/미실현 손익 반영

**계산 공식**:
```
P&L % = ((Account total balance - Initial Investment) / Initial Investment) * 100

Account total balance = 바이낸스 API total_wallet_balance
(바이낸스 API가 실현/미실현 손익 자동 반영)
```

**예시**:
```
Initial Investment = 10,000 USDT
Account total balance = 11,500 USDT (바이낸스 API, 손익 자동 반영)

P&L % = ((11,500 - 10,000) / 10,000) * 100 = +15.0%
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

## 🔍 현재 구현 상태 검증 (재검증)

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
- ✅ **재시작 시 변경**: 이미 의도와 일치
- ✅ **세션 고정**: 플래그로 세션 동안 고정 유지

**평가**: ✅ **사용자 의도와 완전 일치** - 수정 불필요

---

### 2. Account total balance 구현 상태 (재검증)

#### 현재 구현
- **위치**: `backend/core/account_manager.py`
- **동작**: 바이낸스 API에서 받은 `total_wallet_balance`를 그대로 반환

```python
return {
    "total_balance": self.total_wallet_balance,  # 바이낸스 API 값 그대로
}
```

#### 검증 결과
- ✅ **바이낸스 API 값 그대로 표시**: 정상 작동
- ✅ **배분 차감 없음**: 현재 구현이 이미 의도와 일치
- ✅ **실현/미실현 손익 자동 반영**: 바이낸스 API가 자동 반영 (`totalWalletBalance`에 포함)
- ✅ **실시간 업데이트**: 3초마다 업데이트

**평가**: ✅ **사용자 의도와 완전 일치** - 수정 불필요

---

### 3. Designated Funds 슬라이더 구현 상태 (재검증)

#### 현재 구현
- **위치**: `gui/widgets/footer_engines_widget.py`
- **동작**: 하드코딩된 10,000 USDT 기준으로 계산

```python
def _on_funds_slider_changed(self, value):
    total_balance = 10000  # ❌ 하드코딩
    allocated_amount = (value / 100) * total_balance
    self.funds_value_label.setText(f"{value}% (${allocated_amount:.2f})")
    self.designated_funds = allocated_amount
```

#### 검증 결과
- ❌ **실제 Account total balance 연동 없음**: 하드코딩된 값 사용
- ✅ **차감 로직 없음**: 현재 구현이 이미 의도와 일치 (차감 안 함)
- ⚠️ **문제점**: 
  - 실제 Account total balance를 참조해야 함
  - Account total balance 업데이트 시 슬라이더 기준 금액도 업데이트 필요

**평가**: ⚠️ **부분 일치** - 실제 Account total balance 연동만 필요

---

### 4. P&L % (헤더) 구현 상태 (재검증)

#### 현재 구현
- **위치**: `backend/core/account_manager.py`

```python
pnl_percent = ((self.total_wallet_balance - self.initial_capital) / self.initial_capital) * 100.0
```

#### 검증 결과
- ✅ **계산 공식**: 정확함
- ✅ **계산 기준**: 
  - `total_wallet_balance` (바이낸스 API 값, 실현/미실현 손익 자동 반영)
  - `initial_capital` (초기 투자금)
- ✅ **실시간 업데이트**: 3초마다 업데이트

**평가**: ✅ **사용자 의도와 완전 일치** - 수정 불필요

---

### 5. 각 엔진의 Total Slot Gain/Loss 및 P&L % 구현 상태 (재검증)

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
  - 실현/미실현 손익 구분하여 추적 필요
  - 각 엔진의 손익을 독립적으로 추적 필요

**평가**: ⚠️ **부분 일치** - Designated Funds 기준 계산 로직 필요

---

## 🚨 발견된 문제점 및 구현 필요 사항 (재정리)

### 문제점 1: Designated Funds 실제 Account total balance 연동 부재 ⚠️ **중요**

**필요 기능**:
- Account total balance를 엔진 위젯으로 전달
- 슬라이더 변경 시 실제 Account total balance 기준으로 계산
- Account total balance 업데이트 시 슬라이더 표시 금액도 업데이트

**구현 필요 위치**:
- `gui/main.py`: Account total balance 전달
- `gui/widgets/footer_engines_widget.py`: 실제 잔고 기준 계산

**구현 난이도**: ⭐⭐ (쉬움)  
**예상 소요 시간**: 1시간

---

### 문제점 2: 각 엔진의 손익 추적 메커니즘 부재 ⚠️ **중요**

**필요 기능**:
- 각 엔진의 실현 손익 추적 (거래 완료 시)
- 각 엔진의 미실현 손익 추적 (현재 포지션)
- Designated Funds 기준으로 P&L % 계산
- 바이낸스 API에서 각 심볼별 포지션 정보 조회

**구현 필요 위치**:
- `backend/core/engine_manager.py`: 각 엔진의 손익 집계
- `backend/core/strategies/base_strategy.py`: 손익 계산 로직
- `backend/api_client/binance_client.py`: 포지션 정보 조회 (필요 시)

**구현 난이도**: ⭐⭐⭐ (중간)  
**예상 소요 시간**: 3시간

---

### 문제점 3: 실현/미실현 손익 구분 부재 ⚠️ **중요**

**필요 기능**:
- 거래 완료(청산) 시 실현 손익 기록
- 현재 포지션의 미실현 손익 계산
- 구분하여 추적 및 표시

**구현 필요 위치**:
- `backend/core/strategies/base_strategy.py`: 손익 구분 로직
- `backend/core/engine_manager.py`: 손익 집계

**구현 난이도**: ⭐⭐⭐ (중간)  
**예상 소요 시간**: 2시간

---

## 📊 구현 가능성 분석 (재정리)

### ✅ 구현 가능한 기능

| 기능 | 구현 가능성 | 난이도 | 예상 소요 시간 | 우선순위 |
|------|-----------|--------|---------------|---------|
| **Designated Funds 실제 잔고 연동** | ✅ 가능 | ⭐⭐ | 1시간 | **높음** |
| **각 엔진 손익 추적** | ✅ 가능 | ⭐⭐⭐ | 3시간 | **높음** |
| **실현/미실현 손익 구분** | ✅ 가능 | ⭐⭐⭐ | 2시간 | **높음** |
| **엔진별 P&L % 계산** | ✅ 가능 | ⭐⭐ | 1시간 | **높음** |

**총 예상 소요 시간**: 약 7시간

---

## 🔧 구현 방안 요약 (재정리)

### 1. Initial Investment
- ✅ **현재 구현 유지**: 추가 수정 불필요

### 2. Account total balance
- ✅ **현재 구현 유지**: 바이낸스 API 값 그대로 표시 (추가 수정 불필요)
- ✅ **배분 차감 로직 불필요**: 사용자 의도에 따라 차감하지 않음

### 3. Designated Funds 슬라이더
- **메인 윈도우**: Account total balance를 엔진 위젯으로 전달
- **엔진 위젯**: 실제 Account total balance 기준으로 슬라이더 계산
- **Account total balance 업데이트 시**: 슬라이더 표시 금액 자동 업데이트

### 4. P&L % (헤더)
- ✅ **현재 구현 유지**: 추가 수정 불필요

### 5. 각 엔진 손익 추적
- **BaseStrategy**: 손익 계산 메서드 추가
- **EngineManager**: 각 엔진의 손익 집계
- **실현/미실현 구분**: 포지션 상태로 구분
- **Designated Funds 기준**: P&L % 계산

---

## ✅ 종합 평가 (재정리)

### 사용자 의도와의 일치 여부

| 기능 | 사용자 의도 | 현재 구현 | 일치 여부 | 구현 필요성 |
|------|------------|----------|----------|------------|
| **Initial Investment** | 재시작 시 변경 | ✅ 이미 구현됨 | ✅ 완전 일치 | 불필요 |
| **Account total balance** | 바이낸스 API 값 그대로 표시 | ✅ 바이낸스 API 값 그대로 | ✅ 완전 일치 | 불필요 |
| **Account total balance 배분 차감** | 차감하지 않음 | ✅ 차감 안 함 | ✅ 완전 일치 | 불필요 |
| **Designated Funds 실제 잔고 연동** | 실제 Account total balance 기준 | 하드코딩 | ❌ 불일치 | **필요** |
| **P&L % (헤더)** | Initial Investment 기준 | ✅ 이미 구현됨 | ✅ 완전 일치 | 불필요 |
| **각 엔진 손익 추적** | Designated Funds 기준 | 기준 불명확 | ⚠️ 부분 일치 | **필요** |
| **실현/미실현 손익 구분** | 구분하여 표시 | 구분 안 됨 | ❌ 불일치 | **필요** |

---

## 📋 구현 필요 항목 요약 (재정리)

### 우선순위 1 (필수)

1. ✅ **Designated Funds 실제 Account total balance 연동**
   - 메인 윈도우에서 Account total balance 전달
   - 엔진 위젯에서 실제 잔고 기준 계산
   - 예상 소요 시간: 1시간

2. ✅ **각 엔진 손익 추적 메커니즘 구현**
   - 각 엔진의 실현/미실현 손익 추적
   - Designated Funds 기준으로 P&L % 계산
   - 예상 소요 시간: 3시간

3. ✅ **실현/미실현 손익 구분**
   - 거래 완료 시 실현 손익 기록
   - 현재 포지션 미실현 손익 계산
   - 예상 소요 시간: 2시간

4. ✅ **엔진별 P&L % 계산 (Designated Funds 기준)**
   - Total Slot Gain/Loss = 실현 손익 + 미실현 손익
   - P&L % = (Total Slot Gain/Loss / Designated Funds) * 100
   - 예상 소요 시간: 1시간

---

## ✅ 결론 (재정리)

### 현재 상태 요약

1. **Initial Investment**: ✅ **사용자 의도와 완전 일치** (추가 수정 불필요)
2. **Account total balance**: ✅ **사용자 의도와 완전 일치** (바이낸스 API 값 그대로, 추가 수정 불필요)
3. **Account total balance 배분 차감**: ✅ **사용자 의도와 완전 일치** (차감하지 않음, 추가 수정 불필요)
4. **P&L % (헤더)**: ✅ **사용자 의도와 완전 일치** (추가 수정 불필요)
5. **Designated Funds 실제 잔고 연동**: ❌ **구현 필요**
6. **각 엔진 손익 추적**: ⚠️ **부분 구현, 개선 필요**

### 주요 발견 사항

**좋은 소식**:
- ✅ 대부분의 핵심 기능이 이미 사용자 의도와 일치
- ✅ Account total balance는 배분 차감 불필요 (구현이 간단해짐)
- ✅ P&L % 계산 로직도 이미 정확히 구현됨

**구현 필요**:
- ⚠️ Designated Funds 실제 잔고 연동 (1시간)
- ⚠️ 각 엔진 손익 추적 (3시간)
- ⚠️ 실현/미실현 손익 구분 (2시간)
- ⚠️ 엔진별 P&L % 계산 (1시간)

### 구현 가능성

- ✅ **모든 기능 구현 가능**
- ✅ **기술적 제약 없음**
- ✅ **예상 총 소요 시간**: 약 7시간 (이전 11시간에서 대폭 감소)

### 권장 사항

**즉시 구현 시작 가능**:
- 대부분의 기능이 이미 구현되어 있어 구현 범위가 크게 축소됨
- 배분 차감 로직이 불필요하여 구현이 간단해짐
- 순차적으로 구현 진행 가능

---

## 📊 구현 범위 비교

### 이전 의도 (배분 차감 필요)
- Account total balance 배분 차감 로직: 2시간
- 배분 자금 추적 메커니즘: 2시간
- **총 예상 시간**: 11시간

### 현재 의도 (배분 차감 불필요)
- ~~Account total balance 배분 차감 로직~~: 불필요 ✅
- ~~배분 자금 추적 메커니즘~~: 불필요 ✅
- Designated Funds 실제 잔고 연동: 1시간
- 각 엔진 손익 추적: 3시간
- 실현/미실현 손익 구분: 2시간
- 엔진별 P&L % 계산: 1시간
- **총 예상 시간**: 7시간 (4시간 절감)

---

**검증 일시**: 2025-01-XX  
**검증자**: AI Assistant  
**검증 범위**: 최종 사용자 의도 기반 전체 기능 검증


