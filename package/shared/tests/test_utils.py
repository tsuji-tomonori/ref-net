"""ユーティリティテスト."""

import pytest
from refnet_shared.utils import get_app_info, validate_required_settings
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
