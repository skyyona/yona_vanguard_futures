from typing import List, Optional
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from backtesting_backend.database import models
from backtesting_backend.database.db_manager import BacktestDB


class BacktestResultRepository:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory or BacktestDB.get_instance().get_session

    async def create_backtest_result(self, result_data: dict) -> models.BacktestResult:
        async with self._session_factory() as session:  # type: AsyncSession
            async with session.begin():
                r = models.BacktestResult(**result_data)
                session.add(r)
                return r

    async def get_backtest_result_by_run_id(self, run_id: str) -> Optional[models.BacktestResult]:
        async with self._session_factory() as session:
            stmt = select(models.BacktestResult).where(models.BacktestResult.run_id == run_id)
            res = await session.execute(stmt)
            return res.scalars().first()

    async def get_all_backtest_results(self) -> List[models.BacktestResult]:
        async with self._session_factory() as session:
            stmt = select(models.BacktestResult).order_by(models.BacktestResult.created_at.desc())
            res = await session.execute(stmt)
            return res.scalars().all()

    async def update_backtest_result(self, run_id: str, updates: dict) -> Optional[models.BacktestResult]:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = select(models.BacktestResult).where(models.BacktestResult.run_id == run_id)
                res = await session.execute(stmt)
                r = res.scalars().first()
                if not r:
                    return None
                for k, v in updates.items():
                    if hasattr(r, k):
                        setattr(r, k, v)
                await session.flush()
                return r
