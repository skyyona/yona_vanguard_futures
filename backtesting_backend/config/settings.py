from pydantic import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "backtesting_backend"
    DB_FILE: str = "backtesting_backend.db"
    DATABASE_URL: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


def get_settings() -> Settings:
    return Settings()
