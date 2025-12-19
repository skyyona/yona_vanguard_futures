"""DB-backed store for assigned strategies in engine backend.

This persists STRATEGY_ASSIGNED events into the local sqlite DB so that
the trading engine can later load per-symbol configurations.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List
import json
import time

from engine_backend.db.manager import get_conn


def upsert_strategy(config: Dict[str, Any], db_path: Optional[str] = None) -> int:
    """Insert or update strategy config for a symbol.

    Expected keys in `config`:
      - symbol, interval, engine, parameter_set_id, parameters, assigned_at, assigned_by, note
    """

    symbol = config.get("symbol")
    interval = config.get("interval")
    engine_name = config.get("engine") or config.get("engine_name")
    parameter_set_id = config.get("parameter_set_id")
    params = config.get("parameters") or {}
    assigned_by = config.get("assigned_by")
    note = config.get("note")

    if not symbol or not interval or not engine_name:
        raise ValueError("symbol, interval, and engine are required to upsert strategy")

    assigned_at_ms = int(config.get("assigned_at") or 0)
    if assigned_at_ms <= 0:
        assigned_at_ms = int(time.time() * 1000)

    assigned_at_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(assigned_at_ms / 1000.0))
    params_json = json.dumps(params or {})

    conn = get_conn(db_path)
    cur = conn.cursor()

    # Try update first (symbol UNIQUE)
    cur.execute(
        """
        UPDATE strategies
        SET interval = ?, engine_name = ?, parameter_set_id = ?, parameters_json = ?,
            assigned_at_utc = ?, assigned_by = ?, note = ?
        WHERE symbol = ?
        """,
        (
            interval,
            engine_name,
            parameter_set_id,
            params_json,
            assigned_at_utc,
            assigned_by,
            note,
            symbol,
        ),
    )
    if cur.rowcount == 0:
        # insert new
        cur.execute(
            """
            INSERT INTO strategies (
                symbol, interval, engine_name, parameter_set_id, parameters_json,
                assigned_at_utc, assigned_by, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                interval,
                engine_name,
                parameter_set_id,
                params_json,
                assigned_at_utc,
                assigned_by,
                note,
            ),
        )

    conn.commit()
    # Return rowid of the last operation (useful for debugging)
    rowid = cur.lastrowid
    conn.close()
    return int(rowid or 0)


def get_strategy(symbol: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM strategies WHERE symbol = ?", (symbol,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None

    d = dict(row)
    try:
        d["parameters"] = json.loads(d.get("parameters_json") or "{}")
    except Exception:
        d["parameters"] = {}
    return d


def list_strategies_for_engine(engine_name: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM strategies WHERE engine_name = ? ORDER BY symbol", (engine_name,))
    rows = cur.fetchall()
    conn.close()
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            d["parameters"] = json.loads(d.get("parameters_json") or "{}")
        except Exception:
            d["parameters"] = {}
        out.append(d)
    return out


def list_all_strategies(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all strategies regardless of engine, ordered by symbol.

    Trading loop can use this to iterate configured symbols.
    """
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM strategies ORDER BY symbol")
    rows = cur.fetchall()
    conn.close()
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            d["parameters"] = json.loads(d.get("parameters_json") or "{}")
        except Exception:
            d["parameters"] = {}
        out.append(d)
    return out

