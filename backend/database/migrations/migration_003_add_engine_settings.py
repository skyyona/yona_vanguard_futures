"""마이그레이션 003: 엔진 설정 테이블 추가"""
import aiosqlite

VERSION = 3
DESCRIPTION = "엔진 설정 테이블 추가"


async def up(db: aiosqlite.Connection):
    """마이그레이션 실행"""
    # engine_settings 테이블 생성
    await db.execute("""
        CREATE TABLE IF NOT EXISTS engine_settings (
            engine_name TEXT PRIMARY KEY,
            designated_funds REAL NOT NULL DEFAULT 0.0,
            applied_leverage INTEGER NOT NULL DEFAULT 1,
            funds_percent REAL NOT NULL DEFAULT 0.0,
            updated_at_utc TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        )
    """)


async def down(db: aiosqlite.Connection):
    """마이그레이션 롤백"""
    await db.execute("DROP TABLE IF EXISTS engine_settings")


