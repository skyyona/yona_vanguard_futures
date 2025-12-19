import os
from typing import AsyncGenerator
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backtesting_backend.database import models
from backtesting_backend.core.logger import logger


class BacktestDB:
    """Singleton DB manager for backtesting backend."""

    _instance = None

    def __init__(self):
        # load environment from project .env if present
        project_root = os.path.dirname(os.path.dirname(__file__))
        env_path = os.path.join(project_root, ".env")
        load_dotenv(env_path)

        # Default DB location is inside the backtesting_backend package directory
        default_db = os.path.join(project_root, "yona_backtest.db")
        db_path = os.environ.get("DB_PATH", default_db)

        # ensure directory exists for the chosen DB path
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        # Use absolute path to avoid surprises from different CWDs
        db_path = os.path.abspath(db_path)
        self.database_url = f"sqlite+aiosqlite:///{db_path}"
        # Log the resolved DB path/url for visibility at startup
        try:
            logger.info("Backtest DB path resolved: %s", db_path)
            logger.info("Backtest DB URL: %s", self.database_url)
        except Exception:
            # avoid failing init if logging has issues
            pass
        self.engine = None
        self.async_session = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = BacktestDB()
        return cls._instance

    async def init(self) -> None:
        if self.engine is None:
            # echo can be enabled for debugging
            self.engine = create_async_engine(self.database_url, echo=False, future=True)
            self.async_session = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

            # create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(models.Base.metadata.create_all)

    def get_session(self) -> AsyncSession:
        if self.async_session is None:
            raise RuntimeError("DB not initialized. Call BacktestDB.get_instance().init() first.")
        return self.async_session()

    async def close(self) -> None:
        if self.engine:
            await self.engine.dispose()
