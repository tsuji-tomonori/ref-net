"""CLIモジュールの包括的テスト."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from refnet_shared.cli import (
    check,
    create,
    create_migration,
    downgrade,
    env,
    env_validate,
    export,
    history,
    migrate,
    reset,
    status,
    upgrade,
    validate,
    version,
)
from refnet_shared.config.environment import Environment


class TestValidateCommand:
    """validateコマンドのテスト."""

    @patch("refnet_shared.cli.validate_required_settings")
    def test_validate_command_success(self, mock_validate: MagicMock) -> None:
        """validateコマンド成功テスト."""
        mock_validate.return_value = None
        runner = CliRunner()

        result = runner.invoke(validate)

        assert result.exit_code == 0
        assert "✅ Configuration is valid" in result.output
        mock_validate.assert_called_once()

    @patch("refnet_shared.cli.validate_required_settings")
    def test_validate_command_failure(self, mock_validate: MagicMock) -> None:
        """validateコマンド失敗テスト."""
        mock_validate.side_effect = ValueError("Missing config")
        runner = CliRunner()

        result = runner.invoke(validate)

        assert result.exit_code == 1
        assert "❌ Configuration error: Missing config" in result.output


class TestVersionCommand:
    """versionコマンドのテスト."""

    @patch("refnet_shared.cli.settings")
    def test_version_command(self, mock_settings: MagicMock) -> None:
        """versionコマンドテスト."""
        mock_settings.version = "1.0.0"
        runner = CliRunner()

        result = runner.invoke(version)

        assert result.exit_code == 0
        assert "RefNet Shared Library v1.0.0" in result.output


class TestEnvGroup:
    """envグループのテスト."""

    def test_env_group_exists(self) -> None:
        """envグループが存在することを確認."""
        assert isinstance(env, click.Group)
        assert env.name == "env"

    def test_env_help(self) -> None:
        """envヘルプテスト."""
        runner = CliRunner()
        result = runner.invoke(env, ["--help"])

        assert result.exit_code == 0
        assert "環境設定管理" in result.output


class TestCreateCommand:
    """createコマンドのテスト."""

    @patch("refnet_shared.cli.create_env_file_from_template")
    def test_create_command_success(self, mock_create: MagicMock) -> None:
        """createコマンド成功テスト."""
        mock_create.return_value = None
        runner = CliRunner()

        result = runner.invoke(create, ["development"])

        assert result.exit_code == 0
        assert "✅ Created .env.development from template" in result.output
        mock_create.assert_called_once_with(Environment.DEVELOPMENT)

    @patch("refnet_shared.cli.create_env_file_from_template")
    def test_create_command_file_not_found(self, mock_create: MagicMock) -> None:
        """createコマンドファイル未発見テスト."""
        mock_create.side_effect = FileNotFoundError("Template not found")
        runner = CliRunner()

        result = runner.invoke(create, ["production"])

        assert result.exit_code == 1
        assert "❌ Error: Template not found" in result.output

    def test_create_command_invalid_environment(self) -> None:
        """createコマンド無効環境テスト."""
        runner = CliRunner()

        result = runner.invoke(create, ["invalid"])

        assert result.exit_code == 2  # Click argument validation error


class TestEnvValidateCommand:
    """env validateコマンドのテスト."""

    @patch("refnet_shared.cli.load_environment_settings")
    @patch("refnet_shared.cli.ConfigValidator")
    def test_env_validate_success(self, mock_validator_class: MagicMock, mock_load: MagicMock) -> None:
        """env validate成功テスト."""
        mock_settings = MagicMock()
        mock_settings.environment.value = "development"
        mock_load.return_value = mock_settings

        mock_validator = MagicMock()
        mock_validator.warnings = []
        mock_validator_class.return_value = mock_validator

        runner = CliRunner()
        result = runner.invoke(env_validate)

        assert result.exit_code == 0
        assert "✅ Configuration is valid for development environment" in result.output

    @patch("refnet_shared.cli.load_environment_settings")
    @patch("refnet_shared.cli.ConfigValidator")
    def test_env_validate_with_warnings(self, mock_validator_class: MagicMock, mock_load: MagicMock) -> None:
        """env validate警告テスト."""
        mock_settings = MagicMock()
        mock_settings.environment.value = "production"
        mock_load.return_value = mock_settings

        mock_validator = MagicMock()
        mock_validator.warnings = ["Warning 1", "Warning 2"]
        mock_validator_class.return_value = mock_validator

        runner = CliRunner()
        result = runner.invoke(env_validate)

        assert result.exit_code == 0
        assert "⚠️  Warnings:" in result.output
        assert "- Warning 1" in result.output
        assert "- Warning 2" in result.output

    @patch("refnet_shared.cli.load_environment_settings")
    def test_env_validate_failure(self, mock_load: MagicMock) -> None:
        """env validate失敗テスト."""
        mock_load.side_effect = Exception("Config error")
        runner = CliRunner()

        result = runner.invoke(env_validate)

        assert result.exit_code == 1
        assert "❌ Configuration error: Config error" in result.output


class TestExportCommand:
    """exportコマンドのテスト."""

    @patch("refnet_shared.cli.load_environment_settings")
    @patch("refnet_shared.cli.export_settings_to_json")
    def test_export_command_success(self, mock_export: MagicMock, mock_load: MagicMock) -> None:
        """exportコマンド成功テスト."""
        mock_settings = MagicMock()
        mock_load.return_value = mock_settings
        mock_export.return_value = None

        runner = CliRunner()
        result = runner.invoke(export, ["--output", "test.json"])

        assert result.exit_code == 0
        assert "✅ Settings exported to test.json" in result.output
        mock_export.assert_called_once_with(mock_settings, Path("test.json"))

    @patch("refnet_shared.cli.load_environment_settings")
    @patch("refnet_shared.cli.export_settings_to_json")
    def test_export_command_default_output(self, mock_export: MagicMock, mock_load: MagicMock) -> None:
        """exportコマンドデフォルト出力テスト."""
        mock_settings = MagicMock()
        mock_load.return_value = mock_settings
        mock_export.return_value = None

        runner = CliRunner()
        result = runner.invoke(export)

        assert result.exit_code == 0
        assert "✅ Settings exported to config.json" in result.output
        mock_export.assert_called_once_with(mock_settings, Path("config.json"))

    @patch("refnet_shared.cli.load_environment_settings")
    def test_export_command_failure(self, mock_load: MagicMock) -> None:
        """exportコマンド失敗テスト."""
        mock_load.side_effect = Exception("Export error")
        runner = CliRunner()

        result = runner.invoke(export)

        assert result.exit_code == 1
        assert "❌ Export error: Export error" in result.output


class TestCheckCommand:
    """checkコマンドのテスト."""

    @patch("refnet_shared.cli.check_required_env_vars")
    def test_check_command_all_set(self, mock_check: MagicMock) -> None:
        """checkコマンド全変数設定済みテスト."""
        mock_check.return_value = {"VAR1": True, "VAR2": True}
        runner = CliRunner()

        result = runner.invoke(check, ["development"])

        assert result.exit_code == 0
        assert "✅ VAR1" in result.output
        assert "✅ VAR2" in result.output
        assert "✅ All required variables are set for development" in result.output

    @patch("refnet_shared.cli.check_required_env_vars")
    def test_check_command_missing_vars(self, mock_check: MagicMock) -> None:
        """checkコマンド変数不足テスト."""
        mock_check.return_value = {"VAR1": True, "VAR2": False}
        runner = CliRunner()

        result = runner.invoke(check, ["production"])

        assert result.exit_code == 1
        assert "✅ VAR1" in result.output
        assert "❌ VAR2" in result.output
        assert "❌ Some required variables are missing for production" in result.output


class TestMigrateGroup:
    """migrateグループのテスト."""

    def test_migrate_group_exists(self) -> None:
        """migrateグループが存在することを確認."""
        assert isinstance(migrate, click.Group)
        assert migrate.name == "migrate"

    def test_migrate_help(self) -> None:
        """migrateヘルプテスト."""
        runner = CliRunner()
        result = runner.invoke(migrate, ["--help"])

        assert result.exit_code == 0
        assert "データベースマイグレーション管理" in result.output


class TestCreateMigrationCommand:
    """create-migrationコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager.create_migration")
    def test_create_migration_success(self, mock_create: MagicMock) -> None:
        """create-migration成功テスト."""
        mock_create.return_value = "rev_123"
        runner = CliRunner()

        result = runner.invoke(create_migration, ["test migration"])

        assert result.exit_code == 0
        assert "✅ Migration created: rev_123" in result.output
        mock_create.assert_called_once_with("test migration", True)

    @patch("refnet_shared.cli.migration_manager.create_migration")
    def test_create_migration_no_autogenerate(self, mock_create: MagicMock) -> None:
        """create-migration自動生成無しテスト."""
        mock_create.return_value = "rev_456"
        runner = CliRunner()

        result = runner.invoke(create_migration, ["--no-autogenerate", "manual migration"])

        assert result.exit_code == 0
        mock_create.assert_called_once_with("manual migration", False)

    @patch("refnet_shared.cli.migration_manager.create_migration")
    def test_create_migration_failure(self, mock_create: MagicMock) -> None:
        """create-migration失敗テスト."""
        mock_create.side_effect = Exception("Migration failed")
        runner = CliRunner()

        result = runner.invoke(create_migration, ["failed migration"])

        assert result.exit_code == 1
        assert "❌ Migration creation failed: Migration failed" in result.output


class TestUpgradeCommand:
    """upgradeコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager.run_migrations")
    @patch("refnet_shared.cli.migration_manager.backup_before_migration")
    def test_upgrade_with_backup(self, mock_backup: MagicMock, mock_run: MagicMock) -> None:
        """upgradeバックアップ付きテスト."""
        mock_backup.return_value = "/tmp/backup.sql"
        mock_run.return_value = None
        runner = CliRunner()

        result = runner.invoke(upgrade)

        assert result.exit_code == 0
        assert "📁 Backup created: /tmp/backup.sql" in result.output
        assert "✅ Migrations applied to: head" in result.output
        mock_backup.assert_called_once()
        mock_run.assert_called_once_with("head")

    @patch("refnet_shared.cli.migration_manager.run_migrations")
    @patch("refnet_shared.cli.migration_manager.backup_before_migration")
    def test_upgrade_no_backup(self, mock_backup: MagicMock, mock_run: MagicMock) -> None:
        """upgradeバックアップ無しテスト."""
        mock_run.return_value = None
        runner = CliRunner()

        result = runner.invoke(upgrade, ["--no-backup", "--revision", "rev_123"])

        assert result.exit_code == 0
        assert "✅ Migrations applied to: rev_123" in result.output
        mock_backup.assert_not_called()
        mock_run.assert_called_once_with("rev_123")

    @patch("refnet_shared.cli.migration_manager.run_migrations")
    def test_upgrade_failure(self, mock_run: MagicMock) -> None:
        """upgrade失敗テスト."""
        mock_run.side_effect = Exception("Migration error")
        runner = CliRunner()

        result = runner.invoke(upgrade, ["--no-backup"])

        assert result.exit_code == 1
        assert "❌ Migration failed: Migration error" in result.output


class TestDowngradeCommand:
    """downgradeコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager.downgrade")
    def test_downgrade_with_confirm(self, mock_downgrade: MagicMock) -> None:
        """downgrade確認付きテスト."""
        mock_downgrade.return_value = None
        runner = CliRunner()

        result = runner.invoke(downgrade, ["--confirm", "rev_123"])

        assert result.exit_code == 0
        assert "✅ Downgraded to: rev_123" in result.output
        mock_downgrade.assert_called_once_with("rev_123")

    def test_downgrade_no_confirm(self) -> None:
        """downgrade確認無しテスト."""
        runner = CliRunner()

        result = runner.invoke(downgrade, ["rev_123"])

        assert result.exit_code == 1
        assert "⚠️  Downgrade operation requires --confirm flag" in result.output

    @patch("refnet_shared.cli.migration_manager.downgrade")
    def test_downgrade_failure(self, mock_downgrade: MagicMock) -> None:
        """downgrade失敗テスト."""
        mock_downgrade.side_effect = Exception("Downgrade error")
        runner = CliRunner()

        result = runner.invoke(downgrade, ["--confirm", "rev_123"])

        assert result.exit_code == 1
        assert "❌ Downgrade failed: Downgrade error" in result.output


class TestStatusCommand:
    """statusコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager.validate_migrations")
    def test_status_valid(self, mock_validate: MagicMock) -> None:
        """status正常テスト."""
        mock_validate.return_value = {
            "status": "valid",
            "current_revision": "rev_123",
            "available_migrations": 5,
            "pending_migrations": 0,
            "issues": []
        }
        runner = CliRunner()

        result = runner.invoke(status)

        assert result.exit_code == 0
        assert "Status: valid" in result.output
        assert "Current revision: rev_123" in result.output

    @patch("refnet_shared.cli.migration_manager.validate_migrations")
    def test_status_with_issues(self, mock_validate: MagicMock) -> None:
        """status問題ありテスト."""
        mock_validate.return_value = {
            "status": "invalid",
            "current_revision": None,
            "available_migrations": 3,
            "pending_migrations": 2,
            "issues": ["Issue 1", "Issue 2"]
        }
        runner = CliRunner()

        result = runner.invoke(status)

        assert result.exit_code == 1
        assert "Current revision: None" in result.output
        assert "⚠️  Issues:" in result.output
        assert "- Issue 1" in result.output

    @patch("refnet_shared.cli.migration_manager.validate_migrations")
    def test_status_failure(self, mock_validate: MagicMock) -> None:
        """status失敗テスト."""
        mock_validate.side_effect = Exception("Status error")
        runner = CliRunner()

        result = runner.invoke(status)

        assert result.exit_code == 1
        assert "❌ Status check failed: Status error" in result.output


class TestHistoryCommand:
    """historyコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager.get_migration_history")
    def test_history_with_migrations(self, mock_history: MagicMock) -> None:
        """history履歴ありテスト."""
        mock_history.return_value = [
            {"revision_id": "rev_123", "message": "Initial migration", "is_current": True},
            {"revision_id": "rev_456", "message": "Add users table", "is_current": False}
        ]
        runner = CliRunner()

        result = runner.invoke(history)

        assert result.exit_code == 0
        assert "Migration History:" in result.output
        assert "rev_123: Initial migration → CURRENT" in result.output
        assert "rev_456: Add users table" in result.output

    @patch("refnet_shared.cli.migration_manager.get_migration_history")
    def test_history_empty(self, mock_history: MagicMock) -> None:
        """history履歴無しテスト."""
        mock_history.return_value = []
        runner = CliRunner()

        result = runner.invoke(history)

        assert result.exit_code == 0
        assert "No migrations found" in result.output

    @patch("refnet_shared.cli.migration_manager.get_migration_history")
    def test_history_failure(self, mock_history: MagicMock) -> None:
        """history失敗テスト."""
        mock_history.side_effect = Exception("History error")
        runner = CliRunner()

        result = runner.invoke(history)

        assert result.exit_code == 1
        assert "❌ History retrieval failed: History error" in result.output


class TestResetCommand:
    """resetコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager.reset_database")
    def test_reset_with_confirm(self, mock_reset: MagicMock) -> None:
        """reset確認付きテスト."""
        mock_reset.return_value = None
        runner = CliRunner()

        result = runner.invoke(reset, ["--confirm"])

        assert result.exit_code == 0
        assert "✅ Database reset completed" in result.output
        mock_reset.assert_called_once_with(confirm=True)

    def test_reset_no_confirm(self) -> None:
        """reset確認無しテスト."""
        runner = CliRunner()

        result = runner.invoke(reset)

        assert result.exit_code == 1
        assert "⚠️  Database reset requires --confirm flag" in result.output
        assert "This operation will DELETE ALL DATA!" in result.output

    @patch("refnet_shared.cli.migration_manager.reset_database")
    def test_reset_failure(self, mock_reset: MagicMock) -> None:
        """reset失敗テスト."""
        mock_reset.side_effect = Exception("Reset error")
        runner = CliRunner()

        result = runner.invoke(reset, ["--confirm"])

        assert result.exit_code == 1
        assert "❌ Database reset failed: Reset error" in result.output
