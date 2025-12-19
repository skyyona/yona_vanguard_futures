"""DB-backed order store using sqlite3."""
from typing import Dict, Any, Optional
import time
import uuid
from engine_backend.db.manager import get_conn


def persist_order(order: Dict[str, Any], db_path: Optional[str] = None) -> str:
    """Persist order to sqlite and return generated id."""
    order_id = order.get("id") or str(uuid.uuid4())
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO orders (id, idempotency_key, engine_name, symbol, side, type, quantity, price, reduce_only, status, created_at_utc, updated_at_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            order.get("idempotency_key"),
            order.get("engine"),
            order.get("symbol"),
            order.get("side"),
            order.get("type"),
            float(order.get("quantity") or 0),
            order.get("price"),
            1 if order.get("reduceOnly") else 0,
            order.get("status", "PENDING"),
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return order_id


def get_order(order_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def update_order(order_id: str, fields: Dict[str, Any], db_path: Optional[str] = None) -> None:
    if not fields:
        return
    conn = get_conn(db_path)
    cur = conn.cursor()
    sets = []
    values = []
    for k, v in fields.items():
        sets.append(f"{k} = ?")
        values.append(v)
    # update timestamp
    sets.append("updated_at_utc = ?")
    values.append(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    values.append(order_id)
    sql = f"UPDATE orders SET {', '.join(sets)} WHERE id = ?"
    cur.execute(sql, tuple(values))
    conn.commit()
    conn.close()
