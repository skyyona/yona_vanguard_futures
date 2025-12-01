from typing import Optional, List
import asyncio
import logging

import pandas as pd

from backtesting_backend.api_client.binance_client import BinanceClient
from backtesting_backend.database.repositories.kline_repository import KlineRepository
from backtesting_backend.core.logger import logger


class DataLoader:
    def __init__(self, binance_client: Optional[BinanceClient] = None, kline_repo: Optional[KlineRepository] = None):
        self.client = binance_client or BinanceClient()
        self.kline_repo = kline_repo or KlineRepository()
        self._lock = asyncio.Lock()

    async def load_historical_klines(self, symbol: str, interval: str, start_time: int, end_time: int) -> None:
        """Ensure DB has klines for the given range; fetch missing parts from Binance."""
        async with self._lock:
            try:
                # check latest kline time in DB
                latest = await self.kline_repo.get_latest_kline_time(symbol, interval)
                fetch_start = start_time
                if latest is not None and latest >= start_time:
                    fetch_start = latest + 1

                if fetch_start > end_time:
                    logger.info("Data already present for %s %s %s-%s", symbol, interval, start_time, end_time)
                    return

                # fetch from Binance in pages
                klines = await self.client.get_klines(symbol, interval, start_time=fetch_start, end_time=end_time)
                if klines:
                    # convert to list of dicts acceptable to repo
                    await self.kline_repo.bulk_insert_klines(klines)
                    logger.info("Inserted %d klines for %s %s", len(klines), symbol, interval)
            except Exception as e:
                logger.exception("Failed to load historical klines: %s", e)
                raise

    async def get_klines_for_backtest(self, symbol: str, interval: str, start_time: int, end_time: int) -> pd.DataFrame:
        """Return klines for the given range as a pandas DataFrame."""
        rows = await self.kline_repo.get_klines_in_range(symbol, interval, start_time, end_time)
        if not rows:
            # try to fetch if missing
            await self.load_historical_klines(symbol, interval, start_time, end_time)
            rows = await self.kline_repo.get_klines_in_range(symbol, interval, start_time, end_time)

        # convert SQLAlchemy model instances or dicts to DataFrame
        data = []
        for r in rows:
            if hasattr(r, "__dict__"):
                d = {k: getattr(r, k) for k in r.__dict__ if not k.startswith("_")}
            else:
                d = dict(r)
            data.append(d)

        df = pd.DataFrame(data)
        if df.empty:
            return df

        # Ensure open_time is sorted and set index
        df = df.sort_values(by="open_time")
        # convert to timestamps index if needed
        return df
