from typing import Optional, List, Dict, Any
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backtesting_backend.database import models
from backtesting_backend.database.db_manager import BacktestDB


class StrategyParameterRepository:
    """Repository for StrategyParameterSet records."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory or BacktestDB.get_instance().get_session

    async def create_parameter_set(
        self,
        symbol: str,
        interval: str,
        parameters: Dict[str, Any],
        engine_hint: str | None = None,
        source: str | None = None,
        note: str | None = None,
    ) -> models.StrategyParameterSet:
        async with self._session_factory() as session:  # type: AsyncSession
            async with session.begin():
                rec = models.StrategyParameterSet(
                    symbol=symbol,
                    interval=interval,
                    engine_hint=engine_hint,
                    parameters=json.dumps(parameters or {}),
                    source=source,
                    note=note,
                )
                session.add(rec)
                return rec

    async def get_by_id(self, param_id: int) -> Optional[models.StrategyParameterSet]:
        async with self._session_factory() as session:
            stmt = select(models.StrategyParameterSet).where(models.StrategyParameterSet.id == param_id)
            res = await session.execute(stmt)
            return res.scalars().first()

    async def get_latest_for_symbol_interval(
        self, symbol: str, interval: str
    ) -> Optional[models.StrategyParameterSet]:
        async with self._session_factory() as session:
            stmt = (
                select(models.StrategyParameterSet)
                .where(
                    models.StrategyParameterSet.symbol == symbol,
                    models.StrategyParameterSet.interval == interval,
                )
                .order_by(models.StrategyParameterSet.created_at.desc())
            )
            res = await session.execute(stmt)
            return res.scalars().first()

    async def list_for_symbol(self, symbol: str) -> List[models.StrategyParameterSet]:
        async with self._session_factory() as session:
            stmt = (
                select(models.StrategyParameterSet)
                .where(models.StrategyParameterSet.symbol == symbol)
                .order_by(models.StrategyParameterSet.created_at.desc())
            )
            res = await session.execute(stmt)
            return res.scalars().all()
