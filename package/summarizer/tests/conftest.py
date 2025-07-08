"""pytest設定とフィクスチャ."""

import asyncio
from unittest.mock import patch

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """イベントループフィクスチャ."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """モック環境設定."""
    with patch('refnet_summarizer.clients.ai_client.load_environment_settings') as mock_load:
        mock_settings = mock_load.return_value
        mock_settings.openai_api_key = "test-openai-key"
        mock_settings.anthropic_api_key = "test-anthropic-key"
        mock_settings.celery_broker_url = "redis://localhost:6379/0"
        mock_settings.celery_result_backend = "redis://localhost:6379/0"
        mock_settings.redis.url = "redis://localhost:6379/0"
        yield mock_settings
