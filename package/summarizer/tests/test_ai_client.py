"""AI クライアントのテスト."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from refnet_summarizer.clients.ai_client import (
    OpenAIClient,
    AnthropicClient,
    create_ai_client,
    AIClient
)
from refnet_shared.exceptions import ExternalAPIError


@pytest.fixture
def mock_openai_response():
    """モックOpenAIレスポンス."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "This is a mock summary of the paper."
    return response


@pytest.fixture
def mock_anthropic_response():
    """モックAnthropicレスポンス."""
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = "This is a mock summary of the paper."
    return response


@pytest.mark.asyncio
async def test_openai_generate_summary_success(mock_openai_response):
    """OpenAI要約生成成功テスト."""
    with patch('openai.AsyncOpenAI') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)

        client = OpenAIClient("test-api-key")
        result = await client.generate_summary("Test paper text", max_tokens=500)

        assert result == "This is a mock summary of the paper."
        mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_anthropic_generate_summary_success(mock_anthropic_response):
    """Anthropic要約生成成功テスト."""
    with patch('anthropic.AsyncAnthropic') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_anthropic_response)

        client = AnthropicClient("test-api-key")
        result = await client.generate_summary("Test paper text", max_tokens=500)

        assert result == "This is a mock summary of the paper."
        mock_client.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_openai_extract_keywords_success(mock_openai_response):
    """OpenAIキーワード抽出成功テスト."""
    mock_openai_response.choices[0].message.content = "machine learning, neural networks, deep learning"

    with patch('openai.AsyncOpenAI') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)

        client = OpenAIClient("test-api-key")
        result = await client.extract_keywords("Test paper text", max_keywords=3)

        assert result == ["machine learning", "neural networks", "deep learning"]


@pytest.mark.asyncio
async def test_openai_rate_limit_error():
    """OpenAIレート制限エラーテスト."""
    import openai
    from unittest.mock import MagicMock

    # モックレスポンスオブジェクトを作成
    mock_response = MagicMock()
    mock_response.request = MagicMock()

    with patch('openai.AsyncOpenAI') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError("Rate limit exceeded", response=mock_response, body=None)
        )

        client = OpenAIClient("test-api-key")
        with pytest.raises(ExternalAPIError) as exc_info:
            await client.generate_summary("Test paper text")

        assert "Rate limit exceeded" in str(exc_info.value)


def test_create_ai_client_with_openai():
    """OpenAIクライアント作成テスト."""
    with patch('refnet_summarizer.clients.ai_client.settings') as mock_settings:
        mock_settings.openai_api_key = "test-openai-key"
        mock_settings.anthropic_api_key = None

        client = create_ai_client()
        assert isinstance(client, OpenAIClient)


def test_create_ai_client_with_anthropic():
    """Anthropicクライアント作成テスト."""
    with patch('refnet_summarizer.clients.ai_client.settings') as mock_settings:
        mock_settings.openai_api_key = None
        mock_settings.anthropic_api_key = "test-anthropic-key"

        client = create_ai_client()
        assert isinstance(client, AnthropicClient)


def test_create_ai_client_no_api_key():
    """APIキーなしエラーテスト."""
    with patch('refnet_summarizer.clients.ai_client.settings') as mock_settings:
        mock_settings.openai_api_key = None
        mock_settings.anthropic_api_key = None

        with pytest.raises(ExternalAPIError) as exc_info:
            create_ai_client()

        assert "No AI API key configured" in str(exc_info.value)
