from typing import List, Optional
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backtesting_backend.database import models
from backtesting_backend.database.db_manager import BacktestDB


class KlineRepository:
	def __init__(self, session_factory=None):
		# session_factory is a callable returning AsyncSession
		self._session_factory = session_factory or BacktestDB.get_instance().get_session

	async def create_kline(self, kline_data: dict) -> models.Kline:
		async with self._session_factory() as session:  # type: AsyncSession
			async with session.begin():
				k = models.Kline(**kline_data)
				session.add(k)
				return k

	async def bulk_insert_klines(self, klines_data: List[dict]) -> None:
		if not klines_data:
			return
		async with self._session_factory() as session:
			async with session.begin():
				stmt = insert(models.Kline).prefix_with("OR IGNORE")
				try:
					await session.execute(stmt, klines_data)
				except IntegrityError:
					# fallback: insert one by one to avoid failing entire batch
					for kd in klines_data:
						try:
							await session.execute(insert(models.Kline).values(**kd))
						except IntegrityError:
							continue

	async def get_klines_in_range(self, symbol: str, interval: str, start_time: int, end_time: int) -> List[models.Kline]:
		async with self._session_factory() as session:
			stmt = select(models.Kline).where(
				models.Kline.symbol == symbol,
				models.Kline.interval == interval,
				models.Kline.open_time >= start_time,
				models.Kline.open_time <= end_time,
			).order_by(models.Kline.open_time)
			res = await session.execute(stmt)
			return res.scalars().all()

	async def get_latest_kline_time(self, symbol: str, interval: str) -> Optional[int]:
		async with self._session_factory() as session:
			stmt = select(models.Kline.open_time).where(
				models.Kline.symbol == symbol,
				models.Kline.interval == interval,
			).order_by(models.Kline.open_time.desc()).limit(1)
			res = await session.execute(stmt)
			row = res.scalar_one_or_none()
			return row

	async def get_earliest_kline_time(self, symbol: str, interval: str) -> Optional[int]:
		"""Return earliest `open_time` (int) for `symbol`+`interval`, or None if not present."""
		async with self._session_factory() as session:
			stmt = select(models.Kline.open_time).where(
				models.Kline.symbol == symbol,
				models.Kline.interval == interval,
			).order_by(models.Kline.open_time.asc()).limit(1)
			res = await session.execute(stmt)
			row = res.scalar_one_or_none()
			return row

