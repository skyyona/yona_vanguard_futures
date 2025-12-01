# 모듈 인터페이스 설계 문서

**작성일:** 2025-11-18  
**목적:** Option B 신규 아키텍처 모듈 간 계약 정의  
**상태:** DRAFT → REVIEW → FROZEN

---

## 1. 설계 원칙

### 1.1 인터페이스 계약
- 각 모듈은 명확한 입력/출력 계약을 가짐
- 타입 힌트(Type Hints) 필수 사용
- 예외는 명시적으로 문서화
- 부작용(Side Effects) 최소화

### 1.2 의존성 방향
- 단방향 의존성: 상위 → 하위
- 순환 의존성 금지
- Infrastructure(BinanceClient, Logger) ← Domain Modules ← Orchestrator

### 1.3 테스트 가능성
- 모든 모듈은 Mock 가능한 인터페이스
- 외부 의존성(API, DB)은 주입(Injection) 가능
- 순수 함수 우선 사용

---

## 2. 데이터 구조 (공통)

### 2.1 Candle (캔들스틱)
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Candle:
    """단일 캔들스틱 데이터"""
    symbol: str
    interval: str  # "1m", "3m", "5m", "15m", "1h"
    open_time: int  # Unix timestamp (ms)
    close_time: int  # Unix timestamp (ms)
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float  # USDT volume
    trades_count: int
```

### 2.2 IndicatorSet (지표 집합)
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class IndicatorSet:
    """계산된 지표 값 집합 (최신 값)"""
    symbol: str
    timestamp: int  # 계산 시점 Unix timestamp (ms)
    
    # EMA
    ema_5: Optional[float] = None
    ema_10: Optional[float] = None
    ema_20: Optional[float] = None
    ema_60: Optional[float] = None
    ema_120: Optional[float] = None
    
    # RSI
    rsi_14: Optional[float] = None
    
    # Stochastic RSI
    stoch_rsi_k: Optional[float] = None
    stoch_rsi_d: Optional[float] = None
    
    # MACD
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    
    # VWAP
    vwap: Optional[float] = None
    
    # ATR
    atr_14: Optional[float] = None
    
    # Volume
    volume_spike: bool = False
    volume_avg_20: Optional[float] = None
    
    # 추세
    trend: str = "NEUTRAL"  # "STRONG_UPTREND", "UPTREND", "DOWNTREND", "NEUTRAL"
```

### 2.3 SignalResult (신호 결과)
```python
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

class SignalAction(Enum):
    """신호 액션 타입"""
    BUY_LONG = "BUY_LONG"
    SELL_SHORT = "SELL_SHORT"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"
    HOLD = "HOLD"

@dataclass
class SignalResult:
    """신호 평가 결과"""
    symbol: str
    timestamp: int
    action: SignalAction
    score: float  # 0~170 (점수 시스템 사용 시)
    confidence_pct: float  # 0~100
    triggers: List[str]  # 발동된 조건 목록 (예: ["volume_spike", "macd_cross"])
    reason: str  # 신호 발생 이유 설명
```

### 2.4 PositionState (포지션 상태)
```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class PositionSide(Enum):
    """포지션 방향"""
    LONG = "LONG"
    SHORT = "SHORT"

@dataclass
class PositionState:
    """포지션 상태 정보"""
    symbol: str
    side: PositionSide
    entry_price: float
    quantity: float
    leverage: int
    
    # 추적 정보
    opened_at: int  # Unix timestamp (ms)
    highest_price: float  # 진입 이후 최고가
    lowest_price: float  # 진입 이후 최저가
    
    # 손익
    unrealized_pnl: float  # 미실현 손익 (USDT)
    unrealized_pnl_pct: float  # 미실현 손익률 (%)
    
    # 리스크 관리
    stop_loss_price: float
    take_profit_price: float
    trailing_activated: bool = False
```

### 2.5 ExitSignal (청산 신호)
```python
from dataclasses import dataclass
from enum import Enum

class ExitReason(Enum):
    """청산 이유"""
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    EMA_REVERSAL = "EMA_REVERSAL"
    MACD_REVERSAL = "MACD_REVERSAL"
    TIME_LIMIT = "TIME_LIMIT"
    MANUAL = "MANUAL"

@dataclass
class ExitSignal:
    """청산 신호"""
    symbol: str
    timestamp: int
    reason: ExitReason
    action: SignalAction  # CLOSE_LONG or CLOSE_SHORT
    message: str
```

### 2.6 OrderResult (주문 결과)
```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class OrderFill:
    """체결 내역"""
    price: float
    quantity: float
    commission: float
    commission_asset: str

@dataclass
class OrderResult:
    """주문 실행 결과"""
    ok: bool
    symbol: str
    order_id: Optional[int] = None
    side: Optional[str] = None  # "BUY" or "SELL"
    avg_price: Optional[float] = None
    executed_qty: Optional[float] = None
    fills: List[OrderFill] = None
    timestamp: Optional[int] = None
    
    # 오류 정보
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    
    # 슬리피지
    expected_price: Optional[float] = None
    slippage_pct: Optional[float] = None
```

### 2.7 RiskAssessment (리스크 평가)
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class RiskAssessment:
    """리스크 평가 결과"""
    symbol: str
    timestamp: int
    
    # 포지션 위험도
    current_risk_pct: float  # 현재 위험도 (손실 가능성 %)
    max_position_size: float  # 최대 허용 포지션 크기
    
    # 시장 위험도
    volatility_level: str  # "LOW", "MEDIUM", "HIGH", "EXTREME"
    atr_percentile: float  # ATR 백분위 (0~100)
    
    # 계좌 위험도
    account_exposure_pct: float  # 계좌 노출도 (전체 자본 대비 %)
    daily_loss_pct: float  # 당일 손실률
    consecutive_losses: int  # 연속 손실 횟수
    
    # 제한 상태
    trading_allowed: bool
    reason: Optional[str] = None  # 거래 금지 이유
```

---

## 3. DataFetcher (데이터 수집)

### 3.1 책임
- Binance API를 통한 실시간 캔들 데이터 수집
- 멀티 심볼, 멀티 타임프레임 동시 처리
- Rate Limit 준수
- 데이터 검증 및 오류 처리

### 3.2 인터페이스
```python
from typing import List, Optional, Dict
from abc import ABC, abstractmethod

class DataFetcher(ABC):
    """데이터 수집 인터페이스"""
    
    @abstractmethod
    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 200,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Candle]:
        """
        캔들스틱 데이터 가져오기
        
        Args:
            symbol: 심볼 (예: "BTCUSDT")
            interval: 시간 간격 ("1m", "3m", "5m", "15m", "1h")
            limit: 최대 개수 (기본 200, 최대 1500)
            start_time: 시작 시간 (Unix ms, optional)
            end_time: 종료 시간 (Unix ms, optional)
            
        Returns:
            Candle 리스트 (시간 순 정렬)
            
        Raises:
            APIError: API 호출 실패
            ValidationError: 잘못된 파라미터
        """
        pass
    
    @abstractmethod
    def fetch_mark_price(self, symbol: str) -> float:
        """
        Mark Price 가져오기
        
        Args:
            symbol: 심볼
            
        Returns:
            현재 Mark Price
            
        Raises:
            APIError: API 호출 실패
        """
        pass
    
    @abstractmethod
    def fetch_multiple_klines(
        self,
        requests: List[Dict[str, any]]
    ) -> Dict[str, List[Candle]]:
        """
        여러 심볼/타임프레임 동시 조회
        
        Args:
            requests: [{"symbol": "BTCUSDT", "interval": "1m", "limit": 200}, ...]
            
        Returns:
            {symbol_interval: [Candle, ...], ...}
            예: {"BTCUSDT_1m": [...], "ETHUSDT_3m": [...]}
            
        Raises:
            APIError: API 호출 실패
        """
        pass
```

### 3.3 구현 클래스
```python
class BinanceDataFetcher(DataFetcher):
    """Binance API 기반 데이터 수집 구현"""
    
    def __init__(self, binance_client: BinanceClient):
        self.client = binance_client
        self._cache: Dict[str, List[Candle]] = {}
        self._last_fetch: Dict[str, int] = {}
        self._cooldown_ms = 3000  # 3초 쿨다운
    
    # 메서드 구현...
```

---

## 4. MarketDataCache (시장 데이터 캐시)

### 4.1 책임
- 수집된 캔들 데이터 메모리 캐시
- 시계열 데이터 효율적 관리
- TTL(Time To Live) 기반 자동 정리

### 4.2 인터페이스
```python
from typing import List, Optional, Dict
from collections import deque

class MarketDataCache:
    """시장 데이터 캐시"""
    
    def __init__(self, max_candles: int = 2000):
        """
        Args:
            max_candles: 심볼당 최대 캔들 수
        """
        self.max_candles = max_candles
        self._data: Dict[str, deque[Candle]] = {}
    
    def update(self, symbol: str, interval: str, candles: List[Candle]) -> None:
        """
        캔들 데이터 업데이트
        
        Args:
            symbol: 심볼
            interval: 시간 간격
            candles: 새로운 캔들 리스트
        """
        pass
    
    def get_candles(
        self,
        symbol: str,
        interval: str,
        limit: Optional[int] = None
    ) -> List[Candle]:
        """
        캔들 데이터 조회
        
        Args:
            symbol: 심볼
            interval: 시간 간격
            limit: 최근 N개 (None이면 전체)
            
        Returns:
            Candle 리스트 (시간 순)
        """
        pass
    
    def get_latest_price(self, symbol: str, interval: str) -> Optional[float]:
        """최신 종가 조회"""
        pass
    
    def get_series(
        self,
        symbol: str,
        interval: str,
        field: str,  # "close", "high", "low", "volume"
        limit: Optional[int] = None
    ) -> List[float]:
        """
        특정 필드의 시계열 데이터 추출
        
        Returns:
            값 리스트 (시간 순)
        """
        pass
```

---

## 5. IndicatorEngine (지표 계산)

### 5.1 책임
- 기술적 지표 계산 (EMA, RSI, MACD, Stoch RSI, VWAP, ATR, Volume Spike)
- 계산 결과 캐시
- 의존성 관리 (예: MACD는 EMA 필요)

### 5.2 인터페이스
```python
from typing import List, Optional, Dict
from abc import ABC, abstractmethod

class IndicatorEngine(ABC):
    """지표 계산 엔진"""
    
    @abstractmethod
    def compute_ema(
        self,
        prices: List[float],
        period: int
    ) -> List[float]:
        """
        EMA (Exponential Moving Average) 계산
        
        Args:
            prices: 가격 리스트 (시간 순)
            period: 기간 (예: 5, 10, 20, 60, 120)
            
        Returns:
            EMA 값 리스트 (prices와 동일 길이)
        """
        pass
    
    @abstractmethod
    def compute_rsi(
        self,
        prices: List[float],
        period: int = 14
    ) -> List[float]:
        """
        RSI (Relative Strength Index) 계산
        
        Args:
            prices: 가격 리스트
            period: 기간 (기본 14)
            
        Returns:
            RSI 값 리스트 (0~100)
        """
        pass
    
    @abstractmethod
    def compute_stoch_rsi(
        self,
        rsi_values: List[float],
        period: int = 14
    ) -> Dict[str, List[float]]:
        """
        Stochastic RSI 계산
        
        Args:
            rsi_values: RSI 값 리스트
            period: 기간
            
        Returns:
            {"k": [...], "d": [...]}
        """
        pass
    
    @abstractmethod
    def compute_macd(
        self,
        prices: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, List[float]]:
        """
        MACD 계산
        
        Args:
            prices: 가격 리스트
            fast: Fast EMA 기간
            slow: Slow EMA 기간
            signal: Signal Line 기간
            
        Returns:
            {
                "macd": [...],
                "signal": [...],
                "histogram": [...]
            }
        """
        pass
    
    @abstractmethod
    def compute_vwap(
        self,
        candles: List[Candle]
    ) -> List[float]:
        """
        VWAP (Volume Weighted Average Price) 계산
        
        Args:
            candles: 캔들 리스트
            
        Returns:
            VWAP 값 리스트
        """
        pass
    
    @abstractmethod
    def compute_atr(
        self,
        candles: List[Candle],
        period: int = 14
    ) -> List[float]:
        """
        ATR (Average True Range) 계산
        
        Args:
            candles: 캔들 리스트
            period: 기간
            
        Returns:
            ATR 값 리스트
        """
        pass
    
    @abstractmethod
    def detect_volume_spike(
        self,
        volumes: List[float],
        threshold: float = 3.0,
        lookback: int = 20
    ) -> bool:
        """
        거래량 급증 감지
        
        Args:
            volumes: 거래량 리스트
            threshold: 평균 대비 배수 (기본 3배)
            lookback: 비교 기간 (기본 20개)
            
        Returns:
            급증 여부
        """
        pass
    
    @abstractmethod
    def compute_all(
        self,
        symbol: str,
        interval: str,
        cache: MarketDataCache
    ) -> IndicatorSet:
        """
        모든 지표 일괄 계산
        
        Args:
            symbol: 심볼
            interval: 시간 간격
            cache: 캔들 데이터 캐시
            
        Returns:
            IndicatorSet (모든 지표 최신 값)
            
        Raises:
            InsufficientDataError: 데이터 부족
        """
        pass
```

### 5.3 구현 클래스
```python
class TechnicalIndicatorEngine(IndicatorEngine):
    """기술적 지표 계산 구현"""
    
    def __init__(self):
        self._indicator_cache: Dict[str, IndicatorSet] = {}
        self._cache_ttl_ms = 5000  # 5초 캐시
    
    # 메서드 구현...
```

---

## 6. SignalEngine (신호 생성)

### 6.1 책임
- 진입/청산 조건 평가
- 점수 시스템 또는 Rule 기반 신호 생성
- 다중 타임프레임 통합 분석

### 6.2 인터페이스
```python
from typing import Dict, Optional
from abc import ABC, abstractmethod

class SignalEngine(ABC):
    """신호 생성 엔진"""
    
    @abstractmethod
    def evaluate_entry(
        self,
        symbol: str,
        indicators_1m: IndicatorSet,
        indicators_3m: IndicatorSet,
        indicators_5m: Optional[IndicatorSet] = None,
        indicators_15m: Optional[IndicatorSet] = None,
        current_price: float,
        profile: 'StrategyProfile'
    ) -> SignalResult:
        """
        진입 신호 평가
        
        Args:
            symbol: 심볼
            indicators_1m: 1분봉 지표
            indicators_3m: 3분봉 지표
            indicators_5m: 5분봉 지표 (선택)
            indicators_15m: 15분봉 지표 (선택)
            current_price: 현재가
            profile: 전략 프로파일
            
        Returns:
            SignalResult (BUY_LONG, SELL_SHORT, HOLD)
        """
        pass
    
    @abstractmethod
    def evaluate_exit(
        self,
        symbol: str,
        position: PositionState,
        indicators: IndicatorSet,
        current_price: float,
        profile: 'StrategyProfile'
    ) -> Optional[ExitSignal]:
        """
        청산 신호 평가
        
        Args:
            symbol: 심볼
            position: 포지션 상태
            indicators: 현재 지표
            current_price: 현재가
            profile: 전략 프로파일
            
        Returns:
            ExitSignal (청산 필요 시) 또는 None
        """
        pass
```

### 6.3 구현 클래스
```python
class ScoreBasedSignalEngine(SignalEngine):
    """점수 기반 신호 생성 (170점 만점)"""
    
    def __init__(self):
        self.score_weights = {
            "volume_spike": 30,
            "vwap_break": 20,
            "ema_alignment": 20,
            "macd_cross": 15,
            "stoch_rebound": 10,
            # ...
        }
    
    # 메서드 구현...

class RuleBasedSignalEngine(SignalEngine):
    """규칙 기반 신호 생성 (AND/OR 조건)"""
    
    # 메서드 구현...
```

---

## 7. PositionSizer (포지션 크기 계산)

### 7.1 책임
- 위험 기반 포지션 크기 계산
- 거래 필터 검증 (LOT_SIZE, MIN_NOTIONAL)
- 레버리지 적용 및 제한

### 7.2 인터페이스
```python
from typing import Dict, Optional
from abc import ABC, abstractmethod

class PositionSizer(ABC):
    """포지션 크기 계산"""
    
    @abstractmethod
    def compute_quantity(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_pct: float,
        account_equity: float,
        risk_fraction: float,
        leverage: int,
        max_leverage: int
    ) -> Dict[str, any]:
        """
        위험 기반 수량 계산
        
        Args:
            symbol: 심볼
            entry_price: 진입 예상 가격
            stop_loss_pct: 손절 퍼센트 (예: 0.005 = 0.5%)
            account_equity: 계좌 자본
            risk_fraction: 위험 비율 (예: 0.01 = 1%)
            leverage: 목표 레버리지
            max_leverage: 최대 레버리지
            
        Returns:
            {
                "ok": bool,
                "quantity": float,
                "notional": float,
                "reason": str (실패 시)
            }
            
        계산 공식:
            허용_위험_금액 = account_equity * risk_fraction
            quantity = 허용_위험_금액 / (entry_price * stop_loss_pct)
            
            레버리지 검증:
            notional = entry_price * quantity
            if (notional / account_equity) > max_leverage:
                quantity 축소
        """
        pass
    
    @abstractmethod
    def validate_filters(
        self,
        symbol: str,
        quantity: float,
        price: float
    ) -> Dict[str, any]:
        """
        거래 필터 검증
        
        Args:
            symbol: 심볼
            quantity: 수량
            price: 가격
            
        Returns:
            {
                "ok": bool,
                "adjusted_quantity": float,
                "reason": str (실패 시)
            }
            
        검증 항목:
            - LOT_SIZE: stepSize, minQty, maxQty
            - MIN_NOTIONAL: 최소 명목 금액
            - MARKET_LOT_SIZE: 시장가 주문 제한
        """
        pass
```

### 7.3 구현 클래스
```python
class RiskBasedPositionSizer(PositionSizer):
    """위험 기반 포지션 크기 계산 구현"""
    
    def __init__(self, binance_client: BinanceClient):
        self.client = binance_client
        self._filter_cache: Dict[str, Dict] = {}
    
    # 메서드 구현...
```

---

## 8. RiskManager (리스크 관리)

### 8.1 책임
- 실시간 포지션 리스크 평가
- 손절/익절/트레일링 조건 감시
- 계좌 수준 위험 제한

### 8.2 인터페이스
```python
from typing import Optional, Dict
from abc import ABC, abstractmethod

class RiskManager(ABC):
    """리스크 관리"""
    
    @abstractmethod
    def assess_position_risk(
        self,
        position: PositionState,
        current_price: float,
        indicators: IndicatorSet,
        profile: 'StrategyProfile'
    ) -> Optional[ExitSignal]:
        """
        포지션 리스크 평가 및 청산 신호 생성
        
        Args:
            position: 포지션 상태
            current_price: 현재가
            indicators: 현재 지표
            profile: 전략 프로파일
            
        Returns:
            ExitSignal (청산 필요 시) 또는 None
            
        평가 항목:
            - 손절: price <= stop_loss_price
            - 익절: price >= take_profit_price
            - 트레일링: highest_price - price >= trailing_pct
            - EMA 역전: ema_20 < ema_60
            - MACD 데드 크로스: macd < signal
            - 시간 제한: holding_time > max_duration
        """
        pass
    
    @abstractmethod
    def update_trailing_stop(
        self,
        position: PositionState,
        current_price: float,
        profile: 'StrategyProfile'
    ) -> PositionState:
        """
        트레일링 스톱 업데이트
        
        Args:
            position: 포지션 상태
            current_price: 현재가
            profile: 전략 프로파일
            
        Returns:
            업데이트된 PositionState
            
        로직:
            1. unrealized_pnl_pct >= 1% → 손절가를 본절(진입가 + 0.2%)로 이동
            2. trailing_activated == True → highest_price 업데이트
        """
        pass
    
    @abstractmethod
    def assess_account_risk(
        self,
        account_equity: float,
        open_positions: List[PositionState],
        daily_pnl: float,
        consecutive_losses: int
    ) -> RiskAssessment:
        """
        계좌 전체 리스크 평가
        
        Args:
            account_equity: 계좌 자본
            open_positions: 열린 포지션 리스트
            daily_pnl: 당일 손익
            consecutive_losses: 연속 손실 횟수
            
        Returns:
            RiskAssessment
            
        제한 조건:
            - 일일 손실 > 2% → 거래 중단
            - 연속 손실 >= 3회 → 거래 중단
            - MDD > 3% → 레버리지 축소 또는 거래 중단
        """
        pass
```

### 8.3 구현 클래스
```python
class DefaultRiskManager(RiskManager):
    """기본 리스크 관리 구현"""
    
    def __init__(self):
        self._position_history: Dict[str, List[PositionState]] = {}
        self._daily_trades: List[Dict] = []
    
    # 메서드 구현...
```

---

## 9. ExecutionAdapter (주문 실행)

### 9.1 책임
- Binance API 주문 실행 래퍼
- 재시도 정책 (네트워크 오류, 타임스탬프 오류)
- 체결 결과 검증 및 슬리피지 기록

### 9.2 인터페이스
```python
from typing import Optional, Dict
from abc import ABC, abstractmethod

class ExecutionAdapter(ABC):
    """주문 실행 어댑터"""
    
    @abstractmethod
    def prepare_market_order(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        quantity: float,
        reduce_only: bool = False
    ) -> Dict[str, any]:
        """
        시장가 주문 준비 (검증)
        
        Args:
            symbol: 심볼
            side: 주문 방향
            quantity: 수량
            reduce_only: 포지션 축소 전용
            
        Returns:
            {
                "ok": bool,
                "validated_quantity": float,
                "expected_price": float,
                "reason": str (실패 시)
            }
        """
        pass
    
    @abstractmethod
    def execute_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool = False,
        max_retries: int = 3
    ) -> OrderResult:
        """
        시장가 주문 실행
        
        Args:
            symbol: 심볼
            side: "BUY" or "SELL"
            quantity: 수량
            reduce_only: 포지션 축소 전용
            max_retries: 최대 재시도 횟수
            
        Returns:
            OrderResult
            
        재시도 정책:
            - 네트워크 타임아웃: 지수 백오프 (1s, 2s, 4s)
            - -1021 (타임스탬프 오류): 서버 시간 재동기화 후 1회 재시도
            - 기타 오류: 즉시 실패 반환
        """
        pass
    
    @abstractmethod
    def close_position(
        self,
        symbol: str,
        position: PositionState
    ) -> OrderResult:
        """
        포지션 청산 (시장가)
        
        Args:
            symbol: 심볼
            position: 포지션 상태
            
        Returns:
            OrderResult
        """
        pass
    
    @abstractmethod
    def set_leverage(
        self,
        symbol: str,
        leverage: int
    ) -> bool:
        """
        레버리지 설정
        
        Args:
            symbol: 심볼
            leverage: 레버리지 배수
            
        Returns:
            성공 여부
        """
        pass
    
    @abstractmethod
    def set_margin_type(
        self,
        symbol: str,
        isolated: bool = True
    ) -> bool:
        """
        마진 타입 설정
        
        Args:
            symbol: 심볼
            isolated: ISOLATED(True) or CROSSED(False)
            
        Returns:
            성공 여부
        """
        pass
```

### 9.3 구현 클래스
```python
class BinanceExecutionAdapter(ExecutionAdapter):
    """Binance API 주문 실행 구현"""
    
    def __init__(self, binance_client: BinanceClient):
        self.client = binance_client
        self._execution_log: List[OrderResult] = []
    
    # 메서드 구현...
```

---

## 10. StrategyOrchestrator (전략 조율)

### 10.1 책임
- 메인 실행 루프 관리
- 모듈 간 데이터 흐름 조율
- 이벤트 생성 및 GUI/API 전달

### 10.2 인터페이스
```python
from typing import Callable, Optional, Dict, List
import threading

class StrategyOrchestrator:
    """전략 조율자 (메인 루프)"""
    
    def __init__(
        self,
        data_fetcher: DataFetcher,
        market_cache: MarketDataCache,
        indicator_engine: IndicatorEngine,
        signal_engine: SignalEngine,
        position_sizer: PositionSizer,
        risk_manager: RiskManager,
        execution_adapter: ExecutionAdapter
    ):
        self.data_fetcher = data_fetcher
        self.market_cache = market_cache
        self.indicator_engine = indicator_engine
        self.signal_engine = signal_engine
        self.position_sizer = position_sizer
        self.risk_manager = risk_manager
        self.execution_adapter = execution_adapter
        
        self._profiles: Dict[str, 'StrategyProfile'] = {}
        self._positions: Dict[str, PositionState] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def add_profile(self, name: str, profile: 'StrategyProfile') -> None:
        """전략 프로파일 추가"""
        pass
    
    def start(self) -> bool:
        """전략 실행 시작"""
        pass
    
    def stop(self) -> bool:
        """전략 정지"""
        pass
    
    def _tick_loop(self) -> None:
        """
        메인 루프 (1초 간격)
        
        흐름:
            1. 데이터 수집 (DataFetcher)
            2. 캐시 업데이트 (MarketDataCache)
            3. 지표 계산 (IndicatorEngine)
            4. 신호 평가 (SignalEngine)
            5. 리스크 평가 (RiskManager)
            6. 주문 실행 (ExecutionAdapter)
            7. 상태 저장 (PersistenceManager)
        """
        pass
    
    def on_event(self, callback: Callable[[str, Dict], None]) -> None:
        """이벤트 콜백 등록 (GUI/API 연동)"""
        pass
```

---

## 11. 모듈 의존성 다이어그램

```
┌─────────────────────────────────────────┐
│      StrategyOrchestrator (루프)       │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌─────────┐  ┌─────────┐  ┌──────────┐
│ Signal  │  │  Risk   │  │Execution │
│ Engine  │  │ Manager │  │ Adapter  │
└────┬────┘  └────┬────┘  └────┬─────┘
     │            │             │
     └────────────┼─────────────┘
                  │
          ┌───────┴───────┐
          │               │
          ▼               ▼
    ┌──────────┐    ┌──────────┐
    │Indicator │    │ Position │
    │  Engine  │    │  Sizer   │
    └─────┬────┘    └─────┬────┘
          │               │
          └───────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │ MarketDataCache│
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │  DataFetcher   │
         └────────┬───────┘
                  │
                  ▼
         ┌────────────────┐
         │ BinanceClient  │
         │ (Infrastructure)│
         └────────────────┘
```

---

## 12. 예외 처리 전략

### 12.1 예외 계층
```python
class StrategyError(Exception):
    """전략 관련 기본 예외"""
    pass

class APIError(StrategyError):
    """API 호출 실패"""
    pass

class ValidationError(StrategyError):
    """데이터 검증 실패"""
    pass

class InsufficientDataError(StrategyError):
    """데이터 부족"""
    pass

class OrderExecutionError(StrategyError):
    """주문 실행 실패"""
    pass

class RiskLimitExceeded(StrategyError):
    """리스크 한도 초과"""
    pass
```

### 12.2 예외 처리 규칙
- 복구 가능: 재시도 로직 적용 (네트워크, 타임스탬프)
- 복구 불가능: 로그 기록 후 상위 전파 (잘못된 파라미터, 계좌 부족)
- 치명적: 전략 중단 (연속 오류, 리스크 한도)

---

## 13. 로깅 및 모니터링

### 13.1 로그 카테고리
- `data`: 데이터 수집 관련
- `indicator`: 지표 계산 관련
- `signal`: 신호 생성 관련
- `risk`: 리스크 관리 관련
- `execution`: 주문 실행 관련
- `error`: 오류 발생
- `performance`: 성능 메트릭

### 13.2 메트릭 수집
```python
class MetricsCollector:
    """성능 메트릭 수집"""
    
    def record_trade(self, trade_info: Dict) -> None:
        """거래 기록"""
        pass
    
    def get_summary(self) -> Dict:
        """
        통계 요약
        
        Returns:
            {
                "total_trades": int,
                "win_rate": float,
                "avg_pnl": float,
                "sharpe_ratio": float,
                "max_drawdown": float,
                ...
            }
        """
        pass
```

---

## 14. 다음 단계

- [x] 모듈 인터페이스 설계 완료
- [ ] 백테스트 하니스 계약 정의
- [ ] StrategyProfile 스키마 작성
- [ ] 구현 시작 (DataFetcher → IndicatorEngine → ...)

---

**변경 이력:**
- 2025-11-18: 초안 작성 (모든 핵심 모듈 인터페이스 정의 완료)
