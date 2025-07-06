"""CLIテスト."""

import pytest
from click.testing import CliRunner
from refnet_shared.cli import main, info, validate, version
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
