"""ユーティリティテスト."""

import logging
from unittest.mock import patch

import pytest
import structlog

from refnet_shared.utils import get_app_info, validate_required_settings, setup_logging, get_logger
from refnet_shared.config import Settings


def test_get_app_info(test_settings):
    """アプリケーション情報取得テスト."""
    info = get_app_info()

    assert "name" in info
    assert "version" in info
    assert "debug" in info
    assert "database_url" in info
    assert "redis_url" in info
    assert "logging_level" in info

    # パスワードがマスクされていることを確認
    assert "***" in info["database_url"]
    assert test_settings.database.password not in info["database_url"]


def test_validate_required_settings_success(monkeypatch):
    """設定検証成功テスト."""
    # デバッグモードで実行
    monkeypatch.setattr("refnet_shared.config.settings.debug", True)
    validate_required_settings()


def test_validate_required_settings_production_fail(monkeypatch):
    """本番環境設定検証失敗テスト."""
    # 本番環境でデフォルトのシークレットを使用
    monkeypatch.setattr("refnet_shared.config.settings.debug", False)
    monkeypatch.setattr("refnet_shared.config.settings.security.jwt_secret", "development-secret-key")

    with pytest.raises(ValueError) as exc_info:
        validate_required_settings()

    assert "SECURITY__JWT_SECRET must be set in production" in str(exc_info.value)


def test_validate_required_settings_missing_database_host(monkeypatch):
    """データベースホスト不足テスト."""
    monkeypatch.setattr("refnet_shared.config.settings.database.host", "")

    with pytest.raises(ValueError) as exc_info:
        validate_required_settings()

    assert "DATABASE__HOST is required" in str(exc_info.value)


def test_setup_logging_json_format(monkeypatch):
    """ロギング設定テスト（JSON形式）."""
    monkeypatch.setattr("refnet_shared.config.settings.logging.level", "INFO")
    monkeypatch.setattr("refnet_shared.config.settings.logging.format", "json")

    with patch("logging.basicConfig") as mock_basic:
        with patch("structlog.configure") as mock_configure:
            setup_logging()

            mock_basic.assert_called_once()
            mock_configure.assert_called_once()

            # JSONRendererが含まれているかチェック
            configure_args = mock_configure.call_args[1]
            processors = configure_args["processors"]
            processor_names = [proc.__class__.__name__ for proc in processors]
            assert "JSONRenderer" in processor_names


def test_setup_logging_console_format(monkeypatch):
    """ロギング設定テスト（コンソール形式）."""
    monkeypatch.setattr("refnet_shared.config.settings.logging.level", "DEBUG")
    monkeypatch.setattr("refnet_shared.config.settings.logging.format", "console")

    with patch("logging.basicConfig") as mock_basic:
        with patch("structlog.configure") as mock_configure:
            setup_logging()

            mock_basic.assert_called_once()
            mock_configure.assert_called_once()

            # ConsoleRendererが含まれているかチェック
            configure_args = mock_configure.call_args[1]
            processors = configure_args["processors"]
            processor_names = [proc.__class__.__name__ for proc in processors]
            assert "ConsoleRenderer" in processor_names


def test_get_logger():
    """ロガー取得テスト."""
    logger = get_logger("test_logger")
    # structlogが返すのはBoundLoggerLazyProxyかBoundLoggerなので、適切な型チェックを行う
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
    assert hasattr(logger, "debug")
