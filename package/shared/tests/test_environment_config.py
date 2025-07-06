"""環境設定テスト."""

import os
from unittest.mock import patch

import pytest

from refnet_shared.config.environment import ConfigValidator, Environment, EnvironmentSettings
from refnet_shared.exceptions import ConfigurationError


def test_environment_enum():
    """環境Enum テスト."""
    assert Environment.DEVELOPMENT.value == "development"
    assert Environment.STAGING.value == "staging"
    assert Environment.PRODUCTION.value == "production"


def test_environment_settings_defaults():
    """環境設定デフォルト値テスト."""
    settings = EnvironmentSettings()
    assert settings.environment == Environment.DEVELOPMENT
    assert settings.is_development() is True
    assert settings.is_production() is False


def test_environment_settings_production():
    """本番環境設定テスト."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        settings = EnvironmentSettings()
        assert settings.environment == Environment.PRODUCTION
        assert settings.is_production() is True
        assert settings.is_development() is False


def test_config_validator_development():
    """開発環境設定検証テスト."""
    with patch.dict(os.environ, {
        "NODE_ENV": "development",
        "DATABASE__HOST": "localhost",
        "DATABASE__USERNAME": "test",
        "DATABASE__PASSWORD": "test"
    }):
        settings = EnvironmentSettings()
        assert settings.environment == Environment.DEVELOPMENT

        validator = ConfigValidator(settings)
        validator.validate_all()  # エラーが発生しないことを確認


def test_config_validator_production_weak_password():
    """本番環境弱いパスワード検証テスト."""
    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "DATABASE__HOST": "localhost",
        "DATABASE__USERNAME": "prod",
        "DATABASE__PASSWORD": "test"  # 弱いパスワード
    }):
        settings = EnvironmentSettings()
        assert settings.environment == Environment.PRODUCTION

        validator = ConfigValidator(settings)
        with pytest.raises(ConfigurationError):
            validator.validate_all()


def test_config_validator_production_weak_jwt():
    """本番環境弱いJWT検証テスト."""
    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "DATABASE__HOST": "localhost",
        "DATABASE__USERNAME": "prod",
        "DATABASE__PASSWORD": "strong_password",
        "SECURITY__JWT_SECRET": "development-secret"  # 弱いJWT
    }):
        settings = EnvironmentSettings()
        assert settings.environment == Environment.PRODUCTION

        validator = ConfigValidator(settings)
        with pytest.raises(ConfigurationError):
            validator.validate_all()


def test_config_validator_production_no_api_keys():
    """本番環境APIキーなし検証テスト."""
    with patch.dict(os.environ, {
        "ENVIRONMENT": "production",
        "DATABASE__HOST": "localhost",
        "DATABASE__USERNAME": "prod",
        "DATABASE__PASSWORD": "strong_password",
        "SECURITY__JWT_SECRET": "very_secure_jwt_secret_key_for_production"
    }):
        settings = EnvironmentSettings()
        assert settings.environment == Environment.PRODUCTION

        validator = ConfigValidator(settings)
        with pytest.raises(ConfigurationError):
            validator.validate_all()


def test_environment_settings_boolean_methods():
    """環境判定メソッドテスト."""
    # 開発環境
    dev_settings = EnvironmentSettings(environment=Environment.DEVELOPMENT)
    assert dev_settings.is_development() is True
    assert dev_settings.is_staging() is False
    assert dev_settings.is_production() is False
    assert dev_settings.is_testing() is False

    # ステージング環境
    staging_settings = EnvironmentSettings(environment=Environment.STAGING)
    assert staging_settings.is_development() is False
    assert staging_settings.is_staging() is True
    assert staging_settings.is_production() is False
    assert staging_settings.is_testing() is False

    # 本番環境
    prod_settings = EnvironmentSettings(environment=Environment.PRODUCTION)
    assert prod_settings.is_development() is False
    assert prod_settings.is_staging() is False
    assert prod_settings.is_production() is True
    assert prod_settings.is_testing() is False

    # テスト環境
    test_settings = EnvironmentSettings(environment=Environment.TESTING)
    assert test_settings.is_development() is False
    assert test_settings.is_staging() is False
    assert test_settings.is_production() is False
    assert test_settings.is_testing() is True


def test_config_validator_warnings():
    """設定検証警告テスト."""
    # ベース設定から開始
    settings = EnvironmentSettings(environment=Environment.PRODUCTION)

    # データベース設定を直接上書き
    settings.database.host = "localhost"
    settings.database.username = "prod"
    settings.database.password = "very_secure_production_password_strong_enough"

    # セキュリティ設定を直接上書き
    settings.security.jwt_secret = "very_secure_production_jwt_key_32_chars_long_enough_final"
    settings.security.jwt_expiration_minutes = 120  # 長すぎる有効期限（警告対象）

    # その他の設定
    settings.openai_api_key = "production_key"
    settings.debug = False

    validator = ConfigValidator(settings)
    validator.validate_all()  # エラーにはならない

    # 警告が出ることを確認
    assert len(validator.warnings) > 0
    assert any("JWT expiration time" in warning for warning in validator.warnings)


def test_environment_validation():
    """環境種別バリデーションテスト."""
    # 有効な文字列
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
        settings = EnvironmentSettings()
        assert settings.environment == Environment.DEVELOPMENT

    # 大文字小文字混在
    with patch.dict(os.environ, {"ENVIRONMENT": "PRODUCTION"}):
        settings = EnvironmentSettings()
        assert settings.environment == Environment.PRODUCTION

    # 無効な環境種別
    with patch.dict(os.environ, {"ENVIRONMENT": "invalid_env"}):
        with pytest.raises(ValueError):
            EnvironmentSettings()
