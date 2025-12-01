"""마이그레이션 004: 전역 앱 설정 테이블 추가"""
import aiosqlite

VERSION = 4
DESCRIPTION = "전역 앱 설정 테이블 추가"


async def up(db: aiosqlite.Connection):
    """마이그레이션 실행"""
    # app_settings 테이블 생성
    await db.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            value_type TEXT NOT NULL DEFAULT 'string',
            updated_at_utc TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        )
    """)


async def down(db: aiosqlite.Connection):
    """마이그레이션 롤백"""
    await db.execute("DROP TABLE IF EXISTS app_settings")


