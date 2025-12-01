import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

def configure_logging():
    project_root = os.path.dirname(os.path.dirname(__file__))
    env_path = os.path.join(project_root, ".env")
    load_dotenv(env_path)

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)

    logger = logging.getLogger("backtest")
    logger.setLevel(numeric_level)

    if not logger.handlers:
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(numeric_level)
        fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        ch.setFormatter(fmt)
        logger.addHandler(ch)

        # File handler
        logs_dir = os.path.join(project_root, "..", "logs")
        logs_dir = os.path.abspath(logs_dir)
        os.makedirs(logs_dir, exist_ok=True)
        fh_path = os.path.join(logs_dir, "backtest_app.log")
        fh = RotatingFileHandler(fh_path, maxBytes=10 * 1024 * 1024, backupCount=5)
        fh.setLevel(numeric_level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# instantiate module-level logger for import
logger = configure_logging()
