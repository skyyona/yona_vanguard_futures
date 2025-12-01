"""데이터베이스 관리자 - 스키마 버전 관리 및 마이그레이션 실행"""
import aiosqlite
import os
import importlib.util
from typing import Optional, List, Dict, Any
from pathlib import Path
from backend.utils.logger import setup_logger

logger = setup_logger()


class DatabaseManager:
    """데이터베이스 스키마 버전 관리 및 마이그레이션 실행"""
    
    def __init__(self, db_path: str):
        """
        DatabaseManager 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self.migrations_dir = os.path.join(os.path.dirname(__file__), "migrations")
        
    async def initialize(self) -> None:
        """데이터베이스 초기화 및 마이그레이션 실행"""
        try:
            # 마이그레이션 디렉토리 확인
            if not os.path.exists(self.migrations_dir):
                os.makedirs(self.migrations_dir)
                # __init__.py 파일 생성
                init_file = os.path.join(self.migrations_dir, "__init__.py")
                if not os.path.exists(init_file):
                    with open(init_file, 'w') as f:
                        f.write('# Migrations package\n')
                logger.info(f"마이그레이션 디렉토리 생성: {self.migrations_dir}")
            
            # schema_version 테이블 생성 (없으면)
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at_utc TEXT NOT NULL,
                        description TEXT
                    )
                """)
                await db.commit()
                logger.info("schema_version 테이블 확인/생성 완료")
            
            # 마이그레이션 실행
            await self.run_migrations()
            
        except Exception as e:
            logger.error(f"데이터베이스 초기화 실패: {e}", exc_info=True)
            raise
    
    async def get_current_version(self) -> int:
        """현재 데이터베이스 버전 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT MAX(version) as max_version FROM schema_version"
                )
                row = await cur.fetchone()
                if row and row["max_version"] is not None:
                    return int(row["max_version"])
                return 0
        except Exception as e:
            logger.warning(f"현재 버전 조회 실패: {e}")
            return 0
    
    def get_available_migrations(self) -> List[int]:
        """사용 가능한 마이그레이션 파일 목록 조회"""
        migrations = []
        if not os.path.exists(self.migrations_dir):
            return migrations
        
        for file in os.listdir(self.migrations_dir):
            if file.startswith("migration_") and file.endswith(".py"):
                try:
                    # 파일명에서 버전 번호 추출 (migration_001_xxx.py -> 1)
                    version_str = file.split("_")[1]
                    version = int(version_str)
                    migrations.append(version)
                except (ValueError, IndexError):
                    logger.warning(f"마이그레이션 파일명 형식 오류: {file}")
                    continue
        
        return sorted(migrations)
    
    def load_migration_module(self, version: int):
        """마이그레이션 모듈 로드"""
        migration_file = os.path.join(
            self.migrations_dir, 
            f"migration_{version:03d}_*.py"
        )
        
        # 정확한 파일명 찾기
        migration_files = [
            f for f in os.listdir(self.migrations_dir)
            if f.startswith(f"migration_{version:03d}_") and f.endswith(".py")
        ]
        
        if not migration_files:
            raise FileNotFoundError(f"마이그레이션 파일을 찾을 수 없음: version {version}")
        
        migration_file = os.path.join(self.migrations_dir, migration_files[0])
        
        # 모듈 동적 로드
        spec = importlib.util.spec_from_file_location(
            f"migration_{version:03d}", migration_file
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"마이그레이션 모듈 로드 실패: {migration_file}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return module
    
    async def run_migrations(self) -> None:
        """사용 가능한 모든 마이그레이션 실행"""
        current_version = await self.get_current_version()
        available_migrations = self.get_available_migrations()
        
        # 아직 실행하지 않은 마이그레이션만 필터링
        pending_migrations = [v for v in available_migrations if v > current_version]
        
        if not pending_migrations:
            logger.info(f"마이그레이션 불필요 (현재 버전: {current_version})")
            return
        
        logger.info(f"마이그레이션 실행 시작 (현재 버전: {current_version}, 대상 버전: {max(pending_migrations)})")
        
        async with aiosqlite.connect(self.db_path) as db:
            for version in pending_migrations:
                try:
                    logger.info(f"마이그레이션 {version} 실행 중...")
                    migration_module = self.load_migration_module(version)
                    
                    # up 함수 실행
                    if not hasattr(migration_module, 'up'):
                        raise AttributeError(f"마이그레이션 {version}에 'up' 함수가 없습니다")
                    
                    await migration_module.up(db)
                    await db.commit()
                    
                    # 버전 기록
                    description = getattr(migration_module, 'DESCRIPTION', f'Migration {version}')
                    from datetime import datetime
                    applied_at = datetime.utcnow().isoformat()
                    
                    await db.execute(
                        "INSERT INTO schema_version (version, applied_at_utc, description) VALUES (?, ?, ?)",
                        (version, applied_at, description)
                    )
                    await db.commit()
                    
                    logger.info(f"마이그레이션 {version} 완료: {description}")
                    
                except Exception as e:
                    logger.error(f"마이그레이션 {version} 실행 실패: {e}", exc_info=True)
                    # 롤백 시도
                    try:
                        if hasattr(migration_module, 'down'):
                            await migration_module.down(db)
                            await db.commit()
                            logger.info(f"마이그레이션 {version} 롤백 완료")
                    except Exception as rollback_error:
                        logger.error(f"마이그레이션 {version} 롤백 실패: {rollback_error}")
                    
                    raise
    
    async def ensure_tables(self) -> None:
        """필수 테이블 존재 확인"""
        required_tables = [
            'schema_version',
            'yona_blacklist'
        ]
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            existing_tables = {row["name"] for row in await cur.fetchall()}
            
            missing_tables = set(required_tables) - existing_tables
            if missing_tables:
                logger.warning(f"누락된 테이블: {missing_tables}")
                # 마이그레이션 재실행 시도
                await self.run_migrations()
