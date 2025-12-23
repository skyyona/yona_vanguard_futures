# YONA Vanguard Futures 전략 아키텍처 보고서

**작성일:** 2025-11-20  
**목적:** 앱 내 각 엔진별 적용 전략 내용 정리

---

## 📋 목차

1. [전체 아키텍처 개요](#1-전체-아키텍처-개요)
2. [Alpha/Beta/Gamma 전략 (래퍼 레이어)](#2-alphabetagamma-전략-래퍼-레이어)
3. [핵심 엔진별 전략 상세](#3-핵심-엔진별-전략-상세)
4. [전략 실행 흐름](#4-전략-실행-흐름)
5. [설정 파라미터 요약](#5-설정-파라미터-요약)

---

## 1. 전체 아키텍처 개요

### 1.1 구조 설계
```
┌──────────────────────────────────────────────────────────────┐
│                    GUI Layer (PySide6)                       │
│          Alpha/Beta/Gamma 전략 독립 실행 (3개 엔진)           │
└─────────────────────┬────────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │  Strategy Wrapper     │ (AlphaStrategy, BetaStrategy, GammaStrategy)
          │  - BaseStrategy 상속   │
          │  - Orchestrator 초기화 │
          │  - 이벤트 중계        │
          └───────────┬───────────┘
                      │
          ┌───────────┴───────────┐
          │ StrategyOrchestrator  │ ← 핵심 실행 엔진
          └───────────┬───────────┘
                      │
      ┌───────────────┼───────────────┐
      │               │               │
┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
│  Data     │  │ Indicator │  │  Signal   │
│  Fetcher  │→ │  Engine   │→ │  Engine   │
└───────────┘  └───────────┘  └─────┬─────┘
                                     │
                      ┌──────────────┴──────────────┐
                      │                             │
                ┌─────▼─────┐              ┌────────▼────────┐
                │   Risk    │              │   Execution     │
                │  Manager  │              │    Adapter      │
                └───────────┘              └─────────────────┘
```

### 1.2 전략 구성 요소
- **Alpha/Beta/Gamma**: 동일한 로직을 사용하는 3개 독립 인스턴스
- **Orchestrator**: 전략 실행 조율 (워밍업 → 루프)
- **6개 핵심 엔진**:
  1. DataFetcher - 데이터 수집
  2. IndicatorEngine - 지표 계산
  3. SignalEngine - 진입/청산 신호 생성
  4. RiskManager - 손절/익절 관리
  5. ExecutionAdapter - 주문 실행
  6. AdaptiveThresholdManager - 동적 임계치 조정 (옵션)

---

## 2. Alpha/Beta/Gamma 전략 (래퍼 레이어)

### 2.1 공통 특징
**파일 위치:**
- `backend/core/strategies/alpha_strategy.py`
- `backend/core/strategies/beta_strategy.py`
- `backend/core/strategies/gamma_strategy.py`

**역할:**
- BaseStrategy 인터페이스 구현 (GUI 호환)
- StrategyOrchestrator 1:1 래핑
- 이벤트 브릿지 (Orchestrator → GUI)

### 2.2 주요 책임
```python
# 1. 초기화 및 설정
- symbol, leverage, order_quantity 설정
- Orchestrator 인스턴스 생성
- 이벤트 콜백 연결

# 2. 실행 제어
- start(): Orchestrator 백그라운드 시작
- stop(): Orchestrator 중지 및 포지션 청산

# 3. 상태 동기화
- in_position, entry_price 추적
- 이벤트 기반 상태 업데이트 (ENTRY/EXIT)

# 4. GUI 통신
- 모든 Orchestrator 이벤트를 GUI로 전달
- engine 필드 추가 (Alpha/Beta/Gamma 구분)
```

### 2.3 이벤트 처리
```python
# _on_orchestrator_event 메서드에서 처리하는 이벤트
ENTRY           → in_position=True, entry_price 기록
EXIT            → in_position=False, PNL 계산
ENTRY_FAIL      → 에러 메시지 전송
WARMUP_FAIL     → 전략 중지, 에러 전송
EXIT_FAIL       → 에러 메시지 전송
WATCHLIST       → GUI로 전달 (상승에너지 탭)
DATA_PROGRESS   → GUI로 전달
TRAILING_ACTIVATED → GUI로 전달 (포지션분석 탭)
PROTECTIVE_PAUSE → GUI로 전달
```

### 2.4 설정 구조
```python
OrchestratorConfig:
    symbol: str                    # 거래 심볼
    leverage: int = 50             # 레버리지
    order_quantity: float = 0.001  # 고정 수량
    loop_interval_sec: float = 1.0 # 루프 주기
    enable_trading: bool = True    # 실거래 활성화
    adaptive_enabled: bool = False # 동적 임계치
    protective_pause_enabled: bool = False  # 보호 모드
```

---

## 3. 핵심 엔진별 전략 상세

### 3.1 StrategyOrchestrator (조율자)
**파일:** `backend/core/new_strategy/orchestrator.py`

**핵심 전략:**
```python
# 실행 단계
1. 워밍업 (warmup):
   - 1m/3m/15m 각 200개 캔들 수집
   - 지표 초기화 (EMA, MACD, RSI 등)
   - 실패 시 WARMUP_FAIL 이벤트 발생

2. 메인 루프 (step):
   - 1초마다 실행 (loop_interval_sec)
   - 새 캔들 감지 → 지표 업데이트
   - 신호 평가 → 리스크 평가
   - 주문 실행 또는 보유

3. 보호 모드:
   - 연속 실패 시 일시 정지
   - failure_threshold (기본 10회)
   - protective_pause_duration_sec (60초)

4. 동적 임계치:
   - adaptive_enabled=True 시 활성화
   - 최근 신호 점수 기반 조정
   - 과적합 방지
```

**상태 관리:**
```python
PositionState:
    symbol: str
    side: PositionSide (LONG만 지원)
    entry_price: float
    quantity: float
    stop_loss_price: float
    take_profit_price: float
    highest_price: float          # 최고가 추적 (트레일링)
    trailing_activated: bool      # 트레일링 활성화 여부
    opened_at: int               # 진입 시간 (ms)
    unrealized_pnl_pct: float    # 실시간 손익률
```

---

### 3.2 DataFetcher (데이터 수집)
**파일:** `backend/core/new_strategy/data_fetcher.py`

**핵심 전략:**
```python
# 역할
- Binance API에서 캔들스틱 데이터 수집
- 최근 200봉 기준 지표 계산 가능하도록 충분한 데이터 확보

# 주요 메서드
async fetch_historical_candles(symbol, interval, limit):
    - BinanceClient.get_klines() 호출
    - start_time, end_time 파라미터 사용 (snake_case) ← 최근 버그 수정
    - Candle 객체 리스트 반환
    
async fetch_latest_candle(symbol, interval):
    - 가장 최근 1개 캔들 수집
    - 실시간 업데이트용

# 데이터 구조
Candle:
    symbol: str
    interval: str
    open_time: int         # 타임스탬프 (ms)
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float    # USDT 거래량
```

**수집 전략:**
```python
# 워밍업 단계
- 1m, 3m, 15m 각각 200개 수집
- 충분한 과거 데이터 확보 (지표 정확도 향상)

# 메인 루프
- 캔들 종료 시간 추적 (_last_candle_times)
- 새 캔들 생성 시에만 업데이트
- 불필요한 API 호출 최소화
```

---

### 3.3 IndicatorEngine (지표 계산)
**파일:** `backend/core/new_strategy/indicator_engine.py`

**핵심 전략:**
```python
# 계산 지표 (IndicatorSet)
1. 이동평균선 (EMA)
   - EMA 5, 10, 20, 60, 120
   - 추세 및 정렬 상태 판단

2. MACD (이동평균 수렴확산)
   - macd_line (12-26)
   - macd_signal (9일 평균)
   - macd_histogram (line - signal)

3. RSI (상대강도지수)
   - rsi_14 (14일)
   - 과매수(70+)/과매도(30-) 판단

4. Stochastic RSI
   - stoch_rsi_k, stoch_rsi_d
   - 과매수(80+) 교차 감지

5. VWAP (거래량가중평균)
   - 일중 평균 가격
   - 가격 위치 판단 (VWAP 돌파)

6. 추가 지표
   - volume_spike: 평균 대비 2배 이상
   - trend: UPTREND/DOWNTREND/SIDEWAYS
   - consecutive_rise_count: EMA20 연속 상승 횟수
```

**계산 전략:**
```python
def compute(candles: List[Candle]) -> IndicatorSet:
    # 1. pandas DataFrame 변환
    # 2. ta-lib 또는 pandas_ta로 지표 계산
    # 3. 최신 값만 추출 ([-1])
    # 4. IndicatorSet 객체 반환
    
    # 거래량 급등 감지
    recent_volumes = df['volume'].tail(20)
    avg_vol = recent_volumes.mean()
    current_vol = df['volume'].iloc[-1]
    volume_spike = (current_vol > avg_vol * 2.0)
    
    # 추세 판단
    if ema_20 > ema_60 * 1.005:
        trend = "UPTREND"
    elif ema_20 < ema_60 * 0.995:
        trend = "DOWNTREND"
    else:
        trend = "SIDEWAYS"
```

---

### 3.4 SignalEngine (신호 생성)
**파일:** `backend/core/new_strategy/signal_engine.py`

**핵심 전략:**
```python
# 점수 기반 평가 시스템 (최대 170점)

SignalEngineConfig:
    min_entry_score: 100.0        # 관심종목 (WATCHLIST)
    strong_entry_score: 130.0     # 강한 진입
    instant_entry_score: 160.0    # 즉시 진입
    
    # 가중치 배분
    w_volume_spike: 30.0          # 거래량 급증
    w_vwap_breakout: 25.0         # VWAP 돌파
    w_5m_uptrend: 20.0            # EMA20 > EMA60
    w_ema_alignment: 20.0         # EMA 정렬 (5>10>20>60>120)
    w_consecutive_rise: 15.0      # EMA20 연속 상승
    w_3m_trend_confirm: 20.0      # 3분봉 상승 확인
    w_bear_energy_fade: 15.0      # 히스토그램 증가
    w_macd_golden_cross: 15.0     # MACD 골든크로스
    w_rsi_oversold_rebound: 10.0  # RSI 과매도 반등
```

**진입 신호 전략:**
```python
def evaluate(current_1m, prev_1m, confirm_3m, filter_15m) -> SignalResult:
    # 1. 15분봉 필터 (하락 추세 시 차단)
    if filter_15m.trend == "DOWNTREND":
        return HOLD
    
    # 2. 점수 계산 (_score_entry)
    score = 0
    
    # 거래량 급증 (30점)
    if current_1m.volume_spike:
        score += 30
    
    # VWAP 돌파 (25점)
    if last_close > current_1m.vwap:
        score += 25
    
    # EMA20 > EMA60 (20점)
    if current_1m.ema_20 > current_1m.ema_60:
        score += 20
    
    # EMA 정렬 (20점)
    if ema_5 > ema_10 > ema_20 > ema_60 > ema_120:
        score += 20
    
    # EMA20 연속 상승 (15점)
    if current_1m.ema_20 > prev_1m.ema_20:
        score += 15
    
    # 3분봉 상승 (20점)
    if confirm_3m.trend in ("UPTREND", "STRONG_UPTREND"):
        score += 20
    
    # MACD 히스토그램 증가 (15점)
    if current_1m.macd_histogram > prev_1m.macd_histogram:
        score += 15
    
    # MACD 골든크로스 (15점)
    if prev_1m.macd_line <= prev_1m.macd_signal and \
       current_1m.macd_line > current_1m.macd_signal:
        score += 15
    
    # RSI 과매도 반등 (10점)
    if prev_1m.rsi_14 < 35 and current_1m.rsi_14 > prev_1m.rsi_14:
        score += 10
    
    # 3. 행동 결정
    if score >= 160:    return BUY_LONG (즉시 진입)
    elif score >= 130:  return BUY_LONG (강한 진입)
    elif score >= 100:  return HOLD (WATCHLIST 이벤트 발생)
    else:               return HOLD
```

**청산 신호 전략:**
```python
def _evaluate_exit(current_1m, prev_1m) -> ExitSignal:
    exit_score = 0
    
    # EMA 역전 (50점)
    if current_1m.ema_20 < current_1m.ema_60 * 0.999:
        exit_score += 50
    
    # MACD 데드크로스 (40점)
    if current_1m.macd_line < current_1m.macd_signal:
        exit_score += 40
    
    # 히스토그램 하락 (20점)
    if current_1m.macd_histogram < prev_1m.macd_histogram:
        exit_score += 20
    
    # Stoch RSI 과매수 하향 교차 (20점)
    if prev_1m.stoch_rsi_k >= prev_1m.stoch_rsi_d and \
       current_1m.stoch_rsi_k < current_1m.stoch_rsi_d and \
       current_1m.stoch_rsi_k > 80:
        exit_score += 20
    
    # exit_score > 0 이면 CLOSE_LONG
    return CLOSE_LONG if exit_score > 0 else HOLD
```

---

### 3.5 RiskManager (리스크 관리)
**파일:** `backend/core/new_strategy/risk_manager.py`

**핵심 전략:**
```python
RiskManagerConfig:
    stop_loss_pct: 0.005           # 0.5% 손절
    tp_primary_pct: 0.02           # 2.0% 선익절
    tp_extended_pct: 0.035         # 3.5% 확장 익절
    trailing_stop_pct: 0.006       # 0.6% 트레일링
    breakeven_trigger_pct: 0.01    # 1.0% 수익 시 본절 이동
    time_limit_minutes: None       # 시간 제한 (옵션)
    extended_energy_score_threshold: 130.0  # 확장 판단 기준
```

**손익 관리 전략:**
```python
def evaluate(position, current_price, indicators_1m, last_signal):
    # 1. 손절 (-0.5%)
    pnl_pct = (current_price / entry_price - 1) * 100
    if pnl_pct <= -0.5:
        return EXIT (STOP_LOSS)
    
    # 2. 본절 이동 (+1% 시)
    if pnl_pct >= 1.0 and not trailing_activated:
        stop_loss_price = entry_price
        trailing_activated = True
        emit_event(TRAILING_ACTIVATED)
    
    # 3. +2% 선익절 로직
    if pnl_pct >= 2.0:
        # 최소 +2% 확정 (스탑을 진입가*1.02로)
        min_lock = entry_price * 1.02
        stop_loss_price = max(stop_loss_price, min_lock)
        
        # 상승 에너지 평가
        if last_signal.score >= 130:  # 에너지 충분
            # 목표를 +3.5%로 확장
            take_profit_price = entry_price * 1.035
        else:  # 에너지 부족
            # 즉시 +2% 익절
            return EXIT (TAKE_PROFIT)
    
    # 4. 트레일링 스탑 (활성화 후)
    if trailing_activated:
        trail_price = highest_price * 0.994  # 최고가 -0.6%
        # +2% 확정보다 낮아지지 않도록
        if pnl_pct >= 2.0:
            trail_price = max(trail_price, entry_price * 1.02)
        stop_loss_price = max(stop_loss_price, trail_price)
        
        if current_price <= stop_loss_price:
            return EXIT (TRAILING_STOP)
    
    # 5. 확장 익절 (+3.5%)
    if take_profit_price and current_price >= take_profit_price:
        return EXIT (TAKE_PROFIT)
    
    # 6. 시간 제한 (옵션)
    if time_limit_minutes and elapsed >= limit:
        return EXIT (TIME_LIMIT)
    
    return HOLD
```

**리스크 이벤트:**
```python
TRAILING_ACTIVATED:
    # +1% 수익 시 발생
    # stop_loss를 진입가로 이동
    # GUI 포지션분석 탭에 표시
```

---

### 3.6 ExecutionAdapter (주문 실행)
**파일:** `backend/core/new_strategy/execution_adapter.py`

**핵심 전략:**
```python
# 주요 책임
1. 거래 필터 검증
   - LOT_SIZE (stepSize, minQty, maxQty)
   - MIN_NOTIONAL (최소 거래 금액)
   - MARKET_LOT_SIZE

2. 수량 정규화
   - normalize_quantity(symbol, raw_qty)
   - stepSize로 반올림
   - minQty 검증
   - minNotional 검증 (가격 × 수량)

3. 레버리지/마진 설정
   - prepare_symbol(symbol, leverage, isolated)
   - set_margin_type (ISOLATED/CROSSED)
   - set_leverage (1x~125x)

4. 재시도 정책
   - 최대 3회 시도 (max_attempts)
   - 지수 백오프 (0.5초 → 1초 → 2초)
   - API 오류 시 자동 재시도
```

**주문 실행 전략:**
```python
def place_market_long(symbol, quantity) -> OrderResult:
    # 1. 사전 검증
    norm = normalize_quantity(symbol, quantity)
    if not norm.ok:
        return OrderResult(ok=False, error=norm.reason)
    
    # 2. 재시도 루프 (최대 3회)
    for attempt in range(1, 4):
        try:
            resp = client.create_market_order(
                symbol=symbol,
                side="BUY",
                quantity=norm.qty
            )
            
            if "error" not in resp:
                # 성공: filter_meta 포함하여 반환
                return OrderResult(
                    ok=True,
                    order_id=resp['orderId'],
                    avg_price=resp['avgPrice'],
                    executed_qty=resp['executedQty'],
                    fills=resp['fills'],
                    filter_meta={
                        "rawQty": quantity,
                        "finalQty": norm.qty,
                        "stepSize": norm.stepSize,
                        "minNotional": norm.minNotional,
                        ...
                    }
                )
            else:
                # API 오류 → 재시도
                logger.warning(f"시도 {attempt}/3 실패: {resp['error']}")
                time.sleep(backoff_delay)
                
        except Exception as e:
            logger.error(f"예외 발생: {e}")
            time.sleep(backoff_delay)
    
    # 3회 실패 시
    return OrderResult(ok=False, error="order_failed")

def close_market_long(symbol) -> OrderResult:
    # 동일한 재시도 로직
    # close_position_market(symbol, side="SELL") 사용
```

**OrderResult 구조:**
```python
@dataclass
class OrderResult:
    ok: bool
    symbol: str
    order_id: Optional[int] = None
    side: Optional[str] = None          # BUY/SELL
    avg_price: Optional[float] = None
    executed_qty: Optional[float] = None
    fills: Optional[List[OrderFill]] = None
    timestamp: Optional[int] = None
    error_message: Optional[str] = None
    filter_meta: Optional[Dict] = None  # 필터 검증 상세정보
```

---

### 3.7 AdaptiveThresholdManager (동적 임계치)
**파일:** `backend/core/new_strategy/adaptive_thresholds.py`

**핵심 전략:**
```python
# 목적: 과적합 방지, 시장 변동성 대응

class AdaptiveThresholdManager:
    def __init__(self):
        self.history = []  # 최근 신호 점수 기록
        self.max_history = 100
    
    def update(self, score: float):
        # 최근 100개 점수 저장
        self.history.append(score)
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def get_adjusted_thresholds(self, base_config: SignalEngineConfig):
        if len(self.history) < 20:
            # 충분한 데이터 없음 → 기본값 사용
            return base_config
        
        # 통계 분석
        avg_score = mean(self.history)
        std_score = std(self.history)
        
        # 동적 조정
        adjusted_min = avg_score + std_score * 0.5
        adjusted_strong = avg_score + std_score * 1.0
        adjusted_instant = avg_score + std_score * 1.5
        
        # 기본값 대비 ±20% 범위 제한
        min_entry = clamp(adjusted_min, 80, 120)
        strong_entry = clamp(adjusted_strong, 104, 156)
        instant_entry = clamp(adjusted_instant, 128, 192)
        
        return SignalEngineConfig(
            min_entry_score=min_entry,
            strong_entry_score=strong_entry,
            instant_entry_score=instant_entry,
            # 가중치는 동일 유지
            w_volume_spike=base_config.w_volume_spike,
            ...
        )
```

**적용 방법:**
```python
# Orchestrator에서 활성화
if self.cfg.adaptive_enabled:
    self._adaptive.update(last_signal.score)
    adjusted = self._adaptive.get_adjusted_thresholds(base_config)
    self.signal.config = adjusted
```

---

## 4. 전략 실행 흐름

### 4.1 초기화 단계
```
[GUI] 심볼 배정 버튼 클릭
  ↓
[AlphaStrategy] __init__
  ↓
[StrategyOrchestrator] 생성
  - DataFetcher 초기화
  - IndicatorEngine 초기화
  - SignalEngine 초기화
  - RiskManager 초기화
  - ExecutionAdapter 초기화
  ↓
[설정 적용] 버튼 클릭
  ↓
[ExecutionAdapter] prepare_symbol
  - 마진 타입: ISOLATED
  - 레버리지: 50x
```

### 4.2 워밍업 단계
```
[GUI] "거래 활성화" 버튼 클릭
  ↓
[AlphaStrategy] start()
  ↓
[Orchestrator] start() → warmup()
  ↓
[DataFetcher] fetch_historical_candles
  - 1m: 200개 수집
  - 3m: 200개 수집
  - 15m: 200개 수집
  ↓
[IndicatorEngine] compute
  - 각 인터벌별 지표 계산
  - IndicatorSet 생성
  ↓
워밍업 성공 → step() 루프 진입
워밍업 실패 → WARMUP_FAIL 이벤트 → 중지
```

### 4.3 메인 루프 (step)
```
[1초마다 실행]
  ↓
1. 캔들 업데이트 체크
   [DataFetcher] fetch_latest_candle
   - 새 캔들 생성 시에만 업데이트
   ↓
2. 지표 계산
   [IndicatorEngine] compute
   - 1m/3m/15m 각각 계산
   ↓
3. 신호 평가
   [SignalEngine] evaluate
   - 포지션 없음: 진입 신호 평가
   - 포지션 있음: 청산 신호 평가
   ↓
4. 리스크 평가 (포지션 있을 때만)
   [RiskManager] evaluate
   - 손절/익절/트레일링 체크
   ↓
5. 행동 결정
   - BUY_LONG → [ExecutionAdapter] place_market_long
   - CLOSE_LONG → [ExecutionAdapter] close_market_long
   - HOLD → 다음 루프 대기
   ↓
6. 이벤트 발생
   - ENTRY/EXIT/WATCHLIST/TRAILING_ACTIVATED 등
   ↓
7. GUI 업데이트
   [AlphaStrategy] _on_orchestrator_event
   - GUI 콜백 호출
   - 상태 동기화
```

### 4.4 종료 단계
```
[GUI] "거래 중지" 버튼 클릭
  ↓
[AlphaStrategy] stop()
  ↓
[Orchestrator] stop(force_close_position=True)
  ↓
포지션 있음?
  YES → [ExecutionAdapter] close_market_long
  NO → 즉시 종료
  ↓
루프 중지
  ↓
EXIT 이벤트 발생 (포지션 청산 시)
```

---

## 5. 설정 파라미터 요약

### 5.1 전략 설정 (OrchestratorConfig)
| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `symbol` | "BTCUSDT" | 거래 심볼 |
| `leverage` | 50 | 레버리지 배율 |
| `order_quantity` | 0.001 | 고정 주문 수량 (BTC) |
| `loop_interval_sec` | 1.0 | 루프 실행 주기 (초) |
| `enable_trading` | True | 실거래 활성화 |
| `adaptive_enabled` | False | 동적 임계치 사용 |
| `protective_pause_enabled` | False | 보호 모드 사용 |

### 5.2 신호 임계치 (SignalEngineConfig)
| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `min_entry_score` | 100.0 | 관심종목 임계치 |
| `strong_entry_score` | 130.0 | 강한 진입 임계치 |
| `instant_entry_score` | 160.0 | 즉시 진입 임계치 |

### 5.3 신호 가중치 (SignalEngineConfig)
| 지표 | 가중치 | 설명 |
|------|--------|------|
| `w_volume_spike` | 30.0 | 거래량 급증 |
| `w_vwap_breakout` | 25.0 | VWAP 돌파 |
| `w_5m_uptrend` | 20.0 | EMA20>EMA60 |
| `w_ema_alignment` | 20.0 | EMA 정렬 |
| `w_consecutive_rise` | 15.0 | EMA20 연속 상승 |
| `w_3m_trend_confirm` | 20.0 | 3분봉 확인 |
| `w_bear_energy_fade` | 15.0 | 히스토그램 증가 |
| `w_macd_golden_cross` | 15.0 | MACD 골든크로스 |
| `w_rsi_oversold_rebound` | 10.0 | RSI 반등 |
| **총점** | **170.0** | |

### 5.4 리스크 관리 (RiskManagerConfig)
| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `stop_loss_pct` | 0.005 | 손절 (-0.5%) |
| `tp_primary_pct` | 0.02 | 선익절 (+2.0%) |
| `tp_extended_pct` | 0.035 | 확장 익절 (+3.5%) |
| `trailing_stop_pct` | 0.006 | 트레일링 (-0.6%) |
| `breakeven_trigger_pct` | 0.01 | 본절 이동 (+1.0%) |
| `time_limit_minutes` | None | 시간 제한 (비활성) |
| `extended_energy_score_threshold` | 130.0 | 확장 판단 기준 |

### 5.5 주문 실행 (ExecutionRetryPolicy)
| 파라미터 | 기본값 | 설명 |
|---------|--------|------|
| `max_attempts` | 3 | 최대 재시도 횟수 |
| `base_backoff_sec` | 0.5 | 초기 대기 시간 |
| `backoff_multiplier` | 2.0 | 백오프 배율 |

---

## 📊 전략 특징 요약

### ✅ 강점
1. **모듈화**: 각 엔진이 독립적으로 작동, 유지보수 용이
2. **점수 시스템**: 170점 만점, 명확한 진입 기준
3. **3중 시간프레임**: 1m(진입) + 3m(확인) + 15m(필터)
4. **동적 리스크**: 본절 이동 → 트레일링 → 확장 익절
5. **재시도 로직**: 네트워크 오류 자동 처리
6. **이벤트 기반**: 실시간 GUI 업데이트

### ⚠️ 제약사항
1. **LONG 전용**: 숏 포지션 미지원
2. **단일 포지션**: 동시 진입 불가
3. **고정 수량**: 자본금 비례 조정 미구현
4. **수동 심볼**: 자동 스캐닝 없음

### 🎯 적용 전략 핵심
- **진입**: 9가지 조건 점수화 → 130점 이상 진입
- **청산**: 4가지 조건 (EMA역전/MACD데드크로스/히스토그램/StochRSI)
- **리스크**: +2% 선확정 + 에너지 기반 확장(+3.5%) + 트레일링(-0.6%)
- **필터**: 15분봉 하락 추세 시 진입 차단

---

**보고서 끝**
