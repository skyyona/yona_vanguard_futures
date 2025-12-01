"""공통 데이터 구조 정의"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


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
    trades_count: int = 0


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
    triggers: List[str]  # 발동된 조건 목록
    reason: str  # 신호 발생 이유 설명


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
    fills: Optional[List[OrderFill]] = None
    timestamp: Optional[int] = None
    filter_meta: Optional[Dict[str, Any]] = None
    
    # 오류 정보
    error_code: Optional[int] = None
    error_message: Optional[str] = None
    
    # 슬리피지
    expected_price: Optional[float] = None
    slippage_pct: Optional[float] = None


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


# 예외 클래스
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
