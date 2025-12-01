# P&L % 계산 검증 보고서

## 📋 검증 목적

사용자가 제시한 계산 예시를 검증하여 모순점을 확인합니다.

---

## 🔍 제시된 계산 검증

### 제시된 계산

```
Initial Investment = 10,000 USDT

1. Alpha 30% 배분: 3,000 USDT
   Account total balance = 10,000 - 3,000 = 7,000 USDT
   P&L % = ((7,000 - 10,000) / 10,000) * 100 = -30.0%

2. Beta 30% 배분: 2,100 USDT (7,000 × 30%)
   Account total balance = 7,000 - 2,100 = 4,900 USDT
   P&L % = ((4,900 - 10,000) / 10,000) * 100 = -51.0%

3. Gamma 30% 배분: 1,470 USDT (4,900 × 30%)
   Account total balance = 4,900 - 1,470 = 3,430 USDT
   P&L % = ((3,430 - 10,000) / 10,000) * 100 = -65.7%

4. Alpha 거래 종료: +500 USDT 수익 실현
   Account total balance = 3,430 + 500 = 3,930 USDT
   P&L % = ((3,930 - 10,000) / 10,000) * 100 = -60.7%

5. Beta 거래 종료: -200 USDT 손실 실현
   Account total balance = 3,930 - 200 = 3,730 USDT
   P&L % = ((3,730 - 10,000) / 10,000) * 100 = -62.7%

6. Gamma 거래 종료: +300 USDT 수익 실현
   Account total balance = 3,730 + 300 = 4,030 USDT
   P&L % = ((4,030 - 10,000) / 10,000) * 100 = -59.7%
```

---

## 🚨 발견된 모순점

### 문제점 1: 배분만 했을 때 손익률 발생 (가장 큰 문제) ❌

**발견된 문제**:
- 배분만 했을 뿐인데 P&L %가 -30.0%, -51.0%, -65.7%로 나타남
- 배분은 단순히 자금을 할당하는 것이지 손익이 발생한 것이 아님
- 배분만 하고 거래를 시작하지 않았으면 P&L %는 0%여야 함

**예시**:
```
Initial Investment = 10,000 USDT
Alpha 30% 배분: 3,000 USDT → Account total balance = 7,000 USDT
P&L % = -30.0% ❌ (잘못됨)
```

**올바른 계산**:
```
배분만 했을 때:
- 배분된 자금: 3,000 USDT (거래 시작 전, 손익 없음)
- 미배분 잔액: 7,000 USDT (손익 없음)
- 실현 손익: 0 USDT
- P&L % = 0% ✅ (올바름)
```

---

### 문제점 2: 거래 종료 시 손익률 계산 부정확 ❌

**발견된 문제**:
- Alpha 거래 종료 시 +500 USDT 수익 실현
- 하지만 P&L %는 -60.7%로 계산됨
- 실제로는 수익이 발생했는데 전체적으로는 손실로 표시됨

**검증**:
```
Alpha 거래 종료: +500 USDT 수익 실현
Account total balance = 3,430 + 500 = 3,930 USDT

현재 계산:
P&L % = ((3,930 - 10,000) / 10,000) * 100 = -60.7%

문제점:
- 초기 투자: 10,000 USDT
- 현재 잔액: 3,930 USDT (배분 차감 후 + 실현 수익)
- 손실: -6,070 USDT (-60.7%)
- 하지만 Alpha에서 +500 USDT 수익이 발생했는데도 전체적으로는 큰 손실로 표시됨
```

**올바른 계산**:
```
배분: Alpha 3,000 + Beta 2,100 + Gamma 1,470 = 6,570 USDT
미배분 잔액: 3,430 USDT

Alpha 거래 종료: +500 USDT 수익 실현
- Alpha 배분 3,000 USDT 중에서 +500 USDT 수익
- Alpha의 실제 가치: 3,000 + 500 = 3,500 USDT
- 전체 가치: 미배분 3,430 + Alpha 3,500 + Beta 2,100 + Gamma 1,470 = 10,500 USDT
- P&L % = ((10,500 - 10,000) / 10,000) * 100 = +5.0% ✅
```

---

### 문제점 3: 배분 차감 방식의 논리적 문제 ❌

**발견된 문제**:
- Account total balance에서 배분 금액을 차감하면, 배분된 자금은 사라진 것처럼 표시됨
- 하지만 실제로는 배분된 자금도 여전히 존재하고, 거래를 통해 수익/손실이 발생할 수 있음
- 배분 차감은 단순히 "사용 가능한 잔액"을 표시하는 것이지, 전체 자산 가치를 표시하는 것이 아님

**현재 방식의 문제**:
```
Initial Investment = 10,000 USDT
Alpha 30% 배분: 3,000 USDT
Account total balance = 10,000 - 3,000 = 7,000 USDT

문제:
- 실제로는 10,000 USDT가 모두 존재함
- Alpha에 3,000 USDT가 배분되어 거래 중일 수 있음
- Account total balance = 7,000 USDT는 "미배분 잔액"만 표시하는 것
- 전체 자산 가치는 여전히 10,000 USDT (거래 결과에 따라 변동)
```

---

## ✅ 올바른 계산 방식 제안

### 방식 1: 배분 금액을 별도 추적 (권장)

**개념**:
- Account total balance는 전체 자산 가치를 표시
- 배분은 단순히 할당만 하고 차감하지 않음
- 거래 종료 시 실현 손익만 Account total balance에 반영

**계산 공식**:
```
Account total balance = 
  Initial Investment 
  + (실현된 수익/손실 합계)

P&L % = ((Account total balance - Initial Investment) / Initial Investment) * 100
```

**예시**:
```
Initial Investment = 10,000 USDT

1. Alpha 30% 배분: 3,000 USDT
   Account total balance = 10,000 USDT (변경 없음, 배분만 표시)
   P&L % = ((10,000 - 10,000) / 10,000) * 100 = 0.0% ✅

2. Beta 30% 배분: 2,100 USDT
   Account total balance = 10,000 USDT (변경 없음)
   P&L % = 0.0% ✅

3. Gamma 30% 배분: 1,470 USDT
   Account total balance = 10,000 USDT (변경 없음)
   P&L % = 0.0% ✅

4. Alpha 거래 종료: +500 USDT 수익 실현
   Account total balance = 10,000 + 500 = 10,500 USDT
   P&L % = ((10,500 - 10,000) / 10,000) * 100 = +5.0% ✅

5. Beta 거래 종료: -200 USDT 손실 실현
   Account total balance = 10,500 - 200 = 10,300 USDT
   P&L % = ((10,300 - 10,000) / 10,000) * 100 = +3.0% ✅

6. Gamma 거래 종료: +300 USDT 수익 실현
   Account total balance = 10,300 + 300 = 10,600 USDT
   P&L % = ((10,600 - 10,000) / 10,000) * 100 = +6.0% ✅
```

**장점**:
- 배분만 했을 때 P&L %가 0%로 올바르게 표시됨
- 거래 종료 시 실제 수익/손실이 정확히 반영됨
- 논리적으로 명확함

**단점**:
- 사용자 의도와 다를 수 있음 (배분 차감 표시 안 함)

---

### 방식 2: 배분 차감하되, P&L %는 실현 손익만 반영 (사용자 의도 반영)

**개념**:
- Account total balance는 배분 차감 후 잔액 표시 (사용자 의도)
- P&L %는 배분 차감을 손익으로 간주하지 않고, 실현 손익만 반영

**계산 공식**:
```
Account total balance = 
  Initial Investment 
  - (배분 합계)
  + (실현된 수익/손실 합계)

P&L % = (실현된 수익/손실 합계 / Initial Investment) * 100
```

**예시**:
```
Initial Investment = 10,000 USDT

1. Alpha 30% 배분: 3,000 USDT
   Account total balance = 10,000 - 3,000 = 7,000 USDT
   실현 손익 = 0 USDT
   P&L % = (0 / 10,000) * 100 = 0.0% ✅

2. Beta 30% 배분: 2,100 USDT
   Account total balance = 7,000 - 2,100 = 4,900 USDT
   실현 손익 = 0 USDT
   P&L % = 0.0% ✅

3. Gamma 30% 배분: 1,470 USDT
   Account total balance = 4,900 - 1,470 = 3,430 USDT
   실현 손익 = 0 USDT
   P&L % = 0.0% ✅

4. Alpha 거래 종료: +500 USDT 수익 실현
   Account total balance = 3,430 + 500 = 3,930 USDT
   실현 손익 = +500 USDT
   P&L % = (500 / 10,000) * 100 = +5.0% ✅

5. Beta 거래 종료: -200 USDT 손실 실현
   Account total balance = 3,930 - 200 = 3,730 USDT
   실현 손익 = +500 - 200 = +300 USDT
   P&L % = (300 / 10,000) * 100 = +3.0% ✅

6. Gamma 거래 종료: +300 USDT 수익 실현
   Account total balance = 3,730 + 300 = 4,030 USDT
   실현 손익 = +500 - 200 + 300 = +600 USDT
   P&L % = (600 / 10,000) * 100 = +6.0% ✅
```

**장점**:
- 사용자 의도 반영 (배분 차감 표시)
- 배분만 했을 때 P&L %가 0%로 올바르게 표시됨
- 거래 종료 시 실제 수익/손실 정확히 반영

**단점**:
- Account total balance가 "미배분 잔액 + 실현 손익"만 표시
- 배분된 자금의 가치가 표시되지 않음

---

### 방식 3: 배분 차감하되, P&L %는 전체 자산 가치 기준 (복합)

**개념**:
- Account total balance는 배분 차감 후 잔액 표시
- 배분된 자금의 가치를 별도 추적
- P&L %는 (미배분 잔액 + 배분된 자금 현재 가치 + 실현 손익 - Initial Investment) 기준

**계산 공식**:
```
Account total balance = 
  Initial Investment 
  - (배분 합계)
  + (실현된 수익/손실 합계)

전체 자산 가치 = 
  Account total balance 
  + (배분된 자금 현재 가치)
  + (배분된 자금의 미실현 손익)

P&L % = ((전체 자산 가치 - Initial Investment) / Initial Investment) * 100
```

**예시**:
```
Initial Investment = 10,000 USDT

1. Alpha 30% 배분: 3,000 USDT
   Account total balance = 7,000 USDT (미배분 잔액)
   Alpha 배분 가치 = 3,000 USDT (거래 시작 전)
   전체 자산 가치 = 7,000 + 3,000 = 10,000 USDT
   P&L % = ((10,000 - 10,000) / 10,000) * 100 = 0.0% ✅

2. Alpha 거래 진행 중 (미실현 손익 +500 USDT)
   Account total balance = 7,000 USDT
   Alpha 배분 가치 = 3,000 + 500 = 3,500 USDT (미실현 손익 포함)
   전체 자산 가치 = 7,000 + 3,500 = 10,500 USDT
   P&L % = ((10,500 - 10,000) / 10,000) * 100 = +5.0% ✅

3. Alpha 거래 종료: +500 USDT 수익 실현
   Account total balance = 7,000 + 500 = 7,500 USDT (실현 손익 추가)
   Alpha 배분 가치 = 0 USDT (배분 해제)
   전체 자산 가치 = 7,500 + 0 = 7,500 USDT
   P&L % = ((7,500 - 10,000) / 10,000) * 100 = -25.0% ❌
   
   문제: Alpha에서 +500 USDT 수익이 발생했는데도 전체적으로 -25% 손실로 표시됨
```

**문제점**: 복잡하고 논리적으로 혼란스러움

---

## ✅ 최종 권장 계산 방식

### 방식 2: 배분 차감 + 실현 손익만 P&L % 반영 (권장)

**이유**:
1. 사용자 의도 반영 (배분 차감 표시)
2. 배분만 했을 때 P&L %가 0%로 올바르게 표시됨
3. 논리적으로 명확함
4. 구현이 비교적 간단함

**계산 공식**:
```
Account total balance = 
  Initial Investment 
  - (배분 합계)
  + (실현된 수익/손실 합계)

P&L % = (실현된 수익/손실 합계 / Initial Investment) * 100
```

**예시**:
```
Initial Investment = 10,000 USDT

1. Alpha 30% 배분: 3,000 USDT
   Account total balance = 10,000 - 3,000 = 7,000 USDT
   실현 손익 = 0 USDT
   P&L % = (0 / 10,000) * 100 = 0.0% ✅

2. Beta 30% 배분: 2,100 USDT
   Account total balance = 7,000 - 2,100 = 4,900 USDT
   실현 손익 = 0 USDT
   P&L % = 0.0% ✅

3. Gamma 30% 배분: 1,470 USDT
   Account total balance = 4,900 - 1,470 = 3,430 USDT
   실현 손익 = 0 USDT
   P&L % = 0.0% ✅

4. Alpha 거래 종료: +500 USDT 수익 실현
   Account total balance = 3,430 + 500 = 3,930 USDT
   실현 손익 = +500 USDT
   P&L % = (500 / 10,000) * 100 = +5.0% ✅

5. Beta 거래 종료: -200 USDT 손실 실현
   Account total balance = 3,930 - 200 = 3,730 USDT
   실현 손익 = +500 - 200 = +300 USDT
   P&L % = (300 / 10,000) * 100 = +3.0% ✅

6. Gamma 거래 종료: +300 USDT 수익 실현
   Account total balance = 3,730 + 300 = 4,030 USDT
   실현 손익 = +500 - 200 + 300 = +600 USDT
   P&L % = (600 / 10,000) * 100 = +6.0% ✅
```

---

## 📊 비교 분석

| 방식 | 배분 시 P&L % | 거래 종료 시 P&L % | Account total balance | 논리적 명확성 |
|------|--------------|-------------------|----------------------|-------------|
| **현재 제시된 방식** | ❌ -30.0% (잘못됨) | ❌ -60.7% (부정확) | 배분 차감 + 실현 손익 | ❌ 논리적 문제 |
| **방식 1: 배분 차감 없음** | ✅ 0.0% | ✅ +5.0% | Initial + 실현 손익 | ✅ 명확 |
| **방식 2: 배분 차감 + 실현 손익만** | ✅ 0.0% | ✅ +5.0% | 배분 차감 + 실현 손익 | ✅ 명확 |
| **방식 3: 복합** | ✅ 0.0% | ❌ -25.0% (부정확) | 복잡 | ❌ 혼란스러움 |

---

## ✅ 결론

### 발견된 모순점

1. ❌ **배분만 했을 때 손익률 발생**: 배분은 손익이 아닌데 -30%, -51%, -65.7%로 표시됨
2. ❌ **거래 종료 시 손익률 부정확**: 수익이 발생했는데도 전체적으로 손실로 표시됨
3. ❌ **논리적 문제**: 배분 차감을 손익으로 간주하여 계산하는 것이 부적절함

### 권장 계산 방식

**방식 2: 배분 차감 + 실현 손익만 P&L % 반영**

**계산 공식**:
```
Account total balance = Initial Investment - 배분 합계 + 실현 손익 합계
P&L % = (실현 손익 합계 / Initial Investment) * 100
```

**장점**:
- 배분만 했을 때 P&L % = 0% (올바름)
- 거래 종료 시 실제 수익/손실 정확히 반영
- 사용자 의도 반영 (배분 차감 표시)
- 논리적으로 명확함

---

**검증 일시**: 2025-01-XX  
**검증자**: AI Assistant  
**검증 범위**: P&L % 계산 로직 검증


