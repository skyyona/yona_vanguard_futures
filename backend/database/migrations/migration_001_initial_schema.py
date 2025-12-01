"""마이그레이션 001: 초기 스키마 - schema_version 테이블 생성"""
import aiosqlite

VERSION = 1
DESCRIPTION = "초기 스키마 - schema_version 테이블 생성"


async def up(db: aiosqlite.Connection):
    """마이그레이션 실행"""
    # schema_version 테이블은 이미 initialize()에서 생성되므로
    # 여기서는 확인만 수행
    await db.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at_utc TEXT NOT NULL,
            description TEXT
        )
    """)


async def down(db: aiosqlite.Connection):
    """마이그레이션 롤백"""
    # schema_version 테이블은 삭제하지 않음 (다른 마이그레이션에 필요)
    pass


