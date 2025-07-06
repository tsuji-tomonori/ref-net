"""設定テスト."""

import pytest
from refnet_shared.config import Settings, DatabaseConfig, RedisConfig


def test_database_config():
    """データベース設定テスト."""
    config = DatabaseConfig(
        host="testhost",
        port=5433,
        database="testdb",
        username="testuser",
        password="testpass"
    )

    expected_url = "postgresql://testuser:testpass@testhost:5433/testdb"
    assert config.url == expected_url


def test_redis_config():
    """Redis設定テスト."""
    config = RedisConfig(host="redishost", port=6380, database=2)

    expected_url = "redis://redishost:6380/2"
    assert config.url == expected_url


def test_settings_defaults():
    """設定デフォルト値テスト."""
    settings = Settings()

    assert settings.app_name == "RefNet"
    assert settings.version == "0.1.0"
    assert settings.debug is False
    assert settings.database.host == "localhost"
    assert settings.redis.host == "localhost"


def test_settings_with_test_fixture(test_settings):
    """テスト用設定テスト."""
    assert test_settings.debug is True
    assert test_settings.database.database == "refnet_test"
    assert test_settings.redis.database == 1
