"""Migration 001: create orders table (skeleton migration).
This file is a template and should be adapted to your migration runner (alembic / custom).
"""
def up(db):
    db.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        idempotency_key TEXT,
        engine_name TEXT NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        type TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL,
        reduce_only BOOLEAN DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'PENDING',
        exchange_order_id TEXT,
        raw_response TEXT,
        created_at_utc TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL
    );
    ''')

def down(db):
    db.execute('DROP TABLE IF EXISTS orders;')
