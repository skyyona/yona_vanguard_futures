# 백테스트 데이터 주입 미구현 버그 검증 보고서

**작성일**: 2025-11-20  
**분석 대상**: `backend/core/new_strategy/backtest_adapter.py`  
**버그 위치**: `BacktestExecutor._inject_data_to_orchestrator()` (Line 298-309)  
**심각도**: 🔴 **치명적 (CRITICAL)** - 모든 백테스트 기능 무력화

---

## 1. 버그 현황

### 1.1 현재 구현 상태 (Line 298-309)
```python
def _inject_data_to_orchestrator(self, idx: int):
    """
    Orchestrator의 DataFetcher 캐시에 백테스트 데이터 주입
    (실제 구현 시 MarketDataCache를 백테스트 모드로 전환)
    """
    # TODO: 실제 구현 필요
    # orchestrator.data_fetcher.cache.update({
    #     "1m": self.klines_1m.iloc[:idx+1],
    #     "3m": self.klines_3m.iloc[:self.current_3m_idx+1],
    #     "15m": self.klines_15m.iloc[:self.current_15m_idx+1],
    # })
    pass  # ← 비어있음!
```

**문제점**:
- 메서드 본문이 `pass`만 존재 (빈 구현)
- TODO 주석만 있고 실제 로직 없음
- Orchestrator에 백테스트 데이터 전달 불가

### 1.2 영향 범위
| 영향 대상 | 상태 | 결과 |
|----------|------|------|
| `BacktestExecutor.run()` | ❌ 실패 | 모든 백테스트 0점 |
| `IndicatorEngine.calculate()` | ❌ 데이터 없음 | InsufficientDataError 발생 가능 |
| `SignalEngine.evaluate()` | ❌ 진입 조건 평가 불가 | HOLD만 반환 |
| `get_trading_suitability()` API | ❌ 부적합 판정 | 모든 심볼 "부적합(0점)" |

---

## 2. 백테스트 실행 흐름 분석

### 2.1 현재 백테스트 실행 플로우 (routes.py → backtest_adapter.py → orchestrator.py)

```
[API 호출]
backend/api/routes.py::get_trading_suitability()
    │
    ├─> BacktestConfig 생성 (symbol, start_date, end_date, leverage, ...)
    │
    ├─> StrategyOrchestrator 생성
    │   └─> binance_client, config (enable_trading=False)
    │
    ├─> BacktestAdapter.run_backtest() 호출
    │   │
    │   ├─> BacktestDataLoader.load_historical_klines()
    │   │   ├─> 1m, 3m, 15m 캔들 데이터 로드 (Binance API)
    │   │   └─> DataFrame 변환 (timestamp, open, high, low, close, volume)
    │   │
    │   └─> BacktestExecutor 생성 및 실행
    │       │
    │       ├─> BacktestExecutor.__init__()
    │       │   ├─> klines_1m: pd.DataFrame (7~30일 과거 데이터)
    │       │   ├─> klines_3m: pd.DataFrame
    │       │   └─> klines_15m: pd.DataFrame
    │       │
    │       └─> BacktestExecutor.run()
    │           │
    │           ├─> for idx in range(len(klines_1m)):  # 1분봉 기준 순회
    │           │   │
    │           │   ├─> current_candle = klines_1m.iloc[idx]
    │           │   ├─> _update_timeframe_indices(current_time)  # 3m/15m 인덱스 동기화
    │           │   │
    │           │   ├─> _inject_data_to_orchestrator(idx) ⬅️ **여기가 버그!**
    │           │   │   └─> pass  # 아무것도 안함 (데이터 주입 실패)
    │           │   │
    │           │   ├─> orchestrator.step()  ⬅️ **캐시에 데이터 없음**
    │           │   │   │
    │           │   │   ├─> self.fetcher.cache.get_latest_candles()
    │           │   │   │   └─> InsufficientDataError 발생 (캐시 비어있음)
    │           │   │   │
    │           │   │   └─> indicator_engine.calculate()
    │           │   │       └─> 계산 실패 (데이터 부족)
    │           │   │
    │           │   └─> result.get("entry_triggered") → False (진입 기회 0회)
    │           │
    │           └─> _calculate_metrics()
    │               └─> total_trades=0, win_rate=0, max_drawdown=0 → 점수 0점
```

### 2.2 Orchestrator 데이터 사용 흐름 (orchestrator.py)

```python
# orchestrator.py::step() (Line 242-244)
def _compute_indicators(self, interval: str):
    # ⬇️ 여기서 캐시 데이터 조회
    candles = self.fetcher.cache.get_latest_candles(
        self.cfg.symbol, interval, self.indicator.required_candles
    )
    return self.indicator.calculate(candles)

# orchestrator.py::step() (Line 255-259)
def step(self) -> Dict[str, Any]:
    # 1m, 3m, 15m 지표 계산 시도
    ind_1m = self._compute_indicators(self.cfg.interval_entry)    # "1m"
    ind_3m = self._compute_indicators(self.cfg.interval_confirm)  # "3m"
    ind_15m = self._compute_indicators(self.cfg.interval_filter)  # "15m"
    
    # ⬆️ 캐시에 데이터 없으면 InsufficientDataError 발생
```

### 2.3 MarketDataCache 구조 (data_fetcher.py)

```python
# data_fetcher.py (Line 12-56)
class MarketDataCache:
    """멀티 심볼/타임프레임 시계열 데이터 캐시"""
    
    def __init__(self, max_candles: int = 2000):
        self.max_candles = max_candles
        # {symbol: {interval: deque[Candle]}}
        self._cache: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=max_candles))
        )
    
    def add_candle(self, candle: Candle) -> None:
        """새 캔들 추가 (최신 데이터는 뒤에 추가)"""
        cache = self._cache[candle.symbol][candle.interval]
        
        # 중복 체크 (같은 open_time)
        if cache and cache[-1].open_time == candle.open_time:
            # 기존 캔들 업데이트 (실시간 갱신)
            cache[-1] = candle
        else:
            cache.append(candle)
    
    def get_latest_candles(self, symbol: str, interval: str, count: int) -> List[Candle]:
        """최신 N개 캔들 조회 (시간 순서 오름차순)"""
        cache = self._cache[symbol][interval]
        if len(cache) < count:
            raise InsufficientDataError(
                f"요청 캔들 수({count}) > 캐시 크기({len(cache)}) for {symbol}/{interval}"
            )
        return list(cache)[-count:]
```

**핵심 발견**:
- 캐시는 `Candle` 객체의 deque로 관리
- DataFrame → Candle 변환 필요
- `add_candle()` 또는 `add_candles_bulk()` 메서드로 주입

---

## 3. 구현 계획

### 3.1 필수 구현 사항

#### ✅ **Step 1: DataFrame → Candle 변환 유틸리티 추가**
```python
def _dataframe_to_candles(
    self, 
    df: pd.DataFrame, 
    symbol: str, 
    interval: str
) -> List[Candle]:
    """DataFrame을 Candle 리스트로 변환"""
    from backend.core.new_strategy.data_structures import Candle
    
    candles = []
    for _, row in df.iterrows():
        candle = Candle(
            symbol=symbol,
            interval=interval,
            open_time=int(row["timestamp"].timestamp() * 1000),
            close_time=int(row["timestamp"].timestamp() * 1000) + interval_ms - 1,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            quote_volume=float(row.get("quote_volume", 0)),
            trades_count=int(row.get("trades", 0))
        )
        candles.append(candle)
    
    return candles
```

**타임프레임별 간격 (밀리초)**:
- `"1m"` → 60,000ms
- `"3m"` → 180,000ms
- `"15m"` → 900,000ms

#### ✅ **Step 2: `_inject_data_to_orchestrator()` 구현**
```python
def _inject_data_to_orchestrator(self, idx: int):
    """
    Orchestrator의 DataFetcher 캐시에 백테스트 데이터 주입
    
    Args:
        idx: 현재 1분봉 인덱스 (백테스트 진행 지점)
    
    로직:
        1. 현재 시점까지의 데이터만 캐시에 주입 (미래 데이터 누출 방지)
        2. 1m, 3m, 15m 각각 최신 200개 캔들 주입 (지표 계산 최소 요구)
        3. Candle 객체로 변환 후 cache.add_candles_bulk() 호출
    """
    from backend.core.new_strategy.data_structures import Candle
    
    symbol = self.config.symbol
    
    # 캐시 초기화 (기존 데이터 제거 - 백테스트 순수성 보장)
    self.orchestrator.fetcher.cache.clear(symbol)
    
    # 1분봉: 현재 인덱스까지의 최신 200개 (또는 전체)
    start_1m = max(0, idx + 1 - 200)
    df_1m_slice = self.klines_1m.iloc[start_1m:idx+1]
    candles_1m = self._dataframe_to_candles(df_1m_slice, symbol, "1m")
    
    # 3분봉: 현재 3m 인덱스까지의 최신 200개
    start_3m = max(0, self.current_3m_idx + 1 - 200)
    df_3m_slice = self.klines_3m.iloc[start_3m:self.current_3m_idx+1]
    candles_3m = self._dataframe_to_candles(df_3m_slice, symbol, "3m")
    
    # 15분봉: 현재 15m 인덱스까지의 최신 200개
    start_15m = max(0, self.current_15m_idx + 1 - 200)
    df_15m_slice = self.klines_15m.iloc[start_15m:self.current_15m_idx+1]
    candles_15m = self._dataframe_to_candles(df_15m_slice, symbol, "15m")
    
    # 캐시에 주입
    self.orchestrator.fetcher.cache.add_candles_bulk(candles_1m)
    self.orchestrator.fetcher.cache.add_candles_bulk(candles_3m)
    self.orchestrator.fetcher.cache.add_candles_bulk(candles_15m)
    
    logger.debug(
        f"[Backtest] 데이터 주입: 1m={len(candles_1m)}, "
        f"3m={len(candles_3m)}, 15m={len(candles_15m)} @ idx={idx}"
    )
```

**핵심 설계 원칙**:
1. **미래 데이터 누출 방지**: `idx` 시점까지만 주입
2. **지표 계산 최소 요구**: 200개 캔들 보장 (IndicatorEngine.required_candles)
3. **타임프레임 동기화**: `_update_timeframe_indices()` 결과 사용
4. **캐시 순수성**: 매 스텝마다 초기화 (이전 데이터 오염 방지)

#### ✅ **Step 3: close_time 계산 로직 추가**
```python
INTERVAL_MS = {
    "1m": 60 * 1000,
    "3m": 3 * 60 * 1000,
    "15m": 15 * 60 * 1000,
}

# Candle 생성 시
close_time = open_time + INTERVAL_MS[interval] - 1
```

### 3.2 선택적 최적화 (성능 개선)

#### 🔧 **Option 1: 증분 업데이트 (Incremental Update)**
현재 계획은 매 스텝마다 캐시를 초기화하고 200개를 다시 주입하는 방식입니다.  
**대안**: 최초 1회만 200개 주입, 이후 새 캔들만 추가

```python
def _inject_data_to_orchestrator(self, idx: int):
    """증분 업데이트 버전 (선택적)"""
    
    # 최초 실행 시에만 초기화
    if idx == 0:
        self.orchestrator.fetcher.cache.clear(self.config.symbol)
        # 초기 200개 주입 (위 구현과 동일)
        ...
    else:
        # 새 캔들만 추가 (1분봉은 매번 1개씩 증가)
        new_candle_1m = self._row_to_candle(
            self.klines_1m.iloc[idx], self.config.symbol, "1m"
        )
        self.orchestrator.fetcher.cache.add_candle(new_candle_1m)
        
        # 3m/15m은 인덱스 변경 시에만 추가
        if self._3m_idx_changed:
            new_candle_3m = ...
            self.orchestrator.fetcher.cache.add_candle(new_candle_3m)
        
        if self._15m_idx_changed:
            ...
```

**장점**: 메모리 복사 최소화, 속도 2~3배 향상  
**단점**: 구현 복잡도 증가, 인덱스 변경 감지 로직 필요

**권장**: 우선 Step 2 구현 완료 후, 성능 문제 발생 시 적용

#### 🔧 **Option 2: warmup 단계 추가**
백테스트 시작 전 Orchestrator에 초기 200개 캔들 주입

```python
def run(self) -> Dict[str, Any]:
    """백테스트 실행"""
    
    # Warmup: 초기 200개 캔들 주입
    self._warmup_orchestrator()
    
    for idx in range(total_candles):
        ...
```

**장점**: Orchestrator의 실거래 로직과 동일한 초기화  
**단점**: 현재는 필수 아님 (Step 2만으로도 충분)

---

## 4. 누락된 내용 검증

### 4.1 데이터 변환 관련 ✅ 완료 확인
- [x] `BacktestDataLoader.klines_to_dataframe()` 구현 완료 (Line 105-125)
  - 컬럼: `["timestamp", "open", "high", "low", "close", "volume"]`
  - 타입 변환: `pd.to_datetime()`, `astype(float)`
- [x] `Candle` 데이터 구조 정의 완료 (`data_structures.py` Line 7-21)

**추가 필요 사항**:
- `quote_volume`, `trades_count` 필드가 DataFrame에 누락
  → 백테스트에는 필수 아니므로 기본값 0 사용 가능
  → 필요 시 `klines_to_dataframe()` 수정:
    ```python
    df = df[["timestamp", "open", "high", "low", "close", "volume", "quote_volume", "trades"]]
    ```

### 4.2 Orchestrator 통합 ✅ 정상
- [x] `Orchestrator.fetcher.cache` 접근 가능 (Line 114)
- [x] `MarketDataCache.add_candle()` / `add_candles_bulk()` 메서드 존재 (data_fetcher.py)
- [x] `cache.clear(symbol)` 메서드 존재 (Line 54-58)

### 4.3 백테스트 실행 흐름 ✅ 정상
- [x] `BacktestExecutor.run()` 루프 구조 정상 (Line 214-271)
- [x] `_update_timeframe_indices()` 동기화 로직 정상 (Line 287-297)
- [x] `orchestrator.step()` 호출 정상 (Line 237)

### 4.4 메트릭 계산 ✅ 정상
- [x] `_calculate_metrics()` 구현 완료 (Line 377-418)
- [x] 승률, 수익률, MDD, Sharpe Ratio 계산 로직 존재
- [x] `evaluate_suitability()` API 정상 (routes.py Line 524-571)

### 4.5 누락 사항 요약

| 항목 | 상태 | 조치 필요 |
|-----|------|----------|
| `_inject_data_to_orchestrator()` 메서드 본문 | ❌ 미구현 | **필수** |
| `_dataframe_to_candles()` 유틸리티 | ❌ 없음 | **필수** |
| `quote_volume`, `trades_count` DataFrame 컬럼 | ⚠️ 누락 | 선택 (기본값 사용 가능) |
| 증분 업데이트 최적화 | ⚠️ 미구현 | 선택 (성능 개선용) |
| Warmup 단계 | ⚠️ 미구현 | 선택 (현재 불필요) |

---

## 5. 구현 계획 요약

### 5.1 필수 구현 (Priority 1) 🔴
1. **`_dataframe_to_candles()` 유틸리티 메서드 추가**
   - 위치: `BacktestExecutor` 클래스 내부
   - 기능: DataFrame → List[Candle] 변환
   - 추가 필요: `INTERVAL_MS` 상수 딕셔너리

2. **`_inject_data_to_orchestrator()` 메서드 완성**
   - 위치: `BacktestExecutor` (Line 298-309)
   - 기능: Orchestrator 캐시에 백테스트 데이터 주입
   - 핵심 로직:
     - 캐시 초기화 (`cache.clear(symbol)`)
     - 1m/3m/15m 각 200개 캔들 슬라이싱
     - Candle 변환 및 캐시 주입 (`add_candles_bulk()`)

### 5.2 선택적 개선 (Priority 2) 🟡
3. **DataFrame 컬럼 확장**
   - 위치: `BacktestDataLoader.klines_to_dataframe()` (Line 105-125)
   - 추가: `quote_volume`, `trades` 컬럼
   - 영향: Candle 객체 정확도 향상 (백테스트 정확도는 동일)

4. **증분 업데이트 최적화**
   - 성능 개선: 매 스텝 200개 복사 → 새 캔들 1개만 추가
   - 속도 향상: 2~3배 예상
   - 구현 복잡도: 중간 (인덱스 변경 감지 로직 필요)

### 5.3 구현 순서
```
Step 1: INTERVAL_MS 상수 정의
    ↓
Step 2: _dataframe_to_candles() 메서드 추가
    ↓
Step 3: _inject_data_to_orchestrator() 메서드 완성
    ↓
Step 4: 테스트 (BTCUSDT 7일 백테스트)
    ↓
Step 5: (선택) DataFrame 컬럼 확장
    ↓
Step 6: (선택) 증분 업데이트 최적화
```

---

## 6. 예상 결과

### 6.1 수정 전 (현재)
```python
# TNSRUSDT 백테스트 결과 (2024-11-13 ~ 2024-11-20)
{
    "total_trades": 0,        # 거래 기회 0회
    "win_rate": 0,            # 승률 0%
    "total_pnl": 0,           # 수익 0 USDT
    "max_drawdown": 0,        # MDD 0%
    "suitability": "부적합",   # 점수 0점
    "reason": "거래 기회 없음"
}
```

### 6.2 수정 후 (예상)
```python
# TNSRUSDT 백테스트 결과 (2024-11-13 ~ 2024-11-20)
{
    "total_trades": 12,       # 거래 기회 발생
    "win_rate": 58.3,         # 승률 58.3%
    "total_pnl": +850.5,      # 수익 +850 USDT (8.5%)
    "max_drawdown": -15.2,    # MDD -15.2%
    "suitability": "적합",     # 점수 78점
    "reason": "승률 우수, 수익률 양호, MDD 안정적"
}
```

**주의**: 위 예상 결과는 데이터 주입 성공 시 전략이 정상 작동할 경우의 시나리오입니다.  
실제 수익률은 전략 설계(급등 초반 포착)와 TNSRUSDT 급등 패턴(+451% 상승 이후)의 불일치로 인해 낮을 수 있습니다.

---

## 7. 테스트 계획

### 7.1 단위 테스트
```python
# test_backtest_data_injection.py
def test_dataframe_to_candles():
    """DataFrame → Candle 변환 테스트"""
    df = pd.DataFrame({
        "timestamp": [pd.Timestamp("2024-01-01 00:00:00")],
        "open": [40000.0],
        "high": [40100.0],
        "low": [39900.0],
        "close": [40050.0],
        "volume": [100.5]
    })
    
    candles = executor._dataframe_to_candles(df, "BTCUSDT", "1m")
    assert len(candles) == 1
    assert candles[0].symbol == "BTCUSDT"
    assert candles[0].interval == "1m"
    assert candles[0].close == 40050.0

def test_inject_data_to_orchestrator():
    """데이터 주입 테스트"""
    executor._inject_data_to_orchestrator(100)
    
    # 캐시에 데이터 존재 확인
    cache = executor.orchestrator.fetcher.cache
    assert cache.has_sufficient_data("BTCUSDT", "1m", 200)
    assert cache.has_sufficient_data("BTCUSDT", "3m", 200)
    assert cache.has_sufficient_data("BTCUSDT", "15m", 200)
```

### 7.2 통합 테스트
```python
def test_backtest_execution_with_data_injection():
    """전체 백테스트 실행 테스트"""
    config = BacktestConfig(
        symbol="BTCUSDT",
        start_date="2024-01-01",
        end_date="2024-01-07",
    )
    
    results = adapter.run_backtest(orchestrator, config)
    
    # 거래 발생 확인
    assert results["total_trades"] > 0, "거래 기회가 0회면 데이터 주입 실패"
    assert results["win_rate"] >= 0, "승률 계산 오류"
    assert "trades" in results, "거래 내역 누락"
```

### 7.3 실제 데이터 검증
```bash
# BTCUSDT 7일 백테스트 실행
POST /api/v1/backtest/suitability
{
    "symbol": "BTCUSDT",
    "period": "1w"
}

# 기대 결과:
# - total_trades > 0
# - suitability != "부적합" (0점)
# - reason != "거래 기회 없음"
```

---

## 8. 리스크 평가

| 리스크 항목 | 가능성 | 영향도 | 완화 방안 |
|-----------|-------|-------|----------|
| DataFrame → Candle 변환 오류 | 🟡 중간 | 🔴 높음 | 단위 테스트 + 타입 검증 |
| 타임프레임 동기화 오류 | 🟢 낮음 | 🟡 중간 | 기존 `_update_timeframe_indices()` 활용 |
| 메모리 부족 (30일 백테스트) | 🟢 낮음 | 🟡 중간 | 200개 슬라이싱으로 메모리 제한 |
| 미래 데이터 누출 | 🟢 낮음 | 🔴 높음 | `idx+1` 슬라이싱으로 현재 시점만 주입 |
| InsufficientDataError 지속 | 🟢 낮음 | 🔴 높음 | try-except + 로깅 강화 |

---

## 9. 결론

### 9.1 버그 확정 내용
✅ **백테스트 데이터 주입 미구현 버그 확정**
- 위치: `BacktestExecutor._inject_data_to_orchestrator()` (Line 298-309)
- 현상: 메서드 본문이 `pass`만 존재 (TODO 주석만 있음)
- 영향: 모든 백테스트 실패 (거래 기회 0회 → 점수 0점)

### 9.2 필수 구현 사항
1. **`_dataframe_to_candles()` 유틸리티 추가** (DataFrame → Candle 변환)
2. **`_inject_data_to_orchestrator()` 메서드 완성** (캐시 데이터 주입)
3. **`INTERVAL_MS` 상수 정의** (타임프레임별 밀리초 간격)

### 9.3 누락된 내용
- ✅ **핵심 기능**: 모두 구현 완료 (데이터 로더, 메트릭 계산, API 통합)
- ❌ **치명적 누락**: 데이터 주입 로직만 미구현
- ⚠️ **선택적 개선**: DataFrame 컬럼 확장, 증분 업데이트 최적화

### 9.4 구현 우선순위
**Priority 1 (필수)**: 
- `_dataframe_to_candles()` 메서드
- `_inject_data_to_orchestrator()` 메서드 본문

**Priority 2 (선택)**: 
- DataFrame 컬럼 확장 (quote_volume, trades)
- 증분 업데이트 최적화

### 9.5 예상 작업 시간
- 필수 구현: **30분** (코드 작성 + 단위 테스트)
- 통합 테스트: **15분** (BTCUSDT 7일 백테스트)
- 선택적 개선: **1시간** (최적화 + 성능 테스트)

---

**보고 완료**: 수정 미실시 (사용자 요청에 따라 분석만 완료)
