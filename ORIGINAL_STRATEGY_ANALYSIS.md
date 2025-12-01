# 미완성 'YONA Vanguard Futures' 자동매매 전략 분석 보고서

## 📋 개요
미완성 **YONA Vanguard Futures** 앱의 자동매매 엔진 전략 구조를 상세히 분석하고 검증한 결과를 보고합니다.

---

## 🏗️ 전체 아키텍처

### 의존성 주입 구조
미완성 앱은 **복잡한 의존성 주입(Dependency Injection)** 패턴을 사용합니다.

```python
class BaseStrategy(ABC):
    def __init__(self, 
                 engine_name: str,
                 trade_manager: TradeManager,
                 account_manager: AccountManager,
                 blacklist_manager: BlacklistManager,
                 data_processor: DataProcessor,
                 trend_analyzer: TrendAnalyzer,
                 stop_loss_manager: StopLossManager,
                 trailing_stop_manager: TrailingStopManager):
```

**필요한 외부 매니저:**
1. `TradeManager` - 바이낸스 주문 실행
2. `AccountManager` - 계좌 정보 및 포지션 관리
3. `BlacklistManager` - 블랙리스트 심볼 관리
4. `DataProcessor` - K-line 데이터 제공
5. `TrendAnalyzer` - 추세 분석
6. `StopLossManager` - 손절 가격 계산 및 실행
7. `TrailingStopManager` - 트레일링 스톱 관리

---

## 🎯 3개 엔진 전략 상세 분석

### 1. **Alpha 엔진 전략** (1분봉 스캘핑)

**파일**: `backend/core/strategies/alpha_engine_strategy.py`

#### 전략 특성
- **타임프레임**: 1분봉 (초단기)
- **거래 스타일**: 빠른 스캘핑
- **수익 목표**: 낮음 (빠른 회전율)

#### 진입 조건 (LONG만 지원)

```python
# 1. 추세 확인
current_trend in ["UPTREND", "STRONG_UPTREND"]

# 2. EMA 골든 크로스
ema20 > ema60 * 1.0001  # 0.01% 이상 차이

# 3. Stochastic RSI 조건
stoch_rsi_k > stoch_rsi_d AND
20 < stoch_rsi_k < 70

# 4. 거래량 급증
volume_analysis["is_spike"] == True
```

**모든 조건이 동시에 만족되어야 진입!**

#### 청산 조건

```python
# 1. 익절
pnl_percent > PROFIT_TAKE_PERCENT_SCALPING  # config.py에서 0.7%

# 2. 손절
pnl_percent <= -STOP_LOSS_PERCENT  # config.py에서 0.5%

# 3. EMA 데드 크로스
ema20 < ema60 * 0.999
```

#### 리스크 관리
- **초기 손절가**: 진입가 기준 0.5% 하락
- **트레일링 스톱**: 진입 즉시 활성화 (0.3% 추적)
- **포지션 크기**: `(자본 * 레버리지) / 현재가`

---

### 2. **Beta 엔진 전략** (데이 트레이딩)

**파일**: `backend/core/strategies/beta_engine_strategy.py`

#### 전략 특성
- **타임프레임**: 5분-15분봉 (중단기)
- **거래 스타일**: 신중한 데이 트레이딩
- **수익 목표**: 중간 (Alpha보다 보수적)

#### 진입 조건 (LONG만 지원)

```python
# 1. 강한 추세 확인
current_trend == "STRONG_UPTREND"  # Alpha보다 엄격!

# 2. EMA 정배열 (3개 EMA 모두 확인)
ema20 > ema60 * 1.0001 AND
ema60 > ema120 * 1.0001

# 3. Stochastic RSI 조건
stoch_rsi_k > stoch_rsi_d AND
30 < stoch_rsi_k < 70  # Alpha보다 좁은 범위

# 4. MACD 골든 크로스
macd > macd_signal AND
macd_histogram > 0
```

**Alpha보다 더 많은 조건 필요!**

#### 청산 조건

```python
# 1. 익절
pnl_percent > PROFIT_TAKE_PERCENT_DAYTRADE  # 1.5%

# 2. 손절
pnl_percent <= -STOP_LOSS_PERCENT  # 0.5%

# 3. EMA 데드 크로스 또는 MACD 데드 크로스
(ema20 < ema60 * 0.999) OR
(macd < macd_signal AND macd_histogram < 0)
```

#### 리스크 관리
- **초기 손절가**: 진입가 기준 0.5% 하락 (Alpha와 동일)
- **트레일링 스톱**: 진입 즉시 활성화 (0.3% 추적)
- **포지션 크기**: `(자본 * 레버리지) / 현재가`

---

### 3. **Gamma 엔진 전략** (스윙/모멘텀 트레이딩)

**파일**: `backend/core/strategies/gamma_engine_strategy.py`

#### 전략 특성
- **타임프레임**: 15분-1시간봉 이상 (장기)
- **거래 스타일**: 보수적 스윙 트레이딩
- **수익 목표**: 높음 (느린 회전율)

#### 진입 조건 (LONG만 지원)

```python
# 1. 가장 강한 추세만 허용
current_trend == "STRONG_UPTREND"

# 2. EMA 장기 정배열 (더 큰 차이 요구)
ema20 > ema60 * 1.0002 AND  # 0.02% 이상 (Beta의 2배!)
ema60 > ema120 * 1.0002

# 3. MACD 강한 상승 신호
macd > macd_signal AND
macd_histogram > 0
```

**가장 적은 조건이지만 가장 엄격!**

#### 청산 조건

```python
# 1. 익절
pnl_percent > PROFIT_TAKE_PERCENT_SWING  # 2.5% (가장 높음!)

# 2. 손절
pnl_percent <= -STOP_LOSS_PERCENT  # 0.5%

# 3. MACD 데드 크로스만 확인
macd < macd_signal AND macd_histogram < 0
```

#### 리스크 관리
- **초기 손절가**: 진입가 기준 0.5% 하락
- **트레일링 스톱**: 진입 즉시 활성화 (0.3% 추적)
- **포지션 크기**: `(자본 * 레버리지) / 현재가`

---

## 📊 3개 엔진 비교표

| 구분 | Alpha (스캘핑) | Beta (데이 트레이딩) | Gamma (스윙) |
|------|----------------|---------------------|--------------|
| **타임프레임** | 1분봉 | 5-15분봉 | 15분-1시간 이상 |
| **추세 조건** | UPTREND 이상 | STRONG_UPTREND | STRONG_UPTREND |
| **EMA 조건** | 2개 (20, 60) | 3개 (20, 60, 120) | 3개 (더 큰 차이) |
| **Stoch RSI** | ✅ 필수 | ✅ 필수 | ❌ 불필요 |
| **MACD** | ❌ 불필요 | ✅ 필수 | ✅ 필수 |
| **거래량** | ✅ 필수 | ❌ 불필요 | ❌ 불필요 |
| **익절 목표** | 0.7% | 1.5% | 2.5% |
| **손절** | 0.5% | 0.5% | 0.5% |
| **진입 난이도** | 중간 (4개 조건) | 높음 (5개 조건) | 낮음 (3개 조건) |
| **진입 엄격도** | 낮음 | 중간 | 높음 |
| **거래 빈도** | 높음 | 중간 | 낮음 |
| **위험도** | 중간 | 중간 | 낮음 |

---

## 🔧 공통 BaseStrategy 기능

### 1. DB 연동 설정 관리

```python
def _load_config_from_db(self):
    db_config = session.query(EngineConfig).filter_by(engine_name=self.engine_name).first()
    # symbol, capital_allocation, leverage, is_active 로드
```

### 2. 계좌 데이터 처리

```python
def handle_account_data(self, all_positions: dict):
    # 현재 엔진의 심볼 포지션 정보 업데이트
    # in_position, position_side, entry_price, position_quantity, current_pnl 갱신
```

### 3. 리스크 관리 적용

```python
def apply_risk_management(self, current_price: float):
    # 1. 고정 손절가 확인 및 적용
    # 2. 트레일링 스톱 업데이트 및 확인
```

### 4. 메인 실행 루프

```python
def run(self):
    while True:
        if self.is_active:
            # 1. 최신 K-line 데이터 가져오기
            # 2. 리스크 관리 적용
            # 3. 조건 평가 (evaluate_conditions)
            # 4. 거래 실행 (execute_trade)
            # 5. GUI 업데이트
        time.sleep(1)
```

---

## ⚙️ config.py 설정값

### 수익률 목표

```python
PROFIT_TAKE_PERCENT_SCALPING = 0.007   # 0.7% (Alpha)
PROFIT_TAKE_PERCENT_DAYTRADE = 0.015   # 1.5% (Beta)
PROFIT_TAKE_PERCENT_SWING = 0.025      # 2.5% (Gamma)
```

### 리스크 관리

```python
STOP_LOSS_PERCENT = 0.005        # 0.5% 손절
TRAILING_STOP_PERCENT = 0.003    # 0.3% 트레일링
```

### 지표 기간

```python
EMA_SHORT_PERIOD = 20
EMA_MEDIUM_PERIOD = 60
EMA_LONG_PERIOD = 120
RSI_PERIOD = 14
STOCH_K_PERIOD = 14
STOCH_D_PERIOD = 3
MACD_FAST_PERIOD = 12
MACD_SLOW_PERIOD = 26
MACD_SIGNAL_PERIOD = 9
VOLUME_LOOKBACK_PERIOD = 20
```

### 기본값

```python
DEFAULT_LEVERAGE = 10
DEFAULT_CAPITAL_PER_ENGINE = 5000.0  # USDT
```

---

## ✅ 전략 검증 결과

### 강점

1. **체계적인 구조**
   - BaseStrategy 추상 클래스로 공통 기능 구현
   - 의존성 주입으로 유연한 설계
   - DB 연동으로 설정 영속성 확보

2. **리스크 관리 철저**
   - 모든 엔진에 손절/익절 자동 적용
   - 트레일링 스톱으로 수익 보호
   - StopLossManager, TrailingStopManager 분리

3. **다양한 전략**
   - Alpha: 빠른 스캘핑 (높은 빈도, 낮은 수익)
   - Beta: 신중한 데이 트레이딩 (중간 빈도, 중간 수익)
   - Gamma: 보수적 스윙 (낮은 빈도, 높은 수익)

4. **실전 적용 가능**
   - 바이낸스 API 직접 연동
   - 실제 주문 실행 로직 구현
   - 계좌 관리 및 포지션 추적

### 약점

1. **복잡한 의존성**
   - 7개의 매니저 클래스 필요
   - 초기화 순서 중요
   - 테스트 어려움

2. **LONG 전용**
   - 숏 포지션 미지원
   - 하락장에서 비효율적

3. **고정된 레버리지/자본**
   - 시장 변동성에 따른 동적 조절 없음
   - 계좌 잔고 자동 관리 미흡

4. **지표 의존도 높음**
   - 급격한 시장 변화 대응 느림
   - 가짜 신호(false signal) 가능성

---

## 🆚 새로운 앱과의 비교

| 구분 | 미완성 YONA | 새로운 YONA(new) |
|------|-------------|------------------|
| **구조** | 복잡 (7개 매니저) | 간단 (독립 전략) |
| **의존성** | 높음 (DB 필수) | 낮음 (선택적) |
| **테스트** | 어려움 | 쉬움 (시뮬레이션) |
| **실전 적용** | 완성도 높음 | 기본 구조만 |
| **리스크 관리** | 매우 철저 | 기본적 |
| **바이낸스 연동** | 완전 구현 | 미구현 |
| **GUI 연동** | IPC Manager | WebSocket |
| **확장성** | 제한적 | 높음 |

---

## 📝 결론

### ✅ 검증 완료 사항

1. **전략 로직 정상**: Alpha/Beta/Gamma 각 엔진의 진입/청산 조건이 명확하고 논리적
2. **리스크 관리 우수**: 손절/익절/트레일링 스톱 모두 구현됨
3. **실전 준비도**: 바이낸스 API 연동 및 실제 주문 로직 완성
4. **설정 관리**: DB 기반 영속성 및 런타임 변경 지원

### ⚠️ 개선 필요 사항

1. **의존성 단순화**: 7개 매니저를 통합하거나 선택적으로 사용
2. **숏 포지션 추가**: 하락장 대응을 위한 숏 전략 구현
3. **동적 자본 관리**: 계좌 잔고 및 시장 변동성 기반 포지션 크기 조절
4. **백테스팅**: 전략 검증을 위한 백테스팅 시스템 필요

### 💡 추천 사항

**새로운 앱(YONA Vanguard Futures(new))에 적용할 내용:**

1. ✅ **전략 로직 차용**: Alpha/Beta/Gamma의 진입/청산 조건은 우수하므로 새로운 앱에 적용 권장
2. ✅ **리스크 관리 통합**: StopLossManager, TrailingStopManager 개념 차용
3. ❌ **의존성 주입 최소화**: 7개 매니저 대신 자체 완결형 전략으로 재구성
4. ✅ **config.py 활용**: 수익률 목표, 손절 비율 등 설정값 동일하게 사용

---

**작성일**: 2025-11-10  
**검증 대상**: YONA Vanguard Futures (미완성)  
**상태**: 분석 완료 ✅
