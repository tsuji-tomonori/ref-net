"""データベース接続管理."""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from refnet_shared.config import settings
from refnet_shared.exceptions import DatabaseError
from refnet_shared.models.database import Base
from refnet_shared.utils import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """データベース接続管理クラス."""

    def __init__(self, database_url: str | None = None):
        """初期化."""
        self.database_url = database_url or settings.database.url

        # SQLAlchemy エンジン設定
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.debug,  # デバッグ時にSQLログを出力
        )

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def create_tables(self) -> None:
        """テーブル作成."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error("Failed to create database tables", error=str(e))
            raise DatabaseError(f"Failed to create tables: {str(e)}") from e

    def drop_tables(self) -> None:
        """テーブル削除."""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error("Failed to drop database tables", error=str(e))
            raise DatabaseError(f"Failed to drop tables: {str(e)}") from e

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """セッション取得."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Database session error", error=str(e))
            raise DatabaseError(f"Database operation failed: {str(e)}") from e
        finally:
            session.close()

    def health_check(self) -> dict[str, Any]:
        """データベースヘルスチェック."""
        try:
            with self.get_session() as session:
                result = session.execute(text("SELECT 1")).scalar()
                if result == 1:
                    # Try to get pool info, but handle if it's not available (e.g., SQLite)
                    pool_info = {}
                    try:
                        if hasattr(self.engine.pool, 'size') and callable(self.engine.pool.size):
                            pool_info["engine_pool_size"] = self.engine.pool.size()
                        elif hasattr(self.engine.pool, 'size'):
                            pool_info["engine_pool_size"] = self.engine.pool.size

                        if hasattr(self.engine.pool, 'checkedin') and callable(self.engine.pool.checkedin):
                            pool_info["engine_pool_checked_in"] = self.engine.pool.checkedin()
                        elif hasattr(self.engine.pool, 'checkedin'):
                            pool_info["engine_pool_checked_in"] = self.engine.pool.checkedin

                        if hasattr(self.engine.pool, 'checkedout') and callable(self.engine.pool.checkedout):
                            pool_info["engine_pool_checked_out"] = self.engine.pool.checkedout()
                        elif hasattr(self.engine.pool, 'checkedout'):
                            pool_info["engine_pool_checked_out"] = self.engine.pool.checkedout
                    except Exception:
                        # Pool info not available, skip it
                        pass

                    return {
                        "status": "healthy",
                        "database_url": self.database_url.split('@')[1] if '@' in self.database_url else "unknown",
                        **pool_info
                    }
                else:
                    return {"status": "unhealthy", "error": "Unexpected result from health check"}
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return {"status": "unhealthy", "error": str(e)}

    def get_table_stats(self) -> dict[str, int]:
        """テーブル統計情報取得."""
        stats = {}
        try:
            with self.get_session() as session:
                # 各テーブルの行数を取得
                for table_name in Base.metadata.tables.keys():
                    try:
                        count = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                        stats[table_name] = count or 0
                    except Exception as e:
                        logger.warning(f"Failed to get count for table {table_name}", error=str(e))
                        stats[table_name] = -1
        except Exception as e:
            logger.error("Failed to get table statistics", error=str(e))
            raise DatabaseError(f"Failed to get table stats: {str(e)}") from e

        return stats

    def vacuum_analyze(self) -> None:
        """データベースのVACUUM ANALYZE実行（PostgreSQL用）."""
        try:
            # autocommit=Trueでセッションを作成（VACUUM用）
            with self.engine.connect() as connection:
                connection.execute(text("VACUUM ANALYZE"))
            logger.info("Database VACUUM ANALYZE completed")
        except Exception as e:
            logger.error("VACUUM ANALYZE failed", error=str(e))
            raise DatabaseError(f"VACUUM ANALYZE failed: {str(e)}") from e

    def close(self) -> None:
        """データベース接続を閉じる."""
        try:
            self.engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error("Failed to close database connections", error=str(e))


# グローバルインスタンス
db_manager = DatabaseManager()
