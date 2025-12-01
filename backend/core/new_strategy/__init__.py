"""새로운 모듈형 전략 패키지 (Option B)"""

from .data_structures import (
    Candle,
    IndicatorSet,
    SignalAction,
    SignalResult,
    PositionSide,
    PositionState,
    ExitReason,
    ExitSignal,
    OrderFill,
    OrderResult,
    RiskAssessment,
    StrategyError,
    APIError,
    ValidationError,
    InsufficientDataError,
    OrderExecutionError,
    RiskLimitExceeded,
)

from .data_fetcher import (
    MarketDataCache,
    BinanceDataFetcher,
)

from .indicator_engine import (
    IndicatorEngine,
)
from .signal_engine import (
    SignalEngine,
    SignalEngineConfig,
)
from .risk_manager import (
    RiskManager,
    RiskManagerConfig,
)
from .execution_adapter import (
    ExecutionAdapter,
    ExecutionRetryPolicy,
)
from .orchestrator import (
    StrategyOrchestrator,
    OrchestratorConfig,
)

__all__ = [
    # 데이터 구조
    "Candle",
    "IndicatorSet",
    "SignalAction",
    "SignalResult",
    "PositionSide",
    "PositionState",
    "ExitReason",
    "ExitSignal",
    "OrderFill",
    "OrderResult",
    "RiskAssessment",
    
    # 예외
    "StrategyError",
    "APIError",
    "ValidationError",
    "InsufficientDataError",
    "OrderExecutionError",
    "RiskLimitExceeded",
    
    # DataFetcher
    "MarketDataCache",
    "BinanceDataFetcher",
    
    # IndicatorEngine
    "IndicatorEngine",
    
    # SignalEngine
    "SignalEngine",
    "SignalEngineConfig",
    
    # RiskManager
    "RiskManager",
    "RiskManagerConfig",
    
    # ExecutionAdapter
    "ExecutionAdapter",
    "ExecutionRetryPolicy",

    # Orchestrator
    "StrategyOrchestrator",
    "OrchestratorConfig",
]
