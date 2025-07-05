# Task: データベースマイグレーション設定

## タスクの目的

Alembicを使用してデータベーススキーマのマイグレーション管理システムを構築し、本番環境での安全なスキーマ変更を可能にする。開発・ステージング・本番環境でのデータベーススキーマの一貫性を保証する。

## 前提条件

- Phase 1 が完了している
- 00_database_models.md が完了している
- 全データベースモデルが定義済み
- PostgreSQL がセットアップ済み

## 実施内容

### 1. Alembic初期化と設定

#### Alembic初期化
```bash
cd package/shared
uv add alembic
alembic init alembic
```

#### alembic.ini の設定
```ini
# Alembic Config file

[alembic]
# パスを相対パスに変更
script_location = alembic

# SQLAlchemy URL（環境変数から取得）
sqlalchemy.url =

# デフォルトはUTCタイムゾーン
timezone = UTC

# ファイル名の形式
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d%%(second).2d_%%(slug)s

# トランケート設定
truncate_slug_length = 40

# リビジョンパス設定
version_path_separator = os  # Use os.pathsep. Default configuration used by new alembic.ini

# 出力設定
[alembic:exclude]
tables = spatial_ref_sys

[post_write_hooks]
# 自動フォーマット
hooks = ruff_format
ruff_format.type = console
ruff_format.entrypoint = ruff
ruff_format.options = format REVISION_SCRIPT_FILENAME

# ログ設定
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### 2. Alembic env.py の設定

`package/shared/alembic/env.py`:

```python
"""Alembic環境設定."""

import asyncio
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine
from alembic import context
import os
import sys

# プロジェクトルートをpathに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.refnet_shared.models.database import Base
from src.refnet_shared.config.environment import load_environment_settings

# Alembic Configオブジェクト
config = context.config

# ログ設定
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# メタデータ設定
target_metadata = Base.metadata

# 環境設定読み込み
settings = load_environment_settings()


def get_database_url() -> str:
    """データベースURL取得."""
    # 環境変数またはconfig.iniから取得
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    # 設定クラスから構築
    return settings.database.url


def include_object(object, name, type_, reflected, compare_to):
    """マイグレーション対象オブジェクトのフィルタリング."""
    # システムテーブルを除外
    if type_ == "table":
        if name in ["spatial_ref_sys", "geometry_columns"]:
            return False
        if name.startswith("pg_"):
            return False

    return True


def process_revision_directives(context, revision, directives):
    """リビジョン処理のカスタマイズ."""
    # 空のマイグレーションを防ぐ
    if getattr(config.cmd_opts, 'autogenerate', False):
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []
            print("No changes detected, skipping migration generation.")


def run_migrations_offline() -> None:
    """オフラインモードでのマイグレーション実行."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        process_revision_directives=process_revision_directives,
        render_as_batch=True,  # SQLite互換性のため
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """オンラインモードでのマイグレーション実行."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_database_url()

    # 接続プール設定
    configuration.setdefault("sqlalchemy.poolclass", "sqlalchemy.pool.NullPool")

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            process_revision_directives=process_revision_directives,
            render_as_batch=True,
            compare_type=True,  # カラム型の変更を検出
            compare_server_default=True,  # デフォルト値の変更を検出
        )

        with context.begin_transaction():
            context.run_migrations()


# モード判定と実行
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 3. マイグレーション管理ユーティリティ

`package/shared/src/refnet_shared/utils/migration_utils.py`:

```python
"""マイグレーション管理ユーティリティ."""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from refnet_shared.config.environment import load_environment_settings
from refnet_shared.exceptions import DatabaseError
from refnet_shared.utils import get_logger

logger = get_logger(__name__)


class MigrationManager:
    """マイグレーション管理クラス."""

    def __init__(self, alembic_ini_path: Optional[str] = None):
        """初期化."""
        if alembic_ini_path is None:
            # package/shared/alembic.ini のパスを取得
            current_dir = Path(__file__).parent
            self.alembic_ini_path = current_dir.parent.parent / "alembic.ini"
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
            return revision_id

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

    def get_current_revision(self) -> Optional[str]:
        """現在のリビジョン取得."""
        try:
            engine = create_engine(self.settings.database.url)
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return context.get_current_revision()

        except Exception as e:
            logger.error(f"Failed to get current revision: {e}")
            return None

    def get_migration_history(self) -> List[Dict[str, Any]]:
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

    def validate_migrations(self) -> Dict[str, Any]:
        """マイグレーション検証."""
        result = {
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
                    result["issues"].append(f"Pending migrations: {', '.join(pending)}")
            else:
                result["pending_migrations"] = len(all_revisions)
                result["issues"].append("Database has no migration history")

            if result["issues"]:
                result["status"] = "issues_found"

        except Exception as e:
            result["status"] = "error"
            result["issues"].append(str(e))
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
```

### 4. CLI機能の拡張

`package/shared/src/refnet_shared/cli.py` にマイグレーション管理コマンドを追加:

```python
"""マイグレーション管理CLI."""

import click
from refnet_shared.utils.migration_utils import migration_manager


@main.group()
def migrate() -> None:
    """データベースマイグレーション管理."""
    pass


@migrate.command()
@click.argument('message')
@click.option('--autogenerate/--no-autogenerate', default=True, help='Auto-generate migration from model changes')
def create(message: str, autogenerate: bool) -> None:
    """新しいマイグレーション作成."""
    try:
        revision_id = migration_manager.create_migration(message, autogenerate)
        click.echo(f"✅ Migration created: {revision_id}")
    except Exception as e:
        click.echo(f"❌ Migration creation failed: {e}")
        exit(1)


@migrate.command()
@click.option('--revision', default='head', help='Target revision (default: head)')
@click.option('--backup/--no-backup', default=True, help='Create backup before migration')
def upgrade(revision: str, backup: bool) -> None:
    """マイグレーション実行."""
    try:
        if backup:
            backup_file = migration_manager.backup_before_migration()
            if backup_file:
                click.echo(f"📁 Backup created: {backup_file}")

        migration_manager.run_migrations(revision)
        click.echo(f"✅ Migrations applied to: {revision}")
    except Exception as e:
        click.echo(f"❌ Migration failed: {e}")
        exit(1)


@migrate.command()
@click.argument('revision')
@click.option('--confirm', is_flag=True, help='Confirm downgrade operation')
def downgrade(revision: str, confirm: bool) -> None:
    """マイグレーションのダウングレード."""
    if not confirm:
        click.echo("⚠️  Downgrade operation requires --confirm flag")
        exit(1)

    try:
        migration_manager.downgrade(revision)
        click.echo(f"✅ Downgraded to: {revision}")
    except Exception as e:
        click.echo(f"❌ Downgrade failed: {e}")
        exit(1)


@migrate.command()
def status() -> None:
    """マイグレーション状態表示."""
    try:
        validation = migration_manager.validate_migrations()

        click.echo(f"Status: {validation['status']}")
        click.echo(f"Current revision: {validation['current_revision'] or 'None'}")
        click.echo(f"Available migrations: {validation['available_migrations']}")
        click.echo(f"Pending migrations: {validation['pending_migrations']}")

        if validation['issues']:
            click.echo("\n⚠️  Issues:")
            for issue in validation['issues']:
                click.echo(f"  - {issue}")

        if validation['status'] != 'valid':
            exit(1)

    except Exception as e:
        click.echo(f"❌ Status check failed: {e}")
        exit(1)


@migrate.command()
def history() -> None:
    """マイグレーション履歴表示."""
    try:
        history = migration_manager.get_migration_history()

        if not history:
            click.echo("No migrations found")
            return

        click.echo("Migration History:")
        for migration in history:
            status = "→ CURRENT" if migration['is_current'] else ""
            click.echo(f"  {migration['revision_id']}: {migration['message']} {status}")

    except Exception as e:
        click.echo(f"❌ History retrieval failed: {e}")
        exit(1)


@migrate.command()
@click.option('--confirm', is_flag=True, help='Confirm database reset')
def reset(confirm: bool) -> None:
    """データベースリセット（危険な操作）."""
    if not confirm:
        click.echo("⚠️  Database reset requires --confirm flag")
        click.echo("This operation will DELETE ALL DATA!")
        exit(1)

    try:
        migration_manager.reset_database(confirm=True)
        click.echo("✅ Database reset completed")
    except Exception as e:
        click.echo(f"❌ Database reset failed: {e}")
        exit(1)
```

### 5. 初期マイグレーション作成

```bash
# package/sharedディレクトリで実行
cd package/shared

# 初期マイグレーション作成
refnet-shared migrate create "Initial database schema" --autogenerate
```

### 6. マイグレーションファイルの例

生成される初期マイグレーションファイルの例:

`package/shared/alembic/versions/20241201_120000_initial_database_schema.py`:

```python
"""Initial database schema

Revision ID: 001_initial
Revises:
Create Date: 2024-12-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """マイグレーション実行."""
    # authors table
    op.create_table('authors',
        sa.Column('author_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('paper_count', sa.Integer(), nullable=False),
        sa.Column('citation_count', sa.Integer(), nullable=False),
        sa.Column('h_index', sa.Integer(), nullable=True),
        sa.Column('affiliations', sa.Text(), nullable=True),
        sa.Column('homepage_url', sa.String(length=2048), nullable=True),
        sa.Column('orcid', sa.String(length=19), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('paper_count >= 0', name='check_paper_count_positive'),
        sa.CheckConstraint('citation_count >= 0', name='check_citation_count_positive'),
        sa.CheckConstraint('h_index >= 0', name='check_h_index_positive'),
        sa.PrimaryKeyConstraint('author_id')
    )
    op.create_index('idx_authors_name', 'authors', ['name'], unique=False)
    op.create_index('idx_authors_name_fts', 'authors', ['name'], unique=False)
    op.create_index('idx_authors_paper_count', 'authors', ['paper_count'], unique=False)
    op.create_index('idx_authors_citation_count', 'authors', ['citation_count'], unique=False)
    op.create_index('idx_authors_h_index', 'authors', ['h_index'], unique=False)
    op.create_index('idx_authors_orcid', 'authors', ['orcid'], unique=False)

    # 他のテーブルも同様に定義...
    # （実際の実装では全テーブルが含まれる）


def downgrade() -> None:
    """マイグレーション巻き戻し."""
    op.drop_table('authors')
    # 他のテーブルも同様に削除...
```

### 7. テストの作成

`tests/test_migrations.py`:

```python
"""マイグレーションテスト."""

import pytest
import tempfile
from pathlib import Path
from refnet_shared.utils.migration_utils import MigrationManager
from refnet_shared.config.environment import EnvironmentSettings, Environment


@pytest.fixture
def test_migration_manager():
    """テスト用マイグレーションマネージャー."""
    # テスト用設定
    settings = EnvironmentSettings(
        environment=Environment.TESTING,
        database__host="localhost",
        database__database="refnet_test",
        database__username="test",
        database__password="test"
    )

    # テスト用alembic.iniファイル作成
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write("""
[alembic]
script_location = alembic
sqlalchemy.url = sqlite:///test.db
timezone = UTC
file_template = %%(year)d%%(month).2d%%(day).2d_%%(slug)s
""")
        alembic_ini_path = f.name

    manager = MigrationManager(alembic_ini_path)
    yield manager

    # クリーンアップ
    Path(alembic_ini_path).unlink()


def test_migration_validation(test_migration_manager):
    """マイグレーション検証テスト."""
    validation = test_migration_manager.validate_migrations()
    assert "status" in validation
    assert "current_revision" in validation
    assert "available_migrations" in validation


def test_migration_history(test_migration_manager):
    """マイグレーション履歴テスト."""
    history = test_migration_manager.get_migration_history()
    assert isinstance(history, list)


def test_current_revision(test_migration_manager):
    """現在リビジョン取得テスト."""
    # 初期状態ではNoneまたは例外
    revision = test_migration_manager.get_current_revision()
    assert revision is None or isinstance(revision, str)
```

## スコープ

- Alembic初期化と設定
- マイグレーション管理システム構築
- CLI マイグレーション管理機能
- マイグレーション検証・履歴管理
- 本番環境での安全なマイグレーション

**スコープ外:**
- 複雑なデータ移行スクリプト
- 大規模データベースの最適化
- レプリケーション設定
- 高度なバックアップ戦略

## 参照するドキュメント

- `/docs/database/migrations.md`
- `/docs/development/coding-standards.md`
- [Alembic Documentation](https://alembic.sqlalchemy.org/)

## 完了条件

### 必須条件
- [ ] Alembicが正しく初期化されている
- [ ] `alembic.ini` が適切に設定されている
- [ ] `env.py` が環境設定と統合されている
- [ ] 初期マイグレーションが作成されている
- [ ] マイグレーション管理CLIが実装されている

### 動作確認
- [ ] `refnet-shared migrate create "test migration"` が正常実行
- [ ] `refnet-shared migrate upgrade` が正常実行
- [ ] `refnet-shared migrate status` が正常実行
- [ ] `refnet-shared migrate history` が正常実行

### 安全性条件
- [ ] 本番環境でのバックアップ機能が動作
- [ ] ダウングレード機能が実装されている
- [ ] マイグレーション検証が動作している
- [ ] 危険な操作に確認フラグが必要

### テスト条件
- [ ] マイグレーション関連のテストが作成されている
- [ ] テストカバレッジが80%以上
- [ ] `cd package/shared && moon run shared:check` が正常終了

## トラブルシューティング

### よくある問題

1. **マイグレーション作成に失敗する**
   - 解決策: env.py のインポートパス、データベース接続を確認

2. **マイグレーション実行に失敗する**
   - 解決策: データベース権限、制約違反を確認

3. **自動生成で不要な変更が検出される**
   - 解決策: include_object 関数で除外設定を調整

4. **ダウングレードが失敗する**
   - 解決策: 外部キー制約の順序、データ依存関係を確認

## 次のタスクへの引き継ぎ

### Phase 3 への前提条件
- データベーススキーマが確定・適用済み
- マイグレーション管理システムが動作済み
- 本番環境での安全なスキーマ変更が可能

### 引き継ぎファイル
- `package/shared/alembic/` - マイグレーションディレクトリ
- `package/shared/alembic.ini` - Alembic設定
- `package/shared/src/refnet_shared/utils/migration_utils.py` - マイグレーション管理
- 初期マイグレーションファイル
