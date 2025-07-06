"""環境設定テスト."""

import os
import pytest
from unittest.mock import patch
from refnet_shared.config.environment import Environment, EnvironmentSettings, ConfigValidator
from refnet_shared.exceptions import ConfigurationError


def test_environment_enum():
    """環境Enum テスト."""
    assert Environment.DEVELOPMENT == "development"
    assert Environment.STAGING == "staging"
    assert Environment.PRODUCTION == "production"


def test_environment_settings_defaults():
    """環境設定デフォルト値テスト."""
    settings = EnvironmentSettings()
    assert settings.environment == Environment.DEVELOPMENT
    assert settings.is_development() is True
    assert settings.is_production() is False


@patch.dict(os.environ, {"NODE_ENV": "production"})
def test_environment_settings_production():
    """本番環境設定テスト."""
    settings = EnvironmentSettings(environment="production")
    assert settings.environment == Environment.PRODUCTION
    assert settings.is_production() is True
    assert settings.is_development() is False


def test_config_validator_development():
    """開発環境設定検証テスト."""
    settings = EnvironmentSettings(
        environment=Environment.DEVELOPMENT,
        database__host="localhost",
        database__username="test",
        database__password="test"
    )

    validator = ConfigValidator(settings)
    validator.validate_all()  # エラーが発生しないことを確認


def test_config_validator_production_weak_password():
    """本番環境弱いパスワード検証テスト."""
    settings = EnvironmentSettings(
        environment=Environment.PRODUCTION,
        database__host="localhost",
        database__username="prod",
        database__password="test"  # 弱いパスワード
    )

    validator = ConfigValidator(settings)
    with pytest.raises(ConfigurationError):
        validator.validate_all()


def test_config_validator_production_weak_jwt():
    """本番環境弱いJWT検証テスト."""
    settings = EnvironmentSettings(
        environment=Environment.PRODUCTION,
        database__host="localhost",
        database__username="prod",
        database__password="strong_password",
        security__jwt_secret="development-secret"  # 弱いJWT
    )

    validator = ConfigValidator(settings)
    with pytest.raises(ConfigurationError):
        validator.validate_all()


def test_config_validator_production_no_api_keys():
    """本番環境APIキーなし検証テスト."""
    settings = EnvironmentSettings(
        environment=Environment.PRODUCTION,
        database__host="localhost",
        database__username="prod",
        database__password="strong_password",
        security__jwt_secret="very_secure_jwt_secret_key_for_production"
    )

    validator = ConfigValidator(settings)
    with pytest.raises(ConfigurationError):
        validator.validate_all()


def test_config_validator_production_valid():
    """本番環境有効設定検証テスト."""
    # デフォルトのセキュリティ設定を上書きして正しい本番設定を作成
    from refnet_shared.config import SecurityConfig

    security_config = SecurityConfig(
        jwt_secret="very_secure_jwt_secret_key_for_production_at_least_32_chars_long",
        jwt_algorithm="HS256",
        jwt_expiration_minutes=30
    )

    settings = EnvironmentSettings(
        environment=Environment.PRODUCTION,
        database__host="localhost",
        database__username="prod",
        database__password="very_secure_production_password_final",
        security=security_config,
        openai_api_key="valid_openai_key",
        debug=False
    )

    validator = ConfigValidator(settings)
    validator.validate_all()  # エラーが発生しないことを確認


def test_environment_validation_invalid():
    """無効な環境値の検証テスト."""
    with pytest.raises(ValueError, match="Invalid environment"):
        EnvironmentSettings(environment="invalid_env")


def test_environment_methods():
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

    # テスト環境
    test_settings = EnvironmentSettings(environment=Environment.TESTING)
    assert test_settings.is_development() is False
    assert test_settings.is_staging() is False
    assert test_settings.is_production() is False
    assert test_settings.is_testing() is True


def test_config_validator_warnings():
    """設定検証警告テスト."""
    # デフォルトのセキュリティ設定を上書きして正しい本番設定を作成
    from refnet_shared.config import SecurityConfig

    security_config = SecurityConfig(
        jwt_secret="very_secure_jwt_secret_key_for_production_at_least_32_chars_long",
        jwt_algorithm="HS256",
        jwt_expiration_minutes=120  # 長すぎる有効期限（警告対象）
    )

    settings = EnvironmentSettings(
        environment=Environment.PRODUCTION,
        database__host="localhost",
        database__username="prod",
        database__password="very_secure_production_password_final",
        security=security_config,
        openai_api_key="valid_key",
        debug=False
    )

    validator = ConfigValidator(settings)
    validator.validate_all()

    # 警告が生成されることを確認
    assert len(validator.warnings) > 0
    assert any("JWT expiration time" in warning for warning in validator.warnings)
