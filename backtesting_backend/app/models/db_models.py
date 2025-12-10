from sqlalchemy import Column, Integer, String, Float, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy = Column(String(100))
    symbol = Column(String(50))
    result_summary = Column(Text)


class BacktestEvent(Base):
    __tablename__ = "backtest_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer)
    event_type = Column(String(50))
    price = Column(Float)
    metadata = Column(Text)
