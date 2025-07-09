"""Alembic環境設定."""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# プロジェクトルートをpathに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.refnet_shared.config.environment import load_environment_settings
from src.refnet_shared.models.database import Base

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
