from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backtesting_backend.database import models
from backtesting_backend.database.db_manager import BacktestDB


class StrategyAssignmentRepository:
    """Repository for StrategyAssignment records.

    Enforces the invariant that a symbol is assigned to at most one engine.
    """

    def __init__(self, session_factory=None):
        self._session_factory = session_factory or BacktestDB.get_instance().get_session

    async def upsert_assignment(
        self,
        symbol: str,
        engine: str,
        parameter_set_id: int,
        assigned_by: str | None = None,
        note: str | None = None,
    ) -> models.StrategyAssignment:
        async with self._session_factory() as session:  # type: AsyncSession
            async with session.begin():
                # 하나의 심볼에 대한 기존 할당이 있는지 확인
                stmt = select(models.StrategyAssignment).where(models.StrategyAssignment.symbol == symbol)
                res = await session.execute(stmt)
                existing = res.scalars().first()

                if existing is None:
                    rec = models.StrategyAssignment(
                        symbol=symbol,
                        engine=engine,
                        parameter_set_id=parameter_set_id,
                        assigned_by=assigned_by,
                        note=note,
                    )
                    session.add(rec)
                    return rec

                # 이미 다른 엔진에 할당된 경우, 정책에 따라 에러로 간주
                if existing.engine != engine:
                    raise ValueError(
                        f"symbol {symbol} is already assigned to engine {existing.engine}; unassign first."
                    )

                # 동일 엔진이면 파라미터셋만 교체 (재할당)
                existing.parameter_set_id = parameter_set_id
                if assigned_by is not None:
                    existing.assigned_by = assigned_by
                if note is not None:
                    existing.note = note
                await session.flush()
                return existing

    async def unassign_symbol(self, symbol: str) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                stmt = select(models.StrategyAssignment).where(models.StrategyAssignment.symbol == symbol)
                res = await session.execute(stmt)
                existing = res.scalars().first()
                if existing is not None:
                    await session.delete(existing)

    async def get_assignment_for_symbol(self, symbol: str) -> Optional[models.StrategyAssignment]:
        async with self._session_factory() as session:
            stmt = select(models.StrategyAssignment).where(models.StrategyAssignment.symbol == symbol)
            res = await session.execute(stmt)
            return res.scalars().first()

    async def list_assignments_for_engine(self, engine: str) -> List[models.StrategyAssignment]:
        async with self._session_factory() as session:
            stmt = (
                select(models.StrategyAssignment)
                .where(models.StrategyAssignment.engine == engine)
                .order_by(models.StrategyAssignment.assigned_at.desc())
            )
            res = await session.execute(stmt)
            return res.scalars().all()
