import os
from dotenv import load_dotenv


class ConfigManager:
    """Simple config manager that loads env vars and exposes them as attrs."""

    def __init__(self, env_path: str | None = None):
        if env_path is None:
            project_root = os.path.dirname(os.path.dirname(__file__))
            env_path = os.path.join(project_root, ".env")
        load_dotenv(env_path)

        # Load values
        self.BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
        self.BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
        self.DB_PATH = os.getenv("DB_PATH", "./yona_backtest.db")
        self.FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
        self.FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8001"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        # New-listing related defaults
        # Number of days from first available kline to consider a coin "newly listed"
        self.NEW_LISTING_CUTOFF_DAYS = int(os.getenv("NEW_LISTING_CUTOFF_DAYS", "7"))
        # Minimum required 1m candles for running full analysis on new listings
        self.MIN_REQUIRED_CANDLES_FOR_ANALYSIS = int(os.getenv("MIN_REQUIRED_CANDLES_FOR_ANALYSIS", "60"))
        # Backtest minimum candles (legacy compatibility)
        self.SIM_MIN_CANDLES = int(os.getenv("SIM_MIN_CANDLES", "200"))

    def validate(self) -> None:
        missing = []
        # BINANCE keys optional for read-only historical data if not using signed endpoints
        # but warn if both missing
        if not (self.BINANCE_API_KEY and self.BINANCE_SECRET_KEY):
            # not raising, just warn by attribute; caller may handle
            pass

        if not self.DB_PATH:
            missing.append("DB_PATH")

        if missing:
            raise RuntimeError(f"Missing required config vars: {missing}")


# module-level default config
config = ConfigManager()
