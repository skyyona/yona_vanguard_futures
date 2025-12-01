"""마이그레이션 002: 거래 기록 테이블 추가"""
import aiosqlite

VERSION = 2
DESCRIPTION = "거래 기록 테이블 추가"


async def up(db: aiosqlite.Connection):
    """마이그레이션 실행"""
    # trade_history 테이블 생성
    await db.execute("""
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
        )
    """)
    
    # 인덱스 생성
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_history_engine 
        ON trade_history(engine_name)
    """)
    
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_history_symbol 
        ON trade_history(symbol)
    """)
    
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_history_datetime 
        ON trade_history(trade_datetime)
    """)
    
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_history_created 
        ON trade_history(created_at_utc)
    """)


async def down(db: aiosqlite.Connection):
    """마이그레이션 롤백"""
    await db.execute("DROP INDEX IF EXISTS idx_trade_history_created")
    await db.execute("DROP INDEX IF EXISTS idx_trade_history_datetime")
    await db.execute("DROP INDEX IF EXISTS idx_trade_history_symbol")
    await db.execute("DROP INDEX IF EXISTS idx_trade_history_engine")
    await db.execute("DROP TABLE IF EXISTS trade_history")


