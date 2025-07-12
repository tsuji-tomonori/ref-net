"""CLI モジュールのテスト."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
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
    info,
    main,
    migrate,
    reset,
    status,
    upgrade,
    validate,
    version,
)
from refnet_shared.config.environment import Environment


class TestMainGroup:
    """メインCLIグループのテスト."""

    def test_main_group_exists(self) -> None:
        """メインCLIグループが存在することを確認."""
        assert isinstance(main, click.Group)
        assert main.name is None  # メイングループは名前なし

    @patch("refnet_shared.cli.setup_logging")
    def test_main_group_calls_setup_logging(self, mock_setup_logging: MagicMock) -> None:
        """メインCLIグループがsetup_loggingを呼び出すことを確認."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        mock_setup_logging.assert_called_once()

    def test_main_help_contains_all_commands(self) -> None:
        """メインヘルプに全てのコマンドが含まれることを確認."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "RefNet共通ライブラリCLI" in result.output
        assert "info" in result.output
        assert "validate" in result.output
        assert "version" in result.output
        assert "env" in result.output
        assert "migrate" in result.output


class TestInfoCommand:
    """infoコマンドのテスト."""

    @patch("refnet_shared.cli.get_app_info")
    def test_info_command_success(self, mock_get_app_info: MagicMock) -> None:
        """infoコマンドが正常に実行されることを確認."""
        # Arrange
        mock_app_info = {
            "name": "RefNet",
            "version": "0.1.0",
            "environment": "development"
        }
        mock_get_app_info.return_value = mock_app_info
        runner = CliRunner()

        # Act
        result = runner.invoke(info)

        # Assert
        assert result.exit_code == 0
        mock_get_app_info.assert_called_once()
        for key, value in mock_app_info.items():
            assert f"{key}: {value}" in result.output

    @patch("refnet_shared.cli.get_app_info")
    def test_info_command_empty_dict(self, mock_get_app_info: MagicMock) -> None:
        """infoコマンドが空辞書を処理できることを確認."""
        # Arrange
        mock_get_app_info.return_value = {}
        runner = CliRunner()

        # Act
        result = runner.invoke(info)

        # Assert
        assert result.exit_code == 0
        mock_get_app_info.assert_called_once()
        assert result.output.strip() == ""

    def test_info_command_integration(self) -> None:
        """infoコマンドの統合テスト（実際のget_app_info関数を使用）."""
        runner = CliRunner()
        result = runner.invoke(info)

        assert result.exit_code == 0
        assert "name: RefNet" in result.output
        assert "version: 0.1.0" in result.output


class TestValidateCommand:
    """validateコマンドのテスト."""

    @patch("refnet_shared.cli.validate_required_settings")
    def test_validate_command_success(self, mock_validate: MagicMock) -> None:
        """validateコマンドが正常に実行されることを確認."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(validate)

        # Assert
        assert result.exit_code == 0
        mock_validate.assert_called_once()
        assert "✅ Configuration is valid" in result.output

    @patch("refnet_shared.cli.validate_required_settings")
    def test_validate_command_failure(self, mock_validate: MagicMock) -> None:
        """validateコマンドが設定エラー時に適切に失敗することを確認."""
        # Arrange
        error_message = "Missing required configuration"
        mock_validate.side_effect = ValueError(error_message)
        runner = CliRunner()

        # Act
        result = runner.invoke(validate)

        # Assert
        assert result.exit_code == 1
        mock_validate.assert_called_once()
        assert f"❌ Configuration error: {error_message}" in result.output

    def test_validate_command_integration_debug_mode(self, monkeypatch) -> None:
        """validateコマンドの統合テスト（デバッグモード）."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            monkeypatch.setattr("refnet_shared.config.settings.debug", True)
            result = runner.invoke(validate)
            assert result.exit_code == 0
            assert "✅ Configuration is valid" in result.output


class TestVersionCommand:
    """versionコマンドのテスト."""

    @patch("refnet_shared.cli.settings")
    def test_version_command(self, mock_settings: MagicMock) -> None:
        """versionコマンドが正常に実行されることを確認."""
        # Arrange
        mock_settings.version = "1.2.3"
        runner = CliRunner()

        # Act
        result = runner.invoke(version)

        # Assert
        assert result.exit_code == 0
        assert "RefNet Shared Library v1.2.3" in result.output

    def test_version_command_integration(self) -> None:
        """versionコマンドの統合テスト（実際のsettingsを使用）."""
        runner = CliRunner()
        result = runner.invoke(version)

        assert result.exit_code == 0
        # 実際の設定値をテスト
        from refnet_shared.config import settings
        assert f"RefNet Shared Library v{settings.version}" in result.output


class TestEnvGroup:
    """環境設定CLIグループのテスト."""

    def test_env_group_exists(self) -> None:
        """環境設定CLIグループが存在することを確認."""
        assert isinstance(env, click.Group)
        assert env.name == "env"

    def test_env_help_contains_all_subcommands(self) -> None:
        """envヘルプに全てのサブコマンドが含まれることを確認."""
        runner = CliRunner()
        result = runner.invoke(env, ["--help"])

        assert result.exit_code == 0
        assert "環境設定管理" in result.output
        assert "create" in result.output
        assert "validate" in result.output
        assert "export" in result.output
        assert "check" in result.output


class TestEnvCreateCommand:
    """env createコマンドのテスト."""

    @patch("refnet_shared.cli.create_env_file_from_template")
    def test_create_command_development(self, mock_create_env: MagicMock) -> None:
        """env createコマンドでdevelopment環境を作成できることを確認."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(create, ["development"])

        # Assert
        assert result.exit_code == 0
        mock_create_env.assert_called_once_with(Environment.DEVELOPMENT)
        assert "✅ Created .env.development from template" in result.output

    @patch("refnet_shared.cli.create_env_file_from_template")
    def test_create_command_staging(self, mock_create_env: MagicMock) -> None:
        """env createコマンドでstaging環境を作成できることを確認."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(create, ["staging"])

        # Assert
        assert result.exit_code == 0
        mock_create_env.assert_called_once_with(Environment.STAGING)
        assert "✅ Created .env.staging from template" in result.output

    @patch("refnet_shared.cli.create_env_file_from_template")
    def test_create_command_production(self, mock_create_env: MagicMock) -> None:
        """env createコマンドでproduction環境を作成できることを確認."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(create, ["production"])

        # Assert
        assert result.exit_code == 0
        mock_create_env.assert_called_once_with(Environment.PRODUCTION)
        assert "✅ Created .env.production from template" in result.output

    @patch("refnet_shared.cli.create_env_file_from_template")
    def test_create_command_file_not_found(self, mock_create_env: MagicMock) -> None:
        """env createコマンドでテンプレートファイルが見つからない場合のテスト."""
        # Arrange
        error_message = "Template file .env.example not found"
        mock_create_env.side_effect = FileNotFoundError(error_message)
        runner = CliRunner()

        # Act
        result = runner.invoke(create, ["development"])

        # Assert
        assert result.exit_code == 1
        mock_create_env.assert_called_once_with(Environment.DEVELOPMENT)
        assert f"❌ Error: {error_message}" in result.output

    def test_create_command_invalid_environment(self) -> None:
        """env createコマンドで無効な環境を指定した場合のテスト."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(create, ["invalid"])

        # Assert
        assert result.exit_code != 0
        assert "Invalid value for 'ENVIRONMENT'" in result.output

    def test_create_command_integration_success(self) -> None:
        """env createコマンドの統合テスト（成功ケース）."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # .env.exampleファイルを作成
            with open(".env.example", "w") as f:
                f.write("DATABASE__HOST=localhost\nDATABASE__PORT=5432\n")

            result = runner.invoke(create, ["development"])
            assert result.exit_code == 0
            assert "✅ Created .env.development from template" in result.output
            assert Path(".env.development").exists()

    def test_create_command_integration_template_not_found(self) -> None:
        """env createコマンドの統合テスト（テンプレートなし）."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(create, ["development"])
            assert result.exit_code == 1
            assert "❌ Error: Template file .env.example not found" in result.output


class TestEnvValidateCommand:
    """env validateコマンドのテスト."""

    @patch("refnet_shared.cli.load_environment_settings")
    @patch("refnet_shared.cli.ConfigValidator")
    def test_env_validate_success_no_warnings(
        self, mock_validator_class: MagicMock, mock_load_settings: MagicMock
    ) -> None:
        """env validateコマンドが警告なしで成功することを確認."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.environment.value = "development"
        mock_load_settings.return_value = mock_settings

        mock_validator = MagicMock()
        mock_validator.warnings = []
        mock_validator_class.return_value = mock_validator

        runner = CliRunner()

        # Act
        result = runner.invoke(env_validate)

        # Assert
        assert result.exit_code == 0
        mock_load_settings.assert_called_once()
        mock_validator_class.assert_called_once_with(mock_settings)
        mock_validator.validate_all.assert_called_once()
        assert "✅ Configuration is valid for development environment" in result.output

    @patch("refnet_shared.cli.load_environment_settings")
    @patch("refnet_shared.cli.ConfigValidator")
    def test_env_validate_success_with_warnings(
        self, mock_validator_class: MagicMock, mock_load_settings: MagicMock
    ) -> None:
        """env validateコマンドが警告ありで成功することを確認."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.environment.value = "production"
        mock_load_settings.return_value = mock_settings

        mock_validator = MagicMock()
        mock_validator.warnings = ["Warning 1", "Warning 2"]
        mock_validator_class.return_value = mock_validator

        runner = CliRunner()

        # Act
        result = runner.invoke(env_validate)

        # Assert
        assert result.exit_code == 0
        mock_load_settings.assert_called_once()
        mock_validator_class.assert_called_once_with(mock_settings)
        mock_validator.validate_all.assert_called_once()
        assert "✅ Configuration is valid for production environment" in result.output
        assert "⚠️  Warnings:" in result.output
        assert "  - Warning 1" in result.output
        assert "  - Warning 2" in result.output

    @patch("refnet_shared.cli.load_environment_settings")
    def test_env_validate_failure(self, mock_load_settings: MagicMock) -> None:
        """env validateコマンドが設定エラー時に適切に失敗することを確認."""
        # Arrange
        error_message = "Configuration validation failed"
        mock_load_settings.side_effect = Exception(error_message)
        runner = CliRunner()

        # Act
        result = runner.invoke(env_validate)

        # Assert
        assert result.exit_code == 1
        mock_load_settings.assert_called_once()
        assert f"❌ Configuration error: {error_message}" in result.output

    def test_env_validate_integration_success(self) -> None:
        """env validateコマンドの統合テスト（成功ケース）."""
        runner = CliRunner()
        with patch("refnet_shared.cli.load_environment_settings") as mock_load:
            from refnet_shared.config.environment import Environment, EnvironmentSettings

            mock_settings = EnvironmentSettings(environment=Environment.DEVELOPMENT)
            mock_load.return_value = mock_settings

            with patch("refnet_shared.cli.ConfigValidator") as mock_validator_class:
                mock_validator = mock_validator_class.return_value
                mock_validator.warnings = []
                mock_validator.validate_all.return_value = None

                result = runner.invoke(env_validate)
                assert result.exit_code == 0
                assert "✅ Configuration is valid for development environment" in result.output

    def test_env_validate_integration_with_warnings(self) -> None:
        """env validateコマンドの統合テスト（警告あり）."""
        runner = CliRunner()
        with patch("refnet_shared.cli.load_environment_settings") as mock_load:
            from refnet_shared.config.environment import Environment, EnvironmentSettings

            mock_settings = EnvironmentSettings(environment=Environment.DEVELOPMENT)
            mock_load.return_value = mock_settings

            with patch("refnet_shared.cli.ConfigValidator") as mock_validator_class:
                mock_validator = mock_validator_class.return_value
                mock_validator.warnings = ["Test warning"]
                mock_validator.validate_all.return_value = None

                result = runner.invoke(env_validate)
                assert result.exit_code == 0
                assert "✅ Configuration is valid for development environment" in result.output
                assert "⚠️  Warnings:" in result.output
                assert "Test warning" in result.output

    def test_env_validate_integration_failure(self) -> None:
        """env validateコマンドの統合テスト（失敗ケース）."""
        runner = CliRunner()
        with patch("refnet_shared.cli.load_environment_settings") as mock_load:
            mock_load.side_effect = Exception("Configuration error")
            result = runner.invoke(env_validate)
            assert result.exit_code == 1
            assert "❌ Configuration error: Configuration error" in result.output


class TestEnvExportCommand:
    """env exportコマンドのテスト."""

    @patch("refnet_shared.cli.load_environment_settings")
    @patch("refnet_shared.cli.export_settings_to_json")
    def test_export_command_default_output(
        self, mock_export: MagicMock, mock_load_settings: MagicMock
    ) -> None:
        """env exportコマンドがデフォルト出力で成功することを確認."""
        # Arrange
        mock_settings = MagicMock()
        mock_load_settings.return_value = mock_settings
        runner = CliRunner()

        # Act
        result = runner.invoke(export)

        # Assert
        assert result.exit_code == 0
        mock_load_settings.assert_called_once()
        mock_export.assert_called_once_with(mock_settings, Path("config.json"))
        assert "✅ Settings exported to config.json" in result.output

    @patch("refnet_shared.cli.load_environment_settings")
    @patch("refnet_shared.cli.export_settings_to_json")
    def test_export_command_custom_output(
        self, mock_export: MagicMock, mock_load_settings: MagicMock
    ) -> None:
        """env exportコマンドがカスタム出力で成功することを確認."""
        # Arrange
        mock_settings = MagicMock()
        mock_load_settings.return_value = mock_settings
        runner = CliRunner()
        custom_output = "custom_config.json"

        # Act
        result = runner.invoke(export, ["--output", custom_output])

        # Assert
        assert result.exit_code == 0
        mock_load_settings.assert_called_once()
        mock_export.assert_called_once_with(mock_settings, Path(custom_output))
        assert f"✅ Settings exported to {custom_output}" in result.output

    @patch("refnet_shared.cli.load_environment_settings")
    @patch("refnet_shared.cli.export_settings_to_json")
    def test_export_command_short_option(
        self, mock_export: MagicMock, mock_load_settings: MagicMock
    ) -> None:
        """env exportコマンドが短縮オプションで成功することを確認."""
        # Arrange
        mock_settings = MagicMock()
        mock_load_settings.return_value = mock_settings
        runner = CliRunner()
        custom_output = "short_config.json"

        # Act
        result = runner.invoke(export, ["-o", custom_output])

        # Assert
        assert result.exit_code == 0
        mock_load_settings.assert_called_once()
        mock_export.assert_called_once_with(mock_settings, Path(custom_output))
        assert f"✅ Settings exported to {custom_output}" in result.output

    @patch("refnet_shared.cli.load_environment_settings")
    def test_export_command_failure(self, mock_load_settings: MagicMock) -> None:
        """env exportコマンドがエラー時に適切に失敗することを確認."""
        # Arrange
        error_message = "Export failed"
        mock_load_settings.side_effect = Exception(error_message)
        runner = CliRunner()

        # Act
        result = runner.invoke(export)

        # Assert
        assert result.exit_code == 1
        mock_load_settings.assert_called_once()
        assert f"❌ Export error: {error_message}" in result.output

    def test_export_command_integration_success(self) -> None:
        """env exportコマンドの統合テスト（成功ケース）."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch("refnet_shared.cli.load_environment_settings") as mock_load:
                from refnet_shared.config.environment import Environment, EnvironmentSettings

                mock_settings = EnvironmentSettings(environment=Environment.DEVELOPMENT)
                mock_load.return_value = mock_settings

                with patch("refnet_shared.cli.export_settings_to_json") as mock_export:
                    result = runner.invoke(export, ["--output", "test_config.json"])
                    assert result.exit_code == 0
                    assert "✅ Settings exported to test_config.json" in result.output
                    mock_export.assert_called_once()

    def test_export_command_integration_failure(self) -> None:
        """env exportコマンドの統合テスト（失敗ケース）."""
        runner = CliRunner()
        with patch("refnet_shared.cli.load_environment_settings") as mock_load:
            mock_load.side_effect = Exception("Export error")
            result = runner.invoke(export)
            assert result.exit_code == 1
            assert "❌ Export error: Export error" in result.output


class TestEnvCheckCommand:
    """env checkコマンドのテスト."""

    @patch("refnet_shared.cli.check_required_env_vars")
    def test_check_command_all_vars_present(self, mock_check: MagicMock) -> None:
        """env checkコマンドで全ての環境変数が設定されている場合のテスト."""
        # Arrange
        mock_check.return_value = {
            "DATABASE_URL": True,
            "SECRET_KEY": True,
            "API_KEY": True,
        }
        runner = CliRunner()

        # Act
        result = runner.invoke(check, ["development"])

        # Assert
        assert result.exit_code == 0
        mock_check.assert_called_once_with(Environment.DEVELOPMENT)
        assert "Environment variable check for development:" in result.output
        assert "✅ DATABASE_URL" in result.output
        assert "✅ SECRET_KEY" in result.output
        assert "✅ API_KEY" in result.output
        assert "✅ All required variables are set for development" in result.output

    @patch("refnet_shared.cli.check_required_env_vars")
    def test_check_command_missing_vars(self, mock_check: MagicMock) -> None:
        """env checkコマンドで一部の環境変数が不足している場合のテスト."""
        # Arrange
        mock_check.return_value = {
            "DATABASE_URL": True,
            "SECRET_KEY": False,
            "API_KEY": True,
        }
        runner = CliRunner()

        # Act
        result = runner.invoke(check, ["staging"])

        # Assert
        assert result.exit_code == 1
        mock_check.assert_called_once_with(Environment.STAGING)
        assert "Environment variable check for staging:" in result.output
        assert "✅ DATABASE_URL" in result.output
        assert "❌ SECRET_KEY" in result.output
        assert "✅ API_KEY" in result.output
        assert "❌ Some required variables are missing for staging" in result.output

    @patch("refnet_shared.cli.check_required_env_vars")
    def test_check_command_all_vars_missing(self, mock_check: MagicMock) -> None:
        """env checkコマンドで全ての環境変数が不足している場合のテスト."""
        # Arrange
        mock_check.return_value = {
            "DATABASE_URL": False,
            "SECRET_KEY": False,
        }
        runner = CliRunner()

        # Act
        result = runner.invoke(check, ["production"])

        # Assert
        assert result.exit_code == 1
        mock_check.assert_called_once_with(Environment.PRODUCTION)
        assert "Environment variable check for production:" in result.output
        assert "❌ DATABASE_URL" in result.output
        assert "❌ SECRET_KEY" in result.output
        assert "❌ Some required variables are missing for production" in result.output

    def test_check_command_invalid_environment(self) -> None:
        """env checkコマンドで無効な環境を指定した場合のテスト."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(check, ["invalid"])

        # Assert
        assert result.exit_code != 0
        assert "Invalid value for 'ENVIRONMENT'" in result.output

    def test_check_command_integration_success(self) -> None:
        """env checkコマンドの統合テスト（成功ケース）."""
        runner = CliRunner()
        with patch("refnet_shared.cli.check_required_env_vars") as mock_check:
            mock_check.return_value = {
                "DATABASE__HOST": True,
                "DATABASE__USERNAME": True,
                "DATABASE__PASSWORD": True,
            }
            result = runner.invoke(check, ["development"])
            assert result.exit_code == 0
            assert "Environment variable check for development:" in result.output
            assert "✅ All required variables are set for development" in result.output

    def test_check_command_integration_missing_vars(self) -> None:
        """env checkコマンドの統合テスト（変数不足ケース）."""
        runner = CliRunner()
        with patch("refnet_shared.cli.check_required_env_vars") as mock_check:
            mock_check.return_value = {
                "DATABASE__HOST": True,
                "DATABASE__USERNAME": False,
                "DATABASE__PASSWORD": False,
            }
            result = runner.invoke(check, ["development"])
            assert result.exit_code == 1
            assert "Environment variable check for development:" in result.output
            assert "❌ Some required variables are missing for development" in result.output


class TestMigrateGroup:
    """マイグレーションCLIグループのテスト."""

    def test_migrate_group_exists(self) -> None:
        """マイグレーションCLIグループが存在することを確認."""
        assert isinstance(migrate, click.Group)
        assert migrate.name == "migrate"

    def test_migrate_help_contains_all_subcommands(self) -> None:
        """migrateヘルプに全てのサブコマンドが含まれることを確認."""
        runner = CliRunner()
        result = runner.invoke(migrate, ["--help"])

        assert result.exit_code == 0
        assert "データベースマイグレーション管理" in result.output
        assert "create-migration" in result.output
        assert "upgrade" in result.output
        assert "downgrade" in result.output
        assert "status" in result.output
        assert "history" in result.output
        assert "reset" in result.output


class TestCreateMigrationCommand:
    """create-migrationコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager")
    def test_create_migration_success_with_autogenerate(self, mock_manager: MagicMock) -> None:
        """create-migrationコマンドが自動生成ありで正常に実行されることを確認."""
        # Arrange
        revision_id = "abc123"
        message = "Add user table"
        mock_manager.create_migration.return_value = revision_id
        runner = CliRunner()

        # Act
        result = runner.invoke(create_migration, [message])

        # Assert
        assert result.exit_code == 0
        mock_manager.create_migration.assert_called_once_with(message, True)
        assert f"✅ Migration created: {revision_id}" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_create_migration_success_no_autogenerate(self, mock_manager: MagicMock) -> None:
        """create-migrationコマンドで自動生成を無効にした場合のテスト."""
        # Arrange
        revision_id = "def456"
        message = "Manual migration"
        mock_manager.create_migration.return_value = revision_id
        runner = CliRunner()

        # Act
        result = runner.invoke(create_migration, [message, "--no-autogenerate"])

        # Assert
        assert result.exit_code == 0
        mock_manager.create_migration.assert_called_once_with(message, False)
        assert f"✅ Migration created: {revision_id}" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_create_migration_with_autogenerate_flag(self, mock_manager: MagicMock) -> None:
        """create-migrationコマンドで明示的に自動生成を有効にした場合のテスト."""
        # Arrange
        revision_id = "ghi789"
        message = "Auto generated migration"
        mock_manager.create_migration.return_value = revision_id
        runner = CliRunner()

        # Act
        result = runner.invoke(create_migration, [message, "--autogenerate"])

        # Assert
        assert result.exit_code == 0
        mock_manager.create_migration.assert_called_once_with(message, True)
        assert f"✅ Migration created: {revision_id}" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_create_migration_failure(self, mock_manager: MagicMock) -> None:
        """create-migrationコマンドがエラー時に適切に失敗することを確認."""
        # Arrange
        error_message = "Migration creation failed"
        message = "Failed migration"
        mock_manager.create_migration.side_effect = Exception(error_message)
        runner = CliRunner()

        # Act
        result = runner.invoke(create_migration, [message])

        # Assert
        assert result.exit_code == 1
        mock_manager.create_migration.assert_called_once_with(message, True)
        assert f"❌ Migration creation failed: {error_message}" in result.output


class TestUpgradeCommand:
    """upgradeコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager")
    def test_upgrade_default_revision_with_backup(self, mock_manager: MagicMock) -> None:
        """upgradeコマンドがデフォルトリビジョンでバックアップ付きで成功することを確認."""
        # Arrange
        backup_file = "/tmp/backup_20230101.sql"
        mock_manager.backup_before_migration.return_value = backup_file
        runner = CliRunner()

        # Act
        result = runner.invoke(upgrade)

        # Assert
        assert result.exit_code == 0
        mock_manager.backup_before_migration.assert_called_once()
        mock_manager.run_migrations.assert_called_once_with("head")
        assert f"📁 Backup created: {backup_file}" in result.output
        assert "✅ Migrations applied to: head" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_upgrade_custom_revision_no_backup(self, mock_manager: MagicMock) -> None:
        """upgradeコマンドがカスタムリビジョンでバックアップなしで成功することを確認."""
        # Arrange
        revision = "abc123"
        runner = CliRunner()

        # Act
        result = runner.invoke(upgrade, ["--revision", revision, "--no-backup"])

        # Assert
        assert result.exit_code == 0
        mock_manager.backup_before_migration.assert_not_called()
        mock_manager.run_migrations.assert_called_once_with(revision)
        assert "📁 Backup created:" not in result.output
        assert f"✅ Migrations applied to: {revision}" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_upgrade_with_backup_flag(self, mock_manager: MagicMock) -> None:
        """upgradeコマンドで明示的にバックアップを有効にした場合のテスト."""
        # Arrange
        backup_file = "/tmp/backup_20230102.sql"
        mock_manager.backup_before_migration.return_value = backup_file
        runner = CliRunner()

        # Act
        result = runner.invoke(upgrade, ["--backup"])

        # Assert
        assert result.exit_code == 0
        mock_manager.backup_before_migration.assert_called_once()
        mock_manager.run_migrations.assert_called_once_with("head")
        assert f"📁 Backup created: {backup_file}" in result.output
        assert "✅ Migrations applied to: head" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_upgrade_no_backup_file_created(self, mock_manager: MagicMock) -> None:
        """upgradeコマンドでバックアップファイルが作成されなかった場合のテスト."""
        # Arrange
        mock_manager.backup_before_migration.return_value = None
        runner = CliRunner()

        # Act
        result = runner.invoke(upgrade)

        # Assert
        assert result.exit_code == 0
        mock_manager.backup_before_migration.assert_called_once()
        mock_manager.run_migrations.assert_called_once_with("head")
        assert "📁 Backup created:" not in result.output
        assert "✅ Migrations applied to: head" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_upgrade_failure(self, mock_manager: MagicMock) -> None:
        """upgradeコマンドがエラー時に適切に失敗することを確認."""
        # Arrange
        error_message = "Migration failed"
        mock_manager.run_migrations.side_effect = Exception(error_message)
        runner = CliRunner()

        # Act
        result = runner.invoke(upgrade, ["--no-backup"])

        # Assert
        assert result.exit_code == 1
        mock_manager.run_migrations.assert_called_once_with("head")
        assert f"❌ Migration failed: {error_message}" in result.output


class TestDowngradeCommand:
    """downgradeコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager")
    def test_downgrade_success_with_confirm(self, mock_manager: MagicMock) -> None:
        """downgradeコマンドが確認フラグ付きで成功することを確認."""
        # Arrange
        revision = "abc123"
        runner = CliRunner()

        # Act
        result = runner.invoke(downgrade, [revision, "--confirm"])

        # Assert
        assert result.exit_code == 0
        mock_manager.downgrade.assert_called_once_with(revision)
        assert f"✅ Downgraded to: {revision}" in result.output

    def test_downgrade_without_confirm(self) -> None:
        """downgradeコマンドが確認フラグなしで適切に失敗することを確認."""
        # Arrange
        revision = "abc123"
        runner = CliRunner()

        # Act
        result = runner.invoke(downgrade, [revision])

        # Assert
        assert result.exit_code == 1
        assert "⚠️  Downgrade operation requires --confirm flag" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_downgrade_failure(self, mock_manager: MagicMock) -> None:
        """downgradeコマンドがエラー時に適切に失敗することを確認."""
        # Arrange
        revision = "abc123"
        error_message = "Downgrade failed"
        mock_manager.downgrade.side_effect = Exception(error_message)
        runner = CliRunner()

        # Act
        result = runner.invoke(downgrade, [revision, "--confirm"])

        # Assert
        assert result.exit_code == 1
        mock_manager.downgrade.assert_called_once_with(revision)
        assert f"❌ Downgrade failed: {error_message}" in result.output


class TestStatusCommand:
    """statusコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager")
    def test_status_valid_no_issues(self, mock_manager: MagicMock) -> None:
        """statusコマンドが問題なしの有効な状態で成功することを確認."""
        # Arrange
        validation_result = {
            "status": "valid",
            "current_revision": "abc123",
            "available_migrations": 5,
            "pending_migrations": 0,
            "issues": [],
        }
        mock_manager.validate_migrations.return_value = validation_result
        runner = CliRunner()

        # Act
        result = runner.invoke(status)

        # Assert
        assert result.exit_code == 0
        mock_manager.validate_migrations.assert_called_once()
        assert "Status: valid" in result.output
        assert "Current revision: abc123" in result.output
        assert "Available migrations: 5" in result.output
        assert "Pending migrations: 0" in result.output
        assert "⚠️  Issues:" not in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_status_with_issues(self, mock_manager: MagicMock) -> None:
        """statusコマンドが問題ありの状態で適切な情報を表示することを確認."""
        # Arrange
        validation_result = {
            "status": "invalid",
            "current_revision": None,
            "available_migrations": 3,
            "pending_migrations": 2,
            "issues": ["Issue 1", "Issue 2"],
        }
        mock_manager.validate_migrations.return_value = validation_result
        runner = CliRunner()

        # Act
        result = runner.invoke(status)

        # Assert
        assert result.exit_code == 1
        mock_manager.validate_migrations.assert_called_once()
        assert "Status: invalid" in result.output
        assert "Current revision: None" in result.output
        assert "Available migrations: 3" in result.output
        assert "Pending migrations: 2" in result.output
        assert "⚠️  Issues:" in result.output
        assert "  - Issue 1" in result.output
        assert "  - Issue 2" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_status_partial_invalid_with_current_revision(self, mock_manager: MagicMock) -> None:
        """statusコマンドで部分的に無効で現在のリビジョンがある場合のテスト."""
        # Arrange
        validation_result = {
            "status": "partial",
            "current_revision": "def456",
            "available_migrations": 10,
            "pending_migrations": 3,
            "issues": ["Pending migration detected"],
        }
        mock_manager.validate_migrations.return_value = validation_result
        runner = CliRunner()

        # Act
        result = runner.invoke(status)

        # Assert
        assert result.exit_code == 1
        mock_manager.validate_migrations.assert_called_once()
        assert "Status: partial" in result.output
        assert "Current revision: def456" in result.output
        assert "Available migrations: 10" in result.output
        assert "Pending migrations: 3" in result.output
        assert "⚠️  Issues:" in result.output
        assert "  - Pending migration detected" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_status_failure(self, mock_manager: MagicMock) -> None:
        """statusコマンドがエラー時に適切に失敗することを確認."""
        # Arrange
        error_message = "Status check failed"
        mock_manager.validate_migrations.side_effect = Exception(error_message)
        runner = CliRunner()

        # Act
        result = runner.invoke(status)

        # Assert
        assert result.exit_code == 1
        mock_manager.validate_migrations.assert_called_once()
        assert f"❌ Status check failed: {error_message}" in result.output


class TestHistoryCommand:
    """historyコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager")
    def test_history_with_migrations(self, mock_manager: MagicMock) -> None:
        """historyコマンドがマイグレーション履歴を正常に表示することを確認."""
        # Arrange
        history_data = [
            {"revision_id": "abc123", "message": "Add user table", "is_current": False},
            {"revision_id": "def456", "message": "Add index", "is_current": True},
            {"revision_id": "ghi789", "message": "Update schema", "is_current": False},
        ]
        mock_manager.get_migration_history.return_value = history_data
        runner = CliRunner()

        # Act
        result = runner.invoke(history, [])

        # Assert
        assert result.exit_code == 0
        mock_manager.get_migration_history.assert_called_once()
        assert "Migration History:" in result.output
        assert "abc123: Add user table" in result.output
        assert "def456: Add index → CURRENT" in result.output
        assert "ghi789: Update schema" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_history_no_migrations(self, mock_manager: MagicMock) -> None:
        """historyコマンドでマイグレーション履歴がない場合のテスト."""
        # Arrange
        mock_manager.get_migration_history.return_value = []
        runner = CliRunner()

        # Act
        result = runner.invoke(history, [])

        # Assert
        assert result.exit_code == 0
        mock_manager.get_migration_history.assert_called_once()
        assert "No migrations found" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_history_single_migration_current(self, mock_manager: MagicMock) -> None:
        """historyコマンドで単一のマイグレーションが現在の場合のテスト."""
        # Arrange
        history_data = [
            {"revision_id": "only123", "message": "Initial migration", "is_current": True},
        ]
        mock_manager.get_migration_history.return_value = history_data
        runner = CliRunner()

        # Act
        result = runner.invoke(history, [])

        # Assert
        assert result.exit_code == 0
        mock_manager.get_migration_history.assert_called_once()
        assert "Migration History:" in result.output
        assert "only123: Initial migration → CURRENT" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_history_failure(self, mock_manager: MagicMock) -> None:
        """historyコマンドがエラー時に適切に失敗することを確認."""
        # Arrange
        error_message = "History retrieval failed"
        mock_manager.get_migration_history.side_effect = Exception(error_message)
        runner = CliRunner()

        # Act
        result = runner.invoke(history, [])

        # Assert
        assert result.exit_code == 1
        mock_manager.get_migration_history.assert_called_once()
        assert f"❌ History retrieval failed: {error_message}" in result.output


class TestResetCommand:
    """resetコマンドのテスト."""

    @patch("refnet_shared.cli.migration_manager")
    def test_reset_success_with_confirm(self, mock_manager: MagicMock) -> None:
        """resetコマンドが確認フラグ付きで成功することを確認."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(reset, ["--confirm"])

        # Assert
        assert result.exit_code == 0
        mock_manager.reset_database.assert_called_once_with(confirm=True)
        assert "✅ Database reset completed" in result.output

    def test_reset_without_confirm(self) -> None:
        """resetコマンドが確認フラグなしで適切に失敗することを確認."""
        # Arrange
        runner = CliRunner()

        # Act
        result = runner.invoke(reset)

        # Assert
        assert result.exit_code == 1
        assert "⚠️  Database reset requires --confirm flag" in result.output
        assert "This operation will DELETE ALL DATA!" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_reset_failure(self, mock_manager: MagicMock) -> None:
        """resetコマンドがエラー時に適切に失敗することを確認."""
        # Arrange
        error_message = "Database reset failed"
        mock_manager.reset_database.side_effect = Exception(error_message)
        runner = CliRunner()

        # Act
        result = runner.invoke(reset, ["--confirm"])

        # Assert
        assert result.exit_code == 1
        mock_manager.reset_database.assert_called_once_with(confirm=True)
        assert f"❌ Database reset failed: {error_message}" in result.output


class TestCLIIntegration:
    """CLI全体の統合テスト."""

    @pytest.mark.parametrize(
        "environment",
        ["development", "staging", "production"]
    )
    def test_all_environments_accepted_in_choice_commands(self, environment: str) -> None:
        """全ての環境がChoice型コマンドで受け入れられることを確認."""
        # Arrange
        runner = CliRunner()

        # Act & Assert - env create
        result = runner.invoke(create, ["--help"])
        assert result.exit_code == 0
        assert environment in result.output

        # Act & Assert - env check
        result = runner.invoke(check, ["--help"])
        assert result.exit_code == 0
        assert environment in result.output

    def test_main_script_execution(self) -> None:
        """メインスクリプト実行テスト."""
        with patch("refnet_shared.cli.main"):
            # __name__ == "__main__" の条件をテスト
            exec("""
import sys
sys.modules['__main__'] = sys.modules['refnet_shared.cli']
from refnet_shared.cli import main
if __name__ == "__main__":
    main()
""")

    @pytest.mark.parametrize(
        "command_name,command_function",
        [
            ("info", info),
            ("validate", validate),
            ("version", version),
        ]
    )
    def test_individual_commands_are_click_commands(
        self, command_name: str, command_function
    ) -> None:
        """個別のコマンドがClickコマンドであることを確認."""
        assert hasattr(command_function, "__click_params__")
        assert callable(command_function)

    @pytest.mark.parametrize(
        "group_name,group_function",
        [
            ("env", env),
            ("migrate", migrate),
        ]
    )
    def test_command_groups_are_click_groups(
        self, group_name: str, group_function
    ) -> None:
        """コマンドグループがClickグループであることを確認."""
        assert isinstance(group_function, click.Group)
        assert group_function.name == group_name

    def test_all_commands_have_proper_docstrings(self) -> None:
        """全てのコマンドが適切なDocstringを持つことを確認."""
        commands_to_check = [info, validate, version]
        for command in commands_to_check:
            assert command.__doc__ is not None
            assert len(command.__doc__.strip()) > 0

    def test_all_groups_have_proper_docstrings(self) -> None:
        """全てのグループが適切なDocstringを持つことを確認."""
        groups_to_check = [main, env, migrate]
        for group in groups_to_check:
            assert group.help is not None
            assert len(group.help.strip()) > 0


class TestCLIErrorHandling:
    """CLIエラーハンドリングのテスト."""

    @patch("refnet_shared.cli.migration_manager")
    def test_migration_commands_handle_generic_exceptions(self, mock_manager: MagicMock) -> None:
        """マイグレーションコマンドが一般的な例外を適切に処理することを確認."""
        # Arrange
        commands_and_args = [
            (create_migration, ["test message"]),
            (upgrade, []),
            (downgrade, ["abc123", "--confirm"]),
            (status, []),
            (history, []),
            (reset, ["--confirm"]),
        ]

        for command, args in commands_and_args:
            # 各コマンドで例外を発生させる
            if command == create_migration:
                mock_manager.create_migration.side_effect = Exception("Test error")
            elif command == upgrade:
                mock_manager.run_migrations.side_effect = Exception("Test error")
            elif command == downgrade:
                mock_manager.downgrade.side_effect = Exception("Test error")
            elif command == status:
                mock_manager.validate_migrations.side_effect = Exception("Test error")
            elif command == history:
                mock_manager.get_migration_history.side_effect = Exception("Test error")
            elif command == reset:
                mock_manager.reset_database.side_effect = Exception("Test error")

            runner = CliRunner()
            result = runner.invoke(command, args)

            # Assert
            assert result.exit_code == 1
            assert "❌" in result.output
            assert "Test error" in result.output

            # Reset mock for next iteration
            mock_manager.reset_mock()

    def test_env_commands_handle_generic_exceptions(self) -> None:
        """環境コマンドが一般的な例外を適切に処理することを確認."""
        # Test env validate
        runner = CliRunner()
        with patch("refnet_shared.cli.load_environment_settings") as mock_load:
            mock_load.side_effect = Exception("Test validation error")
            result = runner.invoke(env_validate)
            assert result.exit_code == 1
            assert "❌ Configuration error: Test validation error" in result.output

        # Test env export
        with patch("refnet_shared.cli.load_environment_settings") as mock_load:
            mock_load.side_effect = Exception("Test export error")
            result = runner.invoke(export)
            assert result.exit_code == 1
            assert "❌ Export error: Test export error" in result.output


class TestCLICommandStructure:
    """CLIコマンド構造のテスト."""

    def test_main_group_contains_expected_commands(self) -> None:
        """メイングループが期待されるコマンドを含むことを確認."""
        expected_commands = {"info", "validate", "version", "env", "migrate"}
        actual_commands = set(main.commands.keys())
        assert expected_commands.issubset(actual_commands)

    def test_env_group_contains_expected_commands(self) -> None:
        """envグループが期待されるコマンドを含むことを確認."""
        expected_commands = {"create", "validate", "export", "check"}
        actual_commands = set(env.commands.keys())
        assert expected_commands.issubset(actual_commands)

    def test_migrate_group_contains_expected_commands(self) -> None:
        """migrateグループが期待されるコマンドを含むことを確認."""
        expected_commands = {
            "create-migration", "upgrade", "downgrade",
            "status", "history", "reset"
        }
        actual_commands = set(migrate.commands.keys())
        assert expected_commands.issubset(actual_commands)

    def test_command_parameter_validation(self) -> None:
        """コマンドパラメータの検証テスト."""
        runner = CliRunner()

        # Test create-migration without message
        result = runner.invoke(create_migration, [])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

        # Test downgrade without revision
        result = runner.invoke(downgrade, [])
        assert result.exit_code != 0
        assert "Missing argument" in result.output


class TestCLIOptionalParameters:
    """CLIオプショナルパラメータのテスト."""

    @patch("refnet_shared.cli.migration_manager")
    def test_upgrade_with_all_options(self, mock_manager: MagicMock) -> None:
        """upgradeコマンドで全てのオプションを指定した場合のテスト."""
        # Arrange
        backup_file = "/tmp/custom_backup.sql"
        mock_manager.backup_before_migration.return_value = backup_file
        runner = CliRunner()

        # Act
        result = runner.invoke(upgrade, [
            "--revision", "custom123",
            "--backup"
        ])

        # Assert
        assert result.exit_code == 0
        mock_manager.backup_before_migration.assert_called_once()
        mock_manager.run_migrations.assert_called_once_with("custom123")
        assert f"📁 Backup created: {backup_file}" in result.output
        assert "✅ Migrations applied to: custom123" in result.output

    @patch("refnet_shared.cli.migration_manager")
    def test_create_migration_with_all_options(self, mock_manager: MagicMock) -> None:
        """create-migrationコマンドで全てのオプションを指定した場合のテスト."""
        # Arrange
        revision_id = "full_opts_123"
        message = "Full options migration"
        mock_manager.create_migration.return_value = revision_id
        runner = CliRunner()

        # Act
        result = runner.invoke(create_migration, [
            message,
            "--autogenerate"
        ])

        # Assert
        assert result.exit_code == 0
        mock_manager.create_migration.assert_called_once_with(message, True)
        assert f"✅ Migration created: {revision_id}" in result.output
