# 백테스트 하니스 계약 정의

**작성일:** 2025-11-18  
**목적:** 과거 데이터 기반 전략 성능 검증 및 파라미터 최적화  
**상태:** DRAFT → REVIEW → FROZEN

---

## 1. 백테스트 목적

### 1.1 주요 목표
- 신규 전략의 역사적 성능 검증 (수익률, 승률, MDD)
- 전략 파라미터 최적화 (손절/익절/트레일링 %)
- Legacy 전략과의 성능 비교 (동일 기간/심볼)
- 리스크 시나리오 테스트 (변동성 급증, 연속 손실)

### 1.2 사용 시점
- 신규 전략 구현 완료 후 실거래 전
- 파라미터 튜닝 시 (score weights, thresholds)
- 새로운 심볼 추가 전 검증
- 정기 성능 리뷰 (월별, 분기별)

---

## 2. 입력 데이터 구조

### 2.1 HistoricalData (과거 데이터)
```python
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class HistoricalData:
    """백테스트 입력 데이터"""
    symbol: str
    interval: str  # "1m", "3m", "5m", "15m"
    start_time: int  # Unix timestamp (ms)
    end_time: int  # Unix timestamp (ms)
    candles: List[Candle]  # 시간 순 정렬된 캔들 리스트
    
    # 메타 정보
    total_candles: int
    data_source: str  # "binance_api", "csv", "database"
    gaps: List[Dict]  # 데이터 누락 구간 [{start, end, reason}, ...]
```

### 2.2 BacktestConfig (백테스트 설정)
```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class BacktestConfig:
    """백테스트 실행 설정"""
    
    # 전략 설정
    profile: 'StrategyProfile'
    
    # 시뮬레이션 설정
    initial_capital: float  # 초기 자본 (USDT)
    commission_rate: float = 0.0004  # 수수료율 (0.04% Taker)
    slippage_pct: float = 0.0001  # 슬리피지 (0.01%)
    
    # 데이터 설정
    symbols: List[str]  # 백테스트 심볼 리스트
    start_date: str  # "2025-01-01"
    end_date: str  # "2025-01-31"
    intervals: List[str] = None  # ["1m", "3m", "5m", "15m"], None이면 profile 기본값
    
    # 실행 옵션
    enable_logging: bool = True
    log_trades: bool = True
    log_signals: bool = False  # 미체결 신호도 로그
    save_equity_curve: bool = True
    
    # 최적화 (선택)
    optimize_params: Optional[Dict] = None  # {"take_profit": [0.03, 0.04, 0.05], ...}
```

---

## 3. BacktestAdapter 인터페이스

### 3.1 주요 메서드
```python
from typing import List, Dict, Optional
from abc import ABC, abstractmethod

class BacktestAdapter(ABC):
    """백테스트 실행 어댑터"""
    
    @abstractmethod
    def load_historical_data(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int
    ) -> HistoricalData:
        """
        과거 데이터 로드
        
        Args:
            symbol: 심볼
            interval: 시간 간격
            start_time: 시작 시간 (Unix ms)
            end_time: 종료 시간 (Unix ms)
            
        Returns:
            HistoricalData
            
        Raises:
            DataLoadError: 데이터 로드 실패
            InsufficientDataError: 데이터 부족
        """
        pass
    
    @abstractmethod
    def run(
        self,
        config: BacktestConfig
    ) -> 'PerformanceReport':
        """
        백테스트 실행
        
        Args:
            config: 백테스트 설정
            
        Returns:
            PerformanceReport (성능 리포트)
            
        실행 흐름:
            1. 데이터 로드 (모든 intervals)
            2. 캔들별 순차 시뮬레이션
               - MarketDataCache 업데이트
               - IndicatorEngine 계산
               - SignalEngine 평가
               - RiskManager 평가
               - 모의 주문 실행 (수수료/슬리피지 적용)
            3. 성능 메트릭 계산
            4. 리포트 생성
        """
        pass
    
    @abstractmethod
    def optimize(
        self,
        config: BacktestConfig
    ) -> 'OptimizationReport':
        """
        파라미터 최적화
        
        Args:
            config: 백테스트 설정 (optimize_params 필수)
            
        Returns:
            OptimizationReport
            
        방법:
            - Grid Search: 모든 조합 시도
            - 최적 파라미터 조합 추출 (Sharpe Ratio 기준)
        """
        pass
    
    @abstractmethod
    def compare_strategies(
        self,
        configs: List[BacktestConfig]
    ) -> 'ComparisonReport':
        """
        여러 전략 비교 (동일 기간/심볼)
        
        Args:
            configs: 비교할 전략 설정 리스트
            
        Returns:
            ComparisonReport
        """
        pass
```

### 3.2 구현 클래스
```python
class SimulationBacktestAdapter(BacktestAdapter):
    """시뮬레이션 기반 백테스트 구현"""
    
    def __init__(
        self,
        data_fetcher: DataFetcher,
        indicator_engine: IndicatorEngine,
        signal_engine: SignalEngine,
        risk_manager: RiskManager
    ):
        self.data_fetcher = data_fetcher
        self.indicator_engine = indicator_engine
        self.signal_engine = signal_engine
        self.risk_manager = risk_manager
        
        # 시뮬레이션 상태
        self._sim_time: int = 0
        self._sim_equity: float = 0.0
        self._sim_positions: Dict[str, PositionState] = {}
        self._sim_trades: List[Trade] = []
    
    # 메서드 구현...
```

---

## 4. 출력 데이터 구조

### 4.1 Trade (거래 기록)
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Trade:
    """단일 거래 기록"""
    trade_id: int
    symbol: str
    
    # 진입
    entry_time: int  # Unix timestamp (ms)
    entry_price: float
    entry_quantity: float
    entry_side: str  # "LONG" or "SHORT"
    
    # 청산
    exit_time: int
    exit_price: float
    exit_reason: str  # "TAKE_PROFIT", "STOP_LOSS", "TRAILING", ...
    
    # 손익
    gross_pnl: float  # 수수료/슬리피지 전
    commission: float
    slippage: float
    net_pnl: float  # 실제 손익
    pnl_pct: float  # 수익률 (%)
    
    # 통계
    holding_time_sec: int  # 보유 시간 (초)
    max_favorable_excursion: float  # MFE (최대 유리 편차)
    max_adverse_excursion: float  # MAE (최대 불리 편차)
```

### 4.2 PerformanceMetrics (성능 지표)
```python
from dataclasses import dataclass

@dataclass
class PerformanceMetrics:
    """성능 메트릭"""
    
    # 기본 통계
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float  # 승률 (%)
    
    # 손익
    total_pnl: float  # 총 손익 (USDT)
    total_return_pct: float  # 총 수익률 (%)
    avg_win: float  # 평균 승리 손익
    avg_loss: float  # 평균 손실 손익
    profit_factor: float  # 이익 팩터 (총승/총패)
    
    # 위험 조정 수익률
    sharpe_ratio: float  # 샤프 비율
    sortino_ratio: float  # 소르티노 비율
    calmar_ratio: float  # 칼마 비율
    
    # 드로우다운
    max_drawdown: float  # 최대 드로우다운 (USDT)
    max_drawdown_pct: float  # 최대 드로우다운 (%)
    max_drawdown_duration_sec: int  # 최대 드로우다운 지속 시간
    
    # 일일 통계
    avg_daily_return: float
    avg_daily_trades: float
    best_day: float
    worst_day: float
    
    # 보유 시간
    avg_holding_time_sec: int
    median_holding_time_sec: int
    
    # 연속성
    max_consecutive_wins: int
    max_consecutive_losses: int
```

### 4.3 EquityCurve (자본 곡선)
```python
from dataclasses import dataclass
from typing import List

@dataclass
class EquityPoint:
    """자본 곡선 단일 포인트"""
    timestamp: int
    equity: float
    drawdown_pct: float

@dataclass
class EquityCurve:
    """자본 곡선"""
    points: List[EquityPoint]
    initial_capital: float
    final_capital: float
```

### 4.4 PerformanceReport (성능 리포트)
```python
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class PerformanceReport:
    """백테스트 성능 리포트"""
    
    # 메타 정보
    config: BacktestConfig
    start_time: int
    end_time: int
    duration_sec: int
    
    # 거래 기록
    trades: List[Trade]
    
    # 성능 지표
    metrics: PerformanceMetrics
    
    # 자본 곡선
    equity_curve: EquityCurve
    
    # 신호 분석 (선택)
    total_signals: Optional[int] = None  # 생성된 신호 수
    executed_signals: Optional[int] = None  # 실제 체결된 신호
    signal_execution_rate: Optional[float] = None  # 신호 체결률
    
    # 오류/경고
    warnings: List[str] = None  # 경고 메시지
    errors: List[str] = None  # 오류 메시지
```

### 4.5 OptimizationReport (최적화 리포트)
```python
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class OptimizationResult:
    """단일 파라미터 조합 결과"""
    params: Dict[str, any]  # {"take_profit": 0.04, "stop_loss": 0.005, ...}
    sharpe_ratio: float
    total_return_pct: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int

@dataclass
class OptimizationReport:
    """파라미터 최적화 리포트"""
    config: BacktestConfig
    
    # 모든 결과
    results: List[OptimizationResult]
    
    # 최적 결과
    best_params: Dict[str, any]  # Sharpe Ratio 기준
    best_sharpe: float
    
    # 분석
    param_correlations: Dict[str, float]  # 파라미터별 Sharpe 상관관계
```

### 4.6 ComparisonReport (비교 리포트)
```python
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class StrategyComparison:
    """전략 비교 항목"""
    name: str
    metrics: PerformanceMetrics
    equity_curve: EquityCurve

@dataclass
class ComparisonReport:
    """전략 비교 리포트"""
    period: str  # "2025-01-01 ~ 2025-01-31"
    symbol: str
    
    # 비교 대상
    strategies: List[StrategyComparison]
    
    # 순위
    best_sharpe: str  # 전략 이름
    best_return: str
    lowest_drawdown: str
    highest_winrate: str
```

---

## 5. 백테스트 실행 흐름

### 5.1 순차 시뮬레이션
```
1. 데이터 로드
   ↓
2. 초기화
   - equity = initial_capital
   - positions = {}
   - trades = []
   ↓
3. 각 캔들별 순회 (시간 순)
   ↓
   3.1 MarketDataCache 업데이트
   ↓
   3.2 IndicatorEngine: 지표 계산
   ↓
   3.3 RiskManager: 포지션 리스크 평가
       → ExitSignal 발생 시 청산 시뮬레이션
   ↓
   3.4 SignalEngine: 진입 신호 평가
       → BUY_LONG 발생 시 진입 시뮬레이션
   ↓
   3.5 Equity 업데이트
       - 체결: equity += net_pnl
       - 미실현: equity + unrealized_pnl
   ↓
   3.6 EquityCurve 기록
   ↓
4. 성능 메트릭 계산
   ↓
5. PerformanceReport 생성
```

### 5.2 모의 주문 실행
```python
def simulate_market_order(
    side: str,
    quantity: float,
    candle: Candle,
    commission_rate: float,
    slippage_pct: float
) -> Dict:
    """
    시장가 주문 시뮬레이션
    
    Args:
        side: "BUY" or "SELL"
        quantity: 수량
        candle: 현재 캔들
        commission_rate: 수수료율
        slippage_pct: 슬리피지 비율
        
    Returns:
        {
            "executed_price": float,
            "executed_qty": float,
            "commission": float,
            "slippage": float
        }
    """
    # 체결 가격 계산 (슬리피지 적용)
    if side == "BUY":
        executed_price = candle.close * (1 + slippage_pct)
    else:
        executed_price = candle.close * (1 - slippage_pct)
    
    # 수수료 계산
    notional = executed_price * quantity
    commission = notional * commission_rate
    
    return {
        "executed_price": executed_price,
        "executed_qty": quantity,
        "commission": commission,
        "slippage": abs(candle.close - executed_price) * quantity
    }
```

---

## 6. 성능 지표 계산 공식

### 6.1 승률 (Win Rate)
```
win_rate = (winning_trades / total_trades) * 100
```

### 6.2 이익 팩터 (Profit Factor)
```
total_wins = sum(pnl for pnl in trades if pnl > 0)
total_losses = abs(sum(pnl for pnl in trades if pnl < 0))
profit_factor = total_wins / total_losses  # (> 1 = 수익성)
```

### 6.3 샤프 비율 (Sharpe Ratio)
```
daily_returns = [(equity[i] - equity[i-1]) / equity[i-1] for i in range(1, len(equity))]
avg_daily_return = mean(daily_returns)
std_daily_return = stdev(daily_returns)
sharpe_ratio = (avg_daily_return / std_daily_return) * sqrt(252)  # 연간화
```

### 6.4 최대 드로우다운 (Max Drawdown)
```
peak = equity[0]
max_dd = 0
for e in equity:
    if e > peak:
        peak = e
    dd = (peak - e) / peak
    if dd > max_dd:
        max_dd = dd
max_drawdown_pct = max_dd * 100
```

### 6.5 칼마 비율 (Calmar Ratio)
```
calmar_ratio = total_return_pct / max_drawdown_pct
```

---

## 7. 데이터 소스

### 7.1 Binance API (실시간/과거)
```python
class BinanceHistoricalDataLoader:
    """Binance API에서 과거 데이터 로드"""
    
    def load(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int
    ) -> HistoricalData:
        """
        Binance API를 통해 과거 데이터 로드
        
        제한:
            - 최대 1500개/요청
            - 시간 범위 자동 분할
            - Rate Limit 준수
        """
        pass
```

### 7.2 CSV 파일
```python
class CSVHistoricalDataLoader:
    """CSV 파일에서 과거 데이터 로드"""
    
    def load(self, file_path: str) -> HistoricalData:
        """
        CSV 형식:
            timestamp,open,high,low,close,volume
            1640995200000,47000.5,47500.0,46800.0,47200.0,1234.56
        """
        pass
```

### 7.3 데이터베이스 (선택)
```python
class DatabaseHistoricalDataLoader:
    """DB에서 과거 데이터 로드 (대량 백테스트용)"""
    
    def load(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int
    ) -> HistoricalData:
        pass
```

---

## 8. 백테스트 예제

### 8.1 단일 전략 백테스트
```python
from datetime import datetime

# 1. 설정 생성
config = BacktestConfig(
    profile=alpha_profile,
    initial_capital=10000.0,
    commission_rate=0.0004,
    slippage_pct=0.0001,
    symbols=["BTCUSDT"],
    start_date="2025-01-01",
    end_date="2025-01-31",
    intervals=["1m", "3m", "15m"],
    enable_logging=True,
    save_equity_curve=True
)

# 2. 백테스트 실행
adapter = SimulationBacktestAdapter(
    data_fetcher=data_fetcher,
    indicator_engine=indicator_engine,
    signal_engine=signal_engine,
    risk_manager=risk_manager
)

report = adapter.run(config)

# 3. 결과 출력
print(f"총 거래: {report.metrics.total_trades}")
print(f"승률: {report.metrics.win_rate:.2f}%")
print(f"총 수익률: {report.metrics.total_return_pct:.2f}%")
print(f"샤프 비율: {report.metrics.sharpe_ratio:.2f}")
print(f"최대 드로우다운: {report.metrics.max_drawdown_pct:.2f}%")
```

### 8.2 파라미터 최적화
```python
config = BacktestConfig(
    profile=alpha_profile,
    initial_capital=10000.0,
    symbols=["BTCUSDT"],
    start_date="2025-01-01",
    end_date="2025-01-31",
    optimize_params={
        "take_profit_pct": [0.03, 0.035, 0.04, 0.045],
        "stop_loss_pct": [0.005, 0.0075, 0.01],
        "trailing_pct": [0.003, 0.005, 0.007]
    }
)

opt_report = adapter.optimize(config)

print(f"최적 파라미터: {opt_report.best_params}")
print(f"최고 샤프: {opt_report.best_sharpe:.2f}")
```

### 8.3 전략 비교
```python
configs = [
    BacktestConfig(profile=alpha_profile, ...),
    BacktestConfig(profile=beta_profile, ...),
    BacktestConfig(profile=legacy_alpha, ...)
]

comparison = adapter.compare_strategies(configs)

for s in comparison.strategies:
    print(f"{s.name}: 수익률 {s.metrics.total_return_pct:.2f}%, "
          f"샤프 {s.metrics.sharpe_ratio:.2f}")

print(f"최고 샤프: {comparison.best_sharpe}")
print(f"최고 수익률: {comparison.best_return}")
```

---

## 9. 백테스트 검증 체크리스트

### 9.1 데이터 품질
- [ ] 캔들 데이터 누락 없음 (또는 갭 기록)
- [ ] 타임스탬프 순서 정확
- [ ] 가격 이상치 제거 (OHLC 검증)
- [ ] 거래량 0 제거

### 9.2 시뮬레이션 정확성
- [ ] 수수료 적용 (0.04% Taker)
- [ ] 슬리피지 적용 (0.01%)
- [ ] Look-Ahead Bias 방지 (미래 데이터 사용 금지)
- [ ] Survivorship Bias 고려 (상장폐지 심볼)

### 9.3 성능 메트릭
- [ ] 샤프 비율 계산 정확
- [ ] 드로우다운 계산 정확
- [ ] 승률/이익팩터 일치

### 9.4 Legacy 비교
- [ ] 동일 기간/심볼 사용
- [ ] 동일 수수료/슬리피지
- [ ] 진입/청산 조건 동등성 확인

---

## 10. 백테스트 결과 활용

### 10.1 파라미터 확정
- 최적화 결과 → StrategyProfile 반영
- 과적합 방지: 여러 기간/심볼로 교차 검증

### 10.2 리스크 한도 설정
- 최대 드로우다운 기반 → 일일 손실 한도 설정
- 연속 손실 횟수 → 거래 중단 조건

### 10.3 실거래 전환 판단
- 승률 ≥ 60%
- 샤프 비율 ≥ 1.5
- 최대 드로우다운 ≤ 3%
- 이익 팩터 ≥ 2.0

---

## 11. 다음 단계

- [x] 모듈 인터페이스 설계 완료
- [x] 백테스트 하니스 계약 정의 완료
- [ ] StrategyProfile 스키마 작성
- [ ] 구현 시작 (BacktestAdapter → 성능 검증)

---

**변경 이력:**
- 2025-11-18: 초안 작성 (백테스트 인터페이스 및 성능 지표 정의 완료)
