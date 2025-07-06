"""マイグレーションテスト."""

import tempfile
from pathlib import Path

import pytest

from refnet_shared.utils.migration_utils import MigrationManager


@pytest.fixture
def test_migration_manager():
    """テスト用マイグレーションマネージャー."""
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

    try:
        manager = MigrationManager(alembic_ini_path)
        yield manager
    finally:
        # クリーンアップ
        Path(alembic_ini_path).unlink(missing_ok=True)


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
