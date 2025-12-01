# 수정된 사용자 의도 기반 기능 검증 및 구현 방안 보고서 (최종)

## 📋 검증 목적

수정된 사용자 의도에 따라 각 기능의 구현 방식을 재정리하고, 구현 가능성을 검증합니다.

---

## 🎯 최종 수정된 사용자 의도 정리

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

### 2. Account total balance (총 계좌 잔액) - 최종 수정

**사용자 의도** (최종 수정):
- **Designated Funds 슬라이더로 배분 시 차감 표기**
- 각 엔진의 'Designated Funds' 슬라이더로 Account total balance 총 자금을 배분
- 배분된 금액만큼 Account total balance에서 **차감되어 표기**
- **각 엔진이 거래를 마치고 '거래 종료' 상황이 되면**, 해당 수익/손실이 Account total balance에 **추가**되는 것으로 구현

**동작 흐름**:

**1단계: 초기 상태**
```
Initial Investment = 10,000 USDT
Account total balance = 10,000 USDT (Initial Investment와 동일)
```

**2단계: 자금 배분**
```
Alpha 슬라이더 30% 설정 → 10,000 × 30% = 3,000 USDT 배분
Account total balance = 10,000 - 3,000 = 7,000 USDT 표시

Beta 슬라이더 30% 설정 → 7,000 × 30% = 2,100 USDT 배분
Account total balance = 7,000 - 2,100 = 4,900 USDT 표시

Gamma 슬라이더 30% 설정 → 4,900 × 30% = 1,470 USDT 배분
Account total balance = 4,900 - 1,470 = 3,430 USDT 표시
```

**3단계: 거래 진행 중**
```
Alpha 엔진: 3,000 USDT로 거래 진행 중 (미실현 손익 +500 USDT)
Beta 엔진: 2,100 USDT로 거래 진행 중 (미실현 손익 -200 USDT)
Gamma 엔진: 1,470 USDT로 거래 진행 중 (미실현 손익 +300 USDT)

Account total balance = 3,430 USDT 표시 (배분 차감 후 잔액, 거래 중 손익 미반영)
```

**4단계: 거래 종료 시 수익/손실 반영**
```
Alpha 엔진 거래 종료: +500 USDT 수익 실현
Account total balance = 3,430 + 500 = 3,930 USDT 표시

Beta 엔진 거래 종료: -200 USDT 손실 실현
Account total balance = 3,930 - 200 = 3,730 USDT 표시

Gamma 엔진 거래 종료: +300 USDT 수익 실현
Account total balance = 3,730 + 300 = 4,030 USDT 표시
```

**계산 공식**:
```
Account total balance = 
  Initial Investment 
  - (Alpha 배분 + Beta 배분 + Gamma 배분)
  + (실현된 수익/손실 합계)

배분 시: 차감 표기
거래 종료 시: 수익/손실 추가
```

---

### 3. Designated Funds 슬라이더

**사용자 의도** (최종 수정):
- Account total balance 총 자금을 배분
- 배분 시 Account total balance에서 **차감되어 표기**
- 슬라이더 변경 시 **현재 Account total balance (배분 차감 후 잔액)** 기준으로 계산

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

---

### 4. P&L % (헤더 상단의 수익/손실률)

**사용자 의도**:
- **Initial Investment 기준**으로 계산
- **실시간으로 총 P&L**을 표기
- Account total balance는 배분 차감 후 잔액 + 실현된 수익/손실

**계산 공식**:
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
실현 손익: Alpha +500, Beta -200, Gamma +300 = +600 USDT

Account total balance = 10,000 - 6,570 + 600 = 4,030 USDT
P&L % = ((4,030 - 10,000) / 10,000) * 100 = -59.7%
```

---

### 5. 각 엔진의 Total Slot Gain/Loss 및 P&L %

**사용자 의도**:
- 각 엔진의 'Total Slot Gain/Loss'와 'P&L %'는 **해당 엔진의 투입 자금(Designated Funds) 기준**으로 표기
- 해당 엔진만의 수익/손실을 표시
- **거래 진행 중**: 미실현 손익 표시
- **거래 종료 시**: 실현 손익 표시

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
```

---

## 🔍 현재 구현 상태 검증 (최종 재검증)

### 1. Initial Investment 구현 상태

#### 현재 구현
- **위치**: `backend/core/account_manager.py`
- **동작**: 첫 계좌 조회 시 `total_wallet_balance`를 `initial_capital`로 설정

#### 검증 결과
- ✅ **자동 설정**: 정상 작동
- ✅ **재시작 시 변경**: 이미 의도와 일치
- ✅ **세션 고정**: 플래그로 세션 동안 고정 유지

**평가**: ✅ **사용자 의도와 완전 일치** - 수정 불필요

---

### 2. Account total balance 구현 상태 (최종 재검증)

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
- ❌ **거래 종료 시 수익/손실 추가 로직 없음**: 실현 손익 반영 안 됨
- ❌ **문제점**: 
  - 배분 자금 추적 메커니즘 필요
  - 실현 손익 추적 메커니즘 필요
  - Account total balance = Initial Investment - 배분 합계 + 실현 손익 합계

**평가**: ❌ **사용자 의도와 불일치** - 배분 차감 및 실현 손익 추가 로직 필요

---

### 3. Designated Funds 슬라이더 구현 상태 (최종 재검증)

#### 현재 구현
- **위치**: `gui/widgets/footer_engines_widget.py`
- **동작**: 하드코딩된 10,000 USDT 기준으로 계산

```python
def _on_funds_slider_changed(self, value):
    total_balance = 10000  # ❌ 하드코딩
    allocated_amount = (value / 100) * total_balance
    # 차감 로직 없음
```

#### 검증 결과
- ❌ **실제 Account total balance 연동 없음**: 하드코딩된 값 사용
- ❌ **차감 로직 없음**: 배분 시 Account total balance에서 차감 안 됨
- ❌ **문제점**: 
  - 실제 Account total balance를 참조해야 함
  - 배분 시 차감 계산 필요
  - Account total balance 업데이트 필요

**평가**: ❌ **사용자 의도와 불일치** - 실제 잔고 연동 및 차감 로직 필요

---

### 4. P&L % (헤더) 구현 상태 (최종 재검증)

#### 현재 구현
- **위치**: `backend/core/account_manager.py`

```python
pnl_percent = ((self.total_wallet_balance - self.initial_capital) / self.initial_capital) * 100.0
```

#### 검증 결과
- ⚠️ **계산 공식**: 부분 일치
- ❌ **계산 기준**: 
  - 현재: `total_wallet_balance` (바이낸스 API 값)
  - 사용자 의도: 배분 차감 후 잔액 + 실현 손익
- ❌ **문제점**: 
  - Account total balance 계산 로직 수정 필요
  - 배분 차감 및 실현 손익 반영 필요

**평가**: ❌ **사용자 의도와 불일치** - Account total balance 계산 로직 수정 필요

---

### 5. 각 엔진의 Total Slot Gain/Loss 및 P&L % 구현 상태 (최종 재검증)

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
- ❌ **거래 종료 시 Account total balance 추가**: 로직 없음
- ⚠️ **문제점**: 
  - 백엔드에서 Designated Funds 기준으로 계산해야 함
  - 실현/미실현 손익 구분하여 추적 필요
  - 거래 종료 시 실현 손익을 Account total balance에 추가하는 로직 필요

**평가**: ❌ **사용자 의도와 불일치** - Designated Funds 기준 계산 및 거래 종료 시 추가 로직 필요

---

## 🚨 발견된 문제점 및 구현 필요 사항 (최종 정리)

### 문제점 1: Account total balance 배분 차감 로직 부재 ⚠️ **높음**

**필요 기능**:
- 각 엔진의 Designated Funds 배분 추적
- 배분 합계 계산
- Account total balance = Initial Investment - 배분 합계
- 배분 변경 시 Account total balance 즉시 업데이트

**구현 필요 위치**:
- `backend/core/account_manager.py` 또는 새로운 `FundsAllocationManager` 클래스

**구현 난이도**: ⭐⭐⭐ (중간)  
**예상 소요 시간**: 2시간

---

### 문제점 2: Account total balance 거래 종료 시 수익/손실 추가 로직 부재 ⚠️ **높음**

**필요 기능**:
- 각 엔진의 거래 종료 시 실현 손익 추적
- 실현 손익을 Account total balance에 추가
- Account total balance = Initial Investment - 배분 합계 + 실현 손익 합계

**구현 필요 위치**:
- `backend/core/account_manager.py`: Account total balance 계산 로직
- `backend/core/engine_manager.py`: 거래 종료 시 실현 손익 전달

**구현 난이도**: ⭐⭐⭐ (중간)  
**예상 소요 시간**: 2시간

---

### 문제점 3: Designated Funds 실제 Account total balance 연동 및 차감 로직 부재 ⚠️ **높음**

**필요 기능**:
- Account total balance를 엔진 위젯으로 전달
- 슬라이더 변경 시 실제 Account total balance(배분 차감 후) 기준으로 계산
- 배분 설정 시 Account total balance에서 차감
- 배분 변경 시 Account total balance 즉시 업데이트

**구현 필요 위치**:
- `gui/main.py`: Account total balance 전달 및 배분 집계
- `gui/widgets/footer_engines_widget.py`: 실제 잔고 기준 계산 및 차감

**구현 난이도**: ⭐⭐⭐ (중간)  
**예상 소요 시간**: 2시간

---

### 문제점 4: 각 엔진의 손익 추적 메커니즘 부재 ⚠️ **높음**

**필요 기능**:
- 각 엔진의 실현 손익 추적 (거래 완료 시)
- 각 엔진의 미실현 손익 추적 (현재 포지션)
- Designated Funds 기준으로 P&L % 계산
- 거래 종료 시 실현 손익을 Account total balance에 추가

**구현 필요 위치**:
- `backend/core/engine_manager.py`: 각 엔진의 손익 집계
- `backend/core/strategies/base_strategy.py`: 손익 계산 로직
- `backend/api_client/binance_client.py`: 포지션 정보 조회 (필요 시)

**구현 난이도**: ⭐⭐⭐ (중간)  
**예상 소요 시간**: 3시간

---

### 문제점 5: 실현/미실현 손익 구분 부재 ⚠️ **높음**

**필요 기능**:
- 거래 완료(청산) 시 실현 손익 기록
- 현재 포지션의 미실현 손익 계산
- 구분하여 추적 및 표시
- 실현 손익만 Account total balance에 반영

**구현 필요 위치**:
- `backend/core/strategies/base_strategy.py`: 손익 구분 로직
- `backend/core/engine_manager.py`: 손익 집계 및 전달

**구현 난이도**: ⭐⭐⭐ (중간)  
**예상 소요 시간**: 2시간

---

### 문제점 6: P&L % 계산 기준 수정 필요 ⚠️ **높음**

**필요 기능**:
- Account total balance = Initial Investment - 배분 합계 + 실현 손익 합계
- P&L % = ((Account total balance - Initial Investment) / Initial Investment) * 100

**구현 필요 위치**:
- `backend/core/account_manager.py`: Account total balance 계산 로직 수정
- `backend/core/account_manager.py`: P&L % 계산 로직 수정

**구현 난이도**: ⭐⭐ (쉬움)  
**예상 소요 시간**: 1시간

---

## 📊 구현 가능성 분석 (최종 정리)

### ✅ 구현 가능한 기능

| 기능 | 구현 가능성 | 난이도 | 예상 소요 시간 | 우선순위 |
|------|-----------|--------|---------------|---------|
| **Account total balance 배분 차감** | ✅ 가능 | ⭐⭐⭐ | 2시간 | **높음** |
| **거래 종료 시 수익/손실 추가** | ✅ 가능 | ⭐⭐⭐ | 2시간 | **높음** |
| **Designated Funds 실제 잔고 연동 및 차감** | ✅ 가능 | ⭐⭐⭐ | 2시간 | **높음** |
| **각 엔진 손익 추적** | ✅ 가능 | ⭐⭐⭐ | 3시간 | **높음** |
| **실현/미실현 손익 구분** | ✅ 가능 | ⭐⭐⭐ | 2시간 | **높음** |
| **P&L % 계산 기준 수정** | ✅ 가능 | ⭐⭐ | 1시간 | **높음** |

**총 예상 소요 시간**: 약 12시간

---

## 🔧 구현 방안 요약 (최종 정리)

### 1. Initial Investment
- ✅ **현재 구현 유지**: 추가 수정 불필요

### 2. Account total balance 배분 차감 및 거래 종료 시 추가
- **새로운 클래스 또는 AccountManager 확장**: 배분 자금 추적, 차감 계산
- **계산 로직**:
  ```
  Account total balance = 
    Initial Investment 
    - (Alpha 배분 + Beta 배분 + Gamma 배분)
    + (실현된 수익/손실 합계)
  ```
- **위치**: `backend/core/account_manager.py` 또는 `backend/core/funds_allocation_manager.py` (신규)

### 3. Designated Funds 슬라이더 실제 잔고 연동 및 차감
- **메인 윈도우**: Account total balance(배분 차감 후) 전달 및 배분 집계
- **엔진 위젯**: 실제 잔고 기준으로 슬라이더 계산, 배분 시 차감
- **배분 변경 시**: Account total balance 즉시 업데이트

### 4. 각 엔진 손익 추적 및 거래 종료 시 추가
- **BaseStrategy**: 손익 계산 메서드 추가
- **EngineManager**: 각 엔진의 손익 집계 및 거래 종료 감지
- **거래 종료 시**: 실현 손익을 Account total balance에 추가

### 5. 실현/미실현 손익 구분
- **BaseStrategy**: 포지션 상태로 손익 구분
- **거래 종료 시**: 실현 손익만 Account total balance에 반영
- **거래 진행 중**: 미실현 손익은 Account total balance에 반영 안 함

### 6. P&L % 계산 기준 수정
- **Account total balance 계산**: 배분 차감 + 실현 손익 반영
- **P&L % 계산**: 수정된 Account total balance 기준

---

## ✅ 종합 평가 (최종 정리)

### 사용자 의도와의 일치 여부

| 기능 | 사용자 의도 | 현재 구현 | 일치 여부 | 구현 필요성 |
|------|------------|----------|----------|------------|
| **Initial Investment** | 재시작 시 변경 | ✅ 이미 구현됨 | ✅ 완전 일치 | 불필요 |
| **Account total balance 배분 차감** | 배분 시 차감 표기 | 차감 로직 없음 | ❌ 불일치 | **필요** |
| **Account total balance 거래 종료 시 추가** | 거래 종료 시 수익/손실 추가 | 추가 로직 없음 | ❌ 불일치 | **필요** |
| **Designated Funds 실제 잔고 연동** | 실제 Account total balance 기준 | 하드코딩 | ❌ 불일치 | **필요** |
| **Designated Funds 차감 로직** | 배분 시 차감 | 차감 로직 없음 | ❌ 불일치 | **필요** |
| **P&L % 계산 기준** | 배분 차감 후 + 실현 손익 기준 | API 값 기준 | ❌ 불일치 | **필요** |
| **각 엔진 손익 추적** | Designated Funds 기준 | 기준 불명확 | ❌ 불일치 | **필요** |
| **실현/미실현 손익 구분** | 구분하여 표시 및 처리 | 구분 안 됨 | ❌ 불일치 | **필요** |

---

## 📋 구현 필요 항목 요약 (최종 정리)

### 우선순위 1 (필수)

1. ✅ **Account total balance 배분 차감 로직 구현**
   - 배분 자금 추적
   - Account total balance = Initial Investment - 배분 합계
   - 예상 소요 시간: 2시간

2. ✅ **Account total balance 거래 종료 시 수익/손실 추가 로직 구현**
   - 실현 손익 추적
   - Account total balance = Initial Investment - 배분 합계 + 실현 손익 합계
   - 예상 소요 시간: 2시간

3. ✅ **Designated Funds 실제 잔고 연동 및 차감 로직 구현**
   - 실제 Account total balance 연동
   - 배분 시 차감
   - 예상 소요 시간: 2시간

4. ✅ **각 엔진 손익 추적 메커니즘 구현**
   - Designated Funds 기준 계산
   - 거래 종료 시 실현 손익 전달
   - 예상 소요 시간: 3시간

5. ✅ **실현/미실현 손익 구분**
   - 구분하여 추적
   - 실현 손익만 Account total balance에 반영
   - 예상 소요 시간: 2시간

6. ✅ **P&L % 계산 기준 수정**
   - Account total balance 계산 로직 수정
   - P&L % 계산 로직 수정
   - 예상 소요 시간: 1시간

---

## ✅ 결론 (최종 정리)

### 현재 상태 요약

1. **Initial Investment**: ✅ **사용자 의도와 완전 일치** (추가 수정 불필요)
2. **Account total balance 배분 차감**: ❌ **구현 필요** (차감 로직 필요)
3. **Account total balance 거래 종료 시 추가**: ❌ **구현 필요** (수익/손실 추가 로직 필요)
4. **Designated Funds 실제 잔고 연동**: ❌ **구현 필요** (연동 및 차감 로직 필요)
5. **P&L % 계산 기준**: ❌ **수정 필요** (배분 차감 + 실현 손익 반영)
6. **각 엔진 손익 추적**: ❌ **구현 필요** (Designated Funds 기준)

### 주요 발견 사항

**구현 필요 사항**:
- ✅ 배분 차감 로직 (2시간)
- ✅ 거래 종료 시 수익/손실 추가 로직 (2시간)
- ✅ Designated Funds 실제 잔고 연동 및 차감 (2시간)
- ✅ 각 엔진 손익 추적 (3시간)
- ✅ 실현/미실현 손익 구분 (2시간)
- ✅ P&L % 계산 기준 수정 (1시간)

### 구현 가능성

- ✅ **모든 기능 구현 가능**
- ✅ **기술적 제약 없음**
- ✅ **예상 총 소요 시간**: 약 12시간

### 주요 구현 포인트

1. **배분 차감 로직**:
   - Initial Investment - 배분 합계
   - 배분 변경 시 즉시 업데이트

2. **거래 종료 시 수익/손실 추가**:
   - 실현 손익만 Account total balance에 추가
   - 미실현 손익은 반영하지 않음

3. **Account total balance 계산**:
   ```
   Account total balance = 
     Initial Investment 
     - (배분 합계)
     + (실현 손익 합계)
   ```

4. **P&L % 계산**:
   ```
   P&L % = ((Account total balance - Initial Investment) / Initial Investment) * 100
   ```

---

## 📊 구현 범위 비교

### 이전 의도 (배분 차감 불필요)
- ~~Account total balance 배분 차감 로직~~: 불필요
- 총 예상 시간: 7시간

### 현재 의도 (배분 차감 필요 + 거래 종료 시 추가)
- Account total balance 배분 차감 로직: 2시간
- Account total balance 거래 종료 시 수익/손실 추가: 2시간
- Designated Funds 실제 잔고 연동 및 차감: 2시간
- 각 엔진 손익 추적: 3시간
- 실현/미실현 손익 구분: 2시간
- P&L % 계산 기준 수정: 1시간
- **총 예상 시간**: 12시간

---

## 🔄 구현 순서 제안

### Phase 1: 기본 구조 (3시간)
1. 배분 자금 추적 메커니즘 구현
2. Account total balance 계산 로직 수정

### Phase 2: GUI 연동 (2시간)
3. Designated Funds 실제 잔고 연동
4. 배분 차감 로직 구현

### Phase 3: 손익 추적 (5시간)
5. 각 엔진 손익 추적 메커니즘
6. 실현/미실현 손익 구분
7. 거래 종료 시 실현 손익 추가

### Phase 4: 최종 통합 (2시간)
8. P&L % 계산 기준 수정
9. 전체 통합 테스트

---

**검증 일시**: 2025-01-XX  
**검증자**: AI Assistant  
**검증 범위**: 최종 수정된 사용자 의도 기반 전체 기능 검증


