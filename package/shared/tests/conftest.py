"""pytest設定."""

import pytest

from refnet_shared.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """テスト用設定."""
    import os
    # 環境変数を直接設定
    os.environ["DEBUG"] = "true"
    os.environ["DATABASE__HOST"] = "localhost"
    os.environ["DATABASE__DATABASE"] = "refnet_test"
    os.environ["REDIS__DATABASE"] = "1"
    os.environ["LOGGING__LEVEL"] = "DEBUG"
    os.environ["SECURITY__JWT_SECRET"] = "test-secret-key"

    return Settings()


@pytest.fixture
def mock_env_vars(monkeypatch):
    """テスト用環境変数."""
    test_vars = {
        "DATABASE__HOST": "localhost",
        "DATABASE__DATABASE": "refnet_test",
        "REDIS__DATABASE": "1",
        "LOGGING__LEVEL": "DEBUG",
    }
    for key, value in test_vars.items():
        monkeypatch.setenv(key, value)
