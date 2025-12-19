import os
import sqlite3
from typing import Optional

DB_FILE = os.environ.get("ENGINE_BACKEND_DB_PATH") or os.path.join(os.path.dirname(__file__), "orders.db")


def get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DB_FILE
    dirpath = os.path.dirname(path)
    if dirpath and not os.path.exists(dirpath):
        os.makedirs(dirpath, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        idempotency_key TEXT,
        engine_name TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        type TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL,
        reduce_only INTEGER DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'PENDING',
        exchange_order_id TEXT,
        raw_response TEXT,
        created_at_utc TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL
    );
    ''')
    # Table for assigned strategies per symbol/engine
    cur.execute('''
    CREATE TABLE IF NOT EXISTS strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        interval TEXT NOT NULL,
        engine_name TEXT NOT NULL,
        parameter_set_id INTEGER,
        parameters_json TEXT NOT NULL,
        assigned_at_utc TEXT NOT NULL,
        assigned_by TEXT,
        note TEXT,
        UNIQUE(symbol)
    );
    ''')
    # Table for per-engine settings (enable/disable, overrides, cooldown, etc.)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS engine_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engine_name TEXT NOT NULL UNIQUE,
        enabled INTEGER NOT NULL DEFAULT 1,
        max_position_usdt REAL,
        max_leverage INTEGER,
        cooldown_sec REAL,
        note TEXT,
        updated_at_utc TEXT NOT NULL
    );
    ''')
    # Table for per-trade history records (summary of closed positions)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS trade_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        engine_name TEXT NOT NULL,
        symbol TEXT NOT NULL,
        trade_datetime TEXT NOT NULL,
        funds REAL NOT NULL,
        leverage INTEGER NOT NULL,
        profit_loss REAL NOT NULL,
        pnl_percent REAL NOT NULL,
        entry_price REAL,
        exit_price REAL,
        position_side TEXT,
        created_at_utc TEXT NOT NULL
    );
    ''')
    # Helpful indexes for common query patterns
    cur.execute('''
    CREATE INDEX IF NOT EXISTS idx_trade_history_engine
    ON trade_history(engine_name);
    ''')
    cur.execute('''
    CREATE INDEX IF NOT EXISTS idx_trade_history_symbol
    ON trade_history(symbol);
    ''')
    cur.execute('''
    CREATE INDEX IF NOT EXISTS idx_trade_history_datetime
    ON trade_history(trade_datetime);
    ''')
    cur.execute('''
    CREATE INDEX IF NOT EXISTS idx_trade_history_created
    ON trade_history(created_at_utc);
    ''')
    # unique constraint for idempotency can be added separately
    conn.commit()
    conn.close()
