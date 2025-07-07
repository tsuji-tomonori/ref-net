"""マイグレーション管理ユーティリティ."""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from refnet_shared.config.environment import load_environment_settings
from refnet_shared.exceptions import DatabaseError
from refnet_shared.utils import get_logger

logger = get_logger(__name__)


class MigrationManager:
    """マイグレーション管理クラス."""

    def __init__(self, alembic_ini_path: str | None = None):
        """初期化."""
        if alembic_ini_path is None:
            # package/shared/alembic.ini のパスを取得
            current_dir = Path(__file__).parent
            # src/refnet_shared/utils -> src/refnet_shared -> src -> package/shared
            self.alembic_ini_path = current_dir.parent.parent.parent / "alembic.ini"
        else:
            self.alembic_ini_path = Path(alembic_ini_path)

        if not self.alembic_ini_path.exists():
            raise FileNotFoundError(f"Alembic config not found: {self.alembic_ini_path}")

        self.config = Config(str(self.alembic_ini_path))
        self.settings = load_environment_settings()

        # データベースURL設定
        self.config.set_main_option("sqlalchemy.url", self.settings.database.url)

    def create_migration(self, message: str, autogenerate: bool = True) -> str:
        """新しいマイグレーション作成."""
        try:
            logger.info(f"Creating migration: {message}")

            if autogenerate:
                command.revision(self.config, message=message, autogenerate=True)
            else:
                command.revision(self.config, message=message)

            # 最新のリビジョンIDを取得
            script_dir = ScriptDirectory.from_config(self.config)
            revision_id = script_dir.get_current_head()

            logger.info(f"Migration created with revision ID: {revision_id}")
            return revision_id or ""

        except Exception as e:
            logger.error(f"Failed to create migration: {e}")
            raise DatabaseError(f"Migration creation failed: {str(e)}") from e

    def run_migrations(self, revision: str = "head") -> None:
        """マイグレーション実行."""
        try:
            logger.info(f"Running migrations to: {revision}")
            command.upgrade(self.config, revision)
            logger.info("Migrations completed successfully")

        except Exception as e:
            logger.error(f"Failed to run migrations: {e}")
            raise DatabaseError(f"Migration execution failed: {str(e)}") from e

    def downgrade(self, revision: str) -> None:
        """マイグレーションのダウングレード."""
        try:
            logger.info(f"Downgrading to revision: {revision}")
            command.downgrade(self.config, revision)
            logger.info("Downgrade completed successfully")

        except Exception as e:
            logger.error(f"Failed to downgrade: {e}")
            raise DatabaseError(f"Migration downgrade failed: {str(e)}") from e

    def get_current_revision(self) -> str | None:
        """現在のリビジョン取得."""
        try:
            engine = create_engine(self.settings.database.url)
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return context.get_current_revision()

        except Exception as e:
            logger.error(f"Failed to get current revision: {e}")
            return None

    def get_migration_history(self) -> list[dict[str, Any]]:
        """マイグレーション履歴取得."""
        try:
            script_dir = ScriptDirectory.from_config(self.config)
            revisions = []

            for revision in script_dir.walk_revisions():
                revisions.append({
                    "revision_id": revision.revision,
                    "down_revision": revision.down_revision,
                    "message": revision.doc,
                    "is_current": revision.revision == self.get_current_revision(),
                })

            return revisions

        except Exception as e:
            logger.error(f"Failed to get migration history: {e}")
            return []

    def validate_migrations(self) -> dict[str, Any]:
        """マイグレーション検証."""
        result: dict[str, Any] = {
            "status": "valid",
            "current_revision": None,
            "available_migrations": 0,
            "pending_migrations": 0,
            "issues": []
        }

        try:
            # 現在のリビジョン
            current = self.get_current_revision()
            result["current_revision"] = current

            # 利用可能なマイグレーション数
            script_dir = ScriptDirectory.from_config(self.config)
            all_revisions = list(script_dir.walk_revisions())
            result["available_migrations"] = len(all_revisions)

            # 未適用のマイグレーション数
            if current:
                head = script_dir.get_current_head()
                if current != head:
                    # 未適用のマイグレーションがある
                    pending = []
                    for revision in script_dir.iterate_revisions(head, current):
                        pending.append(revision.revision)
                    result["pending_migrations"] = len(pending)
                    issues_list = result["issues"]
                    if isinstance(issues_list, list):
                        issues_list.append(f"Pending migrations: {', '.join(pending)}")
            else:
                result["pending_migrations"] = len(all_revisions)
                issues_list = result["issues"]
                if isinstance(issues_list, list):
                    issues_list.append("Database has no migration history")

            if result["issues"]:
                result["status"] = "issues_found"

        except Exception as e:
            result["status"] = "error"
            issues_list = result["issues"]
            if isinstance(issues_list, list):
                issues_list.append(str(e))
            logger.error(f"Migration validation failed: {e}")

        return result

    def reset_database(self, confirm: bool = False) -> None:
        """データベースリセット（危険な操作）."""
        if not confirm:
            raise ValueError("Database reset requires explicit confirmation")

        try:
            logger.warning("Resetting database - this will delete all data!")

            # すべてのテーブルを削除
            command.downgrade(self.config, "base")

            # 最新まで再適用
            command.upgrade(self.config, "head")

            logger.info("Database reset completed")

        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            raise DatabaseError(f"Database reset failed: {str(e)}") from e

    def backup_before_migration(self) -> str:
        """マイグレーション前のバックアップ作成."""
        if not self.settings.is_production():
            logger.info("Skipping backup in non-production environment")
            return ""

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"backup_{timestamp}.sql"

            # pg_dumpを使用してバックアップ
            cmd = [
                "pg_dump",
                f"--host={self.settings.database.host}",
                f"--port={self.settings.database.port}",
                f"--username={self.settings.database.username}",
                f"--dbname={self.settings.database.database}",
                f"--file={backup_file}",
                "--no-password",
                "--verbose"
            ]

            env = os.environ.copy()
            if self.settings.database.password:
                env["PGPASSWORD"] = self.settings.database.password

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info(f"Database backup created: {backup_file}")
                return backup_file
            else:
                logger.error(f"Backup failed: {result.stderr}")
                raise DatabaseError(f"Backup failed: {result.stderr}")

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise DatabaseError(f"Backup creation failed: {str(e)}") from e


# グローバルインスタンス
migration_manager = MigrationManager()
