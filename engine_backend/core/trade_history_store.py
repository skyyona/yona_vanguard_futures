"""SQLite-backed trade history store for Engine Backend.

This module provides simple helpers to insert and delete trade history records
in the engine backend's local SQLite database.
"""
from __future__ import annotations

from typing import Optional
import time

from engine_backend.db.manager import get_conn


def insert_trade_record(
    engine_name: str,
    symbol: str,
    trade_datetime: str,
    funds: float,
    leverage: int,
    profit_loss: float,
    pnl_percent: float,
    entry_price: Optional[float] = None,
    exit_price: Optional[float] = None,
    position_side: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Insert a single trade history record into the local SQLite DB."""

    created_at_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO trade_history (
            engine_name, symbol, trade_datetime, funds, leverage,
            profit_loss, pnl_percent, entry_price, exit_price,
            position_side, created_at_utc
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            engine_name,
            symbol,
            trade_datetime,
            float(funds),
            int(leverage),
            float(profit_loss),
            float(pnl_percent),
            entry_price,
            exit_price,
            position_side,
            created_at_utc,
        ),
    )
    conn.commit()
    conn.close()


def delete_all_trade_history(db_path: Optional[str] = None) -> None:
    """Delete all rows from trade_history table.

    This is intended to be called from a privileged internal API only.
    """

    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM trade_history;")
    conn.commit()
    conn.close()


def delete_trade_history_for_engine(engine_name: str, db_path: Optional[str] = None) -> None:
    """Delete trade history rows for a specific engine.

    Used when the caller wants to wipe history only for a single
    engine (e.g., Alpha/Beta/Gamma) instead of clearing the entire
    table.
    """

    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM trade_history WHERE engine_name = ?;", (engine_name,))
    conn.commit()
    conn.close()
