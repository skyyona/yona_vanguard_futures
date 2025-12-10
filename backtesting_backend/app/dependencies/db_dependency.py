from typing import Generator, Optional
import os

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
except Exception:
    create_engine = None
    sessionmaker = None

from backtesting_backend.config.settings import Settings

def get_engine(db_path: Optional[str] = None):
    settings = Settings()
    db_url = db_path or settings.DATABASE_URL or f"sqlite:///{settings.DB_FILE}"
    if create_engine is None:
        raise RuntimeError("SQLAlchemy is required for DB dependency")
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return engine

def get_db() -> Generator:
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
