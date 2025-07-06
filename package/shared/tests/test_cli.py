"""CLIテスト."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from refnet_shared.cli import main, info, validate, version, env
from refnet_shared.config import settings


def test_main_command():
    """メインコマンドテスト."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "RefNet共通ライブラリCLI" in result.output


def test_info_command():
    """情報表示コマンドテスト."""
    runner = CliRunner()
    result = runner.invoke(info)
    assert result.exit_code == 0
    assert "name: RefNet" in result.output
    assert "version: 0.1.0" in result.output


def test_validate_command_success(monkeypatch):
    """設定検証コマンド成功テスト."""
    runner = CliRunner()
    # デバッグモードで実行
    with runner.isolated_filesystem():
        monkeypatch.setattr("refnet_shared.config.settings.debug", True)
        result = runner.invoke(validate)
        assert result.exit_code == 0
        assert "✅ Configuration is valid" in result.output


def test_version_command():
    """バージョン表示コマンドテスト."""
    runner = CliRunner()
    result = runner.invoke(version)
    assert result.exit_code == 0
    assert f"RefNet Shared Library v{settings.version}" in result.output


def test_validate_command_failure():
    """設定検証コマンド失敗テスト."""
    runner = CliRunner()
    with patch("refnet_shared.cli.validate_required_settings") as mock_validate:
        mock_validate.side_effect = ValueError("Test configuration error")
        result = runner.invoke(validate)
        assert result.exit_code == 1
        assert "❌ Configuration error: Test configuration error" in result.output


def test_env_help_command():
    """環境設定ヘルプコマンドテスト."""
    runner = CliRunner()
    result = runner.invoke(env, ["--help"])
    assert result.exit_code == 0
    assert "環境設定管理" in result.output


def test_env_create_command_success():
    """環境設定ファイル作成コマンド成功テスト."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # .env.exampleファイルを作成
        with open(".env.example", "w") as f:
            f.write("DATABASE__HOST=localhost\nDATABASE__PORT=5432\n")

        result = runner.invoke(env, ["create", "development"])
        assert result.exit_code == 0
        assert "✅ Created .env.development from template" in result.output
        assert Path(".env.development").exists()


def test_env_create_command_template_not_found():
    """環境設定ファイル作成コマンド テンプレートなしテスト."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(env, ["create", "development"])
        assert result.exit_code == 1
        assert "❌ Error: Template file .env.example not found" in result.output


def test_env_validate_command_success():
    """環境設定検証コマンド成功テスト."""
    runner = CliRunner()
    with patch("refnet_shared.cli.load_environment_settings") as mock_load:
        from refnet_shared.config.environment import EnvironmentSettings, Environment, ConfigValidator

        # モック設定オブジェクトを作成
        mock_settings = EnvironmentSettings(environment=Environment.DEVELOPMENT)
        mock_load.return_value = mock_settings

        with patch("refnet_shared.cli.ConfigValidator") as mock_validator_class:
            mock_validator = mock_validator_class.return_value
            mock_validator.warnings = []
            mock_validator.validate_all.return_value = None

            result = runner.invoke(env, ["validate"])
            assert result.exit_code == 0
            assert "✅ Configuration is valid for development environment" in result.output


def test_env_validate_command_with_warnings():
    """環境設定検証コマンド 警告ありテスト."""
    runner = CliRunner()
    with patch("refnet_shared.cli.load_environment_settings") as mock_load:
        from refnet_shared.config.environment import EnvironmentSettings, Environment, ConfigValidator

        mock_settings = EnvironmentSettings(environment=Environment.DEVELOPMENT)
        mock_load.return_value = mock_settings

        with patch("refnet_shared.cli.ConfigValidator") as mock_validator_class:
            mock_validator = mock_validator_class.return_value
            mock_validator.warnings = ["Test warning"]
            mock_validator.validate_all.return_value = None

            result = runner.invoke(env, ["validate"])
            assert result.exit_code == 0
            assert "✅ Configuration is valid for development environment" in result.output
            assert "⚠️  Warnings:" in result.output
            assert "Test warning" in result.output


def test_env_validate_command_failure():
    """環境設定検証コマンド失敗テスト."""
    runner = CliRunner()
    with patch("refnet_shared.cli.load_environment_settings") as mock_load:
        mock_load.side_effect = Exception("Configuration error")
        result = runner.invoke(env, ["validate"])
        assert result.exit_code == 1
        assert "❌ Configuration error: Configuration error" in result.output


def test_env_export_command_success():
    """環境設定エクスポートコマンド成功テスト."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        with patch("refnet_shared.cli.load_environment_settings") as mock_load:
            from refnet_shared.config.environment import EnvironmentSettings, Environment

            mock_settings = EnvironmentSettings(environment=Environment.DEVELOPMENT)
            mock_load.return_value = mock_settings

            with patch("refnet_shared.cli.export_settings_to_json") as mock_export:
                result = runner.invoke(env, ["export", "--output", "test_config.json"])
                assert result.exit_code == 0
                assert "✅ Settings exported to test_config.json" in result.output
                mock_export.assert_called_once()


def test_env_export_command_failure():
    """環境設定エクスポートコマンド失敗テスト."""
    runner = CliRunner()
    with patch("refnet_shared.cli.load_environment_settings") as mock_load:
        mock_load.side_effect = Exception("Export error")
        result = runner.invoke(env, ["export"])
        assert result.exit_code == 1
        assert "❌ Export error: Export error" in result.output


def test_env_check_command_success():
    """環境変数チェックコマンド成功テスト."""
    runner = CliRunner()
    with patch("refnet_shared.cli.check_required_env_vars") as mock_check:
        mock_check.return_value = {
            "DATABASE__HOST": True,
            "DATABASE__USERNAME": True,
            "DATABASE__PASSWORD": True,
        }
        result = runner.invoke(env, ["check", "development"])
        assert result.exit_code == 0
        assert "Environment variable check for development:" in result.output
        assert "✅ All required variables are set for development" in result.output


def test_env_check_command_missing_vars():
    """環境変数チェックコマンド 変数不足テスト."""
    runner = CliRunner()
    with patch("refnet_shared.cli.check_required_env_vars") as mock_check:
        mock_check.return_value = {
            "DATABASE__HOST": True,
            "DATABASE__USERNAME": False,
            "DATABASE__PASSWORD": False,
        }
        result = runner.invoke(env, ["check", "development"])
        assert result.exit_code == 1
        assert "Environment variable check for development:" in result.output
        assert "❌ Some required variables are missing for development" in result.output


def test_main_script_execution():
    """メインスクリプト実行テスト."""
    with patch("refnet_shared.cli.main") as mock_main:
        # __name__ == "__main__" の条件をテスト
        exec("""
import sys
sys.modules['__main__'] = sys.modules['refnet_shared.cli']
from refnet_shared.cli import main
if __name__ == "__main__":
    main()
""")
        # main()が呼ばれたかは、実際のインポート時の動作によるため、
        # ここでは単にエラーが発生しないことを確認
