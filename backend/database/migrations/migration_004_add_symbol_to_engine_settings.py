"""마이그레이션 004: engine_settings 테이블에 symbol 컬럼 추가"""
import aiosqlite

VERSION = 4
DESCRIPTION = "engine_settings 테이블에 symbol 컬럼 추가"


async def up(db: aiosqlite.Connection):
    """마이그레이션 실행"""
    # symbol 컬럼 추가 (기본값 BTCUSDT)
    await db.execute("""
        ALTER TABLE engine_settings 
        ADD COLUMN symbol TEXT NOT NULL DEFAULT 'BTCUSDT'
    """)


async def down(db: aiosqlite.Connection):
    """마이그레이션 롤백"""
    # SQLite는 컬럼 삭제를 직접 지원하지 않으므로 테이블 재생성 필요
    await db.execute("""
        CREATE TABLE engine_settings_backup AS 
        SELECT engine_name, designated_funds, applied_leverage, 
               funds_percent, updated_at_utc, created_at_utc
        FROM engine_settings
    """)
    await db.execute("DROP TABLE engine_settings")
    await db.execute("""
        ALTER TABLE engine_settings_backup 
        RENAME TO engine_settings
    """)
