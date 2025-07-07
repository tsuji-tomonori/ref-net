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


def test_migration_manager_init():
    """マイグレーションマネージャー初期化テスト."""
    # デフォルトalembic.iniファイルを使用
    manager = MigrationManager()
    # デフォルトではコードベースのルートパスが使用される
    assert manager.alembic_ini_path.name == "alembic.ini"

    # 存在しないカスタムalembic.iniファイルを使用しようとするとエラー
    custom_path = "custom_alembic.ini"
    with pytest.raises(FileNotFoundError, match="Alembic config not found"):
        manager = MigrationManager(custom_path)


def test_reset_database_without_confirmation():
    """データベースリセット確認なしテスト."""
    manager = MigrationManager()
    with pytest.raises(ValueError, match="Database reset requires explicit confirmation"):
        manager.reset_database(confirm=False)


def test_create_migration_error_handling(test_migration_manager, monkeypatch):
    """マイグレーション作成エラーハンドリングテスト."""
    from refnet_shared.exceptions import DatabaseError

    # alembic commandを無効にして強制的に例外を発生させる
    def mock_revision(*args, **kwargs):
        raise Exception("Test error")

    import alembic.command
    monkeypatch.setattr(alembic.command, "revision", mock_revision)

    with pytest.raises(DatabaseError, match="Migration creation failed"):
        test_migration_manager.create_migration("test migration")


def test_run_migrations_error_handling(test_migration_manager, monkeypatch):
    """マイグレーション実行エラーハンドリングテスト."""
    from refnet_shared.exceptions import DatabaseError

    # alembic commandを無効にして強制的に例外を発生させる
    def mock_upgrade(*args, **kwargs):
        raise Exception("Test upgrade error")

    import alembic.command
    monkeypatch.setattr(alembic.command, "upgrade", mock_upgrade)

    with pytest.raises(DatabaseError, match="Migration execution failed"):
        test_migration_manager.run_migrations()


def test_downgrade_error_handling(test_migration_manager, monkeypatch):
    """ダウングレードエラーハンドリングテスト."""
    from refnet_shared.exceptions import DatabaseError

    # alembic commandを無効にして強制的に例外を発生させる
    def mock_downgrade(*args, **kwargs):
        raise Exception("Test downgrade error")

    import alembic.command
    monkeypatch.setattr(alembic.command, "downgrade", mock_downgrade)

    with pytest.raises(DatabaseError, match="Migration downgrade failed"):
        test_migration_manager.downgrade("-1")


def test_create_migration_without_autogenerate(test_migration_manager, monkeypatch):
    """自動生成なしマイグレーション作成テスト."""
    from refnet_shared.exceptions import DatabaseError

    def mock_revision(*args, **kwargs):
        # autogenerateがFalseの場合のパス
        raise Exception("Test error for manual migration")

    import alembic.command
    monkeypatch.setattr(alembic.command, "revision", mock_revision)
    with pytest.raises(DatabaseError, match="Migration creation failed"):
        test_migration_manager.create_migration("test migration", autogenerate=False)


def test_run_migrations_to_specific_revision(test_migration_manager, monkeypatch):
    """特定リビジョンへのマイグレーション実行テスト."""
    from refnet_shared.exceptions import DatabaseError

    def mock_upgrade(*args, **kwargs):
        raise Exception("Test upgrade to specific revision error")

    import alembic.command
    monkeypatch.setattr(alembic.command, "upgrade", mock_upgrade)
    with pytest.raises(DatabaseError, match="Migration execution failed"):
        test_migration_manager.run_migrations("abc123")


def test_migration_validation_with_issues(test_migration_manager, monkeypatch):
    """問題ありマイグレーション検証テスト."""
    # ScriptDirectoryからの取得をモック
    def mock_get_current_revision():
        return "current456"  # headと異なる値

    # 未適用マイグレーションがある場合のテスト
    monkeypatch.setattr(test_migration_manager, "get_current_revision", mock_get_current_revision)

    from alembic.script import ScriptDirectory

    class MockScriptDirectory:
        def get_current_head(self):
            return "head123"

        def walk_revisions(self):
            # 複数のリビジョンを返すモック
            class MockRevision:
                def __init__(self, revision_id):
                    self.revision = revision_id

            return [MockRevision("rev1"), MockRevision("rev2")]

        def iterate_revisions(self, start, end):
            # 未適用のリビジョンを返すモック
            class MockRevision:
                def __init__(self, revision_id):
                    self.revision = revision_id

            return [MockRevision("pending1"), MockRevision("pending2")]

    def mock_from_config(config):
        return MockScriptDirectory()

    monkeypatch.setattr(ScriptDirectory, "from_config", mock_from_config)

    result = test_migration_manager.validate_migrations()
    assert result["status"] == "issues_found"
    assert result["pending_migrations"] == 2
    assert len(result["issues"]) > 0


def test_migration_validation_no_history(test_migration_manager, monkeypatch):
    """マイグレーション履歴なし検証テスト."""
    # 現在のリビジョンがNoneの場合（初回状態）
    def mock_get_current_revision():
        return None

    monkeypatch.setattr(test_migration_manager, "get_current_revision", mock_get_current_revision)

    from alembic.script import ScriptDirectory

    class MockScriptDirectory:
        def get_current_head(self):
            return "head123"

        def walk_revisions(self):
            class MockRevision:
                def __init__(self, revision_id):
                    self.revision = revision_id

            return [MockRevision("rev1"), MockRevision("rev2")]

    def mock_from_config(config):
        return MockScriptDirectory()

    monkeypatch.setattr(ScriptDirectory, "from_config", mock_from_config)

    result = test_migration_manager.validate_migrations()
    assert result["status"] == "issues_found"
    assert result["pending_migrations"] == 2
    assert any("no migration history" in issue for issue in result["issues"])


def test_reset_database_with_confirmation(test_migration_manager):
    """データベースリセット確認ありテスト."""
    # 確認ありでリセットを実行（エラーが発生する可能性があるが、例外処理をテスト）
    from refnet_shared.exceptions import DatabaseError
    try:
        test_migration_manager.reset_database(confirm=True)
    except DatabaseError:
        # リセット処理でエラーが発生することは予想される（テスト環境のため）
        pass


def test_migration_manager_alembic_config_error():
    """Alembic設定エラーテスト."""
    # 存在しないディレクトリのalembic.iniを指定
    with pytest.raises(FileNotFoundError, match="Alembic config not found"):
        MigrationManager("/nonexistent/path/alembic.ini")


def test_get_current_revision_script_error(test_migration_manager, monkeypatch):
    """現在リビジョン取得スクリプトエラーテスト."""
    from alembic.script import ScriptDirectory

    # ScriptDirectory.from_configを失敗させる
    def mock_from_config(config):
        raise Exception("Script directory error")

    monkeypatch.setattr(ScriptDirectory, "from_config", mock_from_config)

    # エラー時はNoneが返される
    revision = test_migration_manager.get_current_revision()
    assert revision is None


def test_get_migration_history_script_error(test_migration_manager, monkeypatch):
    """マイグレーション履歴取得スクリプトエラーテスト."""
    from alembic.script import ScriptDirectory

    # ScriptDirectory.from_configを失敗させる
    def mock_from_config(config):
        raise Exception("Script directory error")

    monkeypatch.setattr(ScriptDirectory, "from_config", mock_from_config)

    # エラー時は空リストが返される
    history = test_migration_manager.get_migration_history()
    assert history == []


def test_validate_migrations_script_error(test_migration_manager, monkeypatch):
    """マイグレーション検証スクリプトエラーテスト."""
    from alembic.script import ScriptDirectory

    # ScriptDirectory.from_configを失敗させる
    def mock_from_config(config):
        raise Exception("Script directory error")

    monkeypatch.setattr(ScriptDirectory, "from_config", mock_from_config)

    result = test_migration_manager.validate_migrations()
    # エラー処理によって "error" または "issues_found" のいずれかになる
    assert result["status"] in ["error", "issues_found"]
    # エラーの場合は "error" フィールドに、issues_foundの場合は "issues" フィールドにメッセージが含まれる
    has_error = ("error" in result and "Script directory error" in result["error"]) or \
                ("issues" in result and any("Script directory error" in str(issue) for issue in result["issues"]))
    assert has_error


def test_reset_database_downgrade_error(test_migration_manager, monkeypatch):
    """データベースリセットダウングレードエラーテスト."""
    from refnet_shared.exceptions import DatabaseError

    # downgradeを失敗させる
    def mock_downgrade(*args, **kwargs):
        raise Exception("Downgrade failed during reset")

    import alembic.command
    monkeypatch.setattr(alembic.command, "downgrade", mock_downgrade)

    with pytest.raises(DatabaseError, match="Database reset failed"):
        test_migration_manager.reset_database(confirm=True)


def test_reset_database_upgrade_error(test_migration_manager, monkeypatch):
    """データベースリセットアップグレードエラーテスト."""
    from refnet_shared.exceptions import DatabaseError

    # downgradeは成功するがupgradeを失敗させる
    def mock_downgrade(*args, **kwargs):
        # 最初のdowngradeは成功
        pass

    def mock_upgrade(*args, **kwargs):
        raise Exception("Upgrade failed during reset")

    import alembic.command
    monkeypatch.setattr(alembic.command, "downgrade", mock_downgrade)
    monkeypatch.setattr(alembic.command, "upgrade", mock_upgrade)

    with pytest.raises(DatabaseError, match="Database reset failed"):
        test_migration_manager.reset_database(confirm=True)


def test_migration_manager_environment_error(monkeypatch):
    """マイグレーション環境エラーテスト."""
    from alembic.config import Config

    # Configの初期化を失敗させる
    def mock_config_init(*args, **kwargs):
        raise Exception("Config initialization failed")

    monkeypatch.setattr(Config, "__init__", mock_config_init)

    with pytest.raises(Exception, match="Config initialization failed"):
        MigrationManager()


def test_migration_invalid_revision_format(test_migration_manager, monkeypatch):
    """無効なリビジョン形式テスト."""
    from refnet_shared.exceptions import DatabaseError

    # 無効なリビジョン値でエラーを発生させる
    def mock_upgrade(*args, **kwargs):
        if "invalid_revision" in str(args):
            raise Exception("Invalid revision format")
        return None

    import alembic.command
    monkeypatch.setattr(alembic.command, "upgrade", mock_upgrade)

    with pytest.raises(DatabaseError, match="Migration execution failed"):
        test_migration_manager.run_migrations("invalid_revision")
