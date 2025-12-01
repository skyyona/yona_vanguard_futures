from sqlalchemy import Column, Integer, String, Float, BigInteger, Text, Index
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
