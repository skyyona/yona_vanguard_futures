from sqlalchemy import Column, Integer, String, Float, BigInteger, Text, Index, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime


Base = declarative_base()


class Kline(Base):
    __tablename__ = "klines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False)
    interval = Column(String(16), nullable=False)
    open_time = Column(BigInteger, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    close_time = Column(BigInteger, nullable=False)
    quote_asset_volume = Column(Float)
    number_of_trades = Column(Integer)
    taker_buy_base_asset_volume = Column(Float)
    taker_buy_quote_asset_volume = Column(Float)
    ignore = Column(Float)

    __table_args__ = (
        Index("ix_klines_symbol_interval_open_time", "symbol", "interval", "open_time", unique=True),
    )


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True)
    strategy_name = Column(String(128), nullable=False)
    symbol = Column(String(32), nullable=False)
    interval = Column(String(16), nullable=False)
    start_time = Column(BigInteger, nullable=False)
    end_time = Column(BigInteger, nullable=False)
    initial_balance = Column(Float, nullable=False)
    final_balance = Column(Float, nullable=False)
    profit_percentage = Column(Float)
    max_drawdown = Column(Float)
    total_trades = Column(Integer)
    win_rate = Column(Float)
    parameters = Column(Text)
    created_at = Column(BigInteger, default=lambda: int(datetime.utcnow().timestamp()))

    __table_args__ = (
        Index("ix_backtest_results_run_id", "run_id", unique=True),
    )


class StrategyParameterSet(Base):
    """분석된 전략 파라미터 세트.

    단일 심볼/인터벌에 대한 백테스트/전략 분석 결과를 영구 저장합니다.
    실제 필드는 JSON 문자열로 직렬화된 파라미터를 포함합니다.
    """

    __tablename__ = "strategy_parameter_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False)
    interval = Column(String(16), nullable=False)
    engine_hint = Column(String(32), nullable=True)
    parameters = Column(Text, nullable=False)
    source = Column(String(32), nullable=True)
    note = Column(String(255), nullable=True)
    created_at = Column(BigInteger, default=lambda: int(datetime.utcnow().timestamp()))

    __table_args__ = (
        Index("ix_strategy_params_symbol_interval", "symbol", "interval"),
    )


class StrategyAssignment(Base):
    """엔진 할당 정보.

    하나의 심볼은 하나의 엔진에만 할당되도록 (symbol UNIQUE) 제약을 둡니다.
    parameter_set_id 는 StrategyParameterSet 을 참조합니다.
    """

    __tablename__ = "strategy_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False)
    engine = Column(String(32), nullable=False)
    parameter_set_id = Column(Integer, ForeignKey("strategy_parameter_sets.id"), nullable=False)
    assigned_at = Column(BigInteger, default=lambda: int(datetime.utcnow().timestamp()))
    assigned_by = Column(String(64), nullable=True)
    note = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ux_strategy_assignments_symbol", "symbol", unique=True),
        Index("ix_strategy_assignments_engine_symbol", "engine", "symbol"),
    )
