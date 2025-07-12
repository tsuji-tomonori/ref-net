"""Semantic Scholar APIクライアントのテスト."""

from typing import Any
from unittest.mock import Mock, patch

import httpx
import pytest
from refnet_shared.exceptions import ExternalAPIError

from refnet_crawler.clients.semantic_scholar import SemanticScholarClient


@pytest.fixture  # type: ignore[misc]
def client() -> SemanticScholarClient:
    """テスト用クライアント."""
    return SemanticScholarClient()


@pytest.fixture  # type: ignore[misc]
def mock_paper_data() -> dict[str, Any]:
    """モック論文データ."""
    return {
        "paperId": "test-paper-1",
        "title": "Test Paper",
        "abstract": "Test abstract",
        "year": 2023,
        "citationCount": 10,
        "referenceCount": 5,
        "authors": [
            {"authorId": "author-1", "name": "Test Author"}
        ],
        "externalIds": {"DOI": "10.1000/test"},
        "fieldsOfStudy": ["Computer Science"]
    }


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_success(
    client: SemanticScholarClient,
    mock_paper_data: dict[str, Any],
) -> None:
    """論文取得成功テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_paper_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.get_paper("test-paper-1")

        assert result is not None
        assert result.paperId == "test-paper-1"
        assert result.title == "Test Paper"
        assert result.citationCount == 10


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_not_found(client: SemanticScholarClient) -> None:
    """論文取得（存在しない）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/nonexistent-paper"),
            response=Mock(status_code=404)
        )
        mock_get.return_value = mock_response

        result = await client.get_paper("nonexistent-paper")

        assert result is None


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_citations(
    client: SemanticScholarClient,
    mock_paper_data: dict[str, Any],
) -> None:
    """引用論文取得テスト."""
    citation_data = {
        "data": [
            {"citingPaper": mock_paper_data}
        ]
    }

    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = citation_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.get_paper_citations("test-paper-1")

        assert len(result) == 1
        assert result[0].paperId == "test-paper-1"


@pytest.mark.asyncio  # type: ignore[misc]
async def test_search_papers(
    client: SemanticScholarClient,
    mock_paper_data: dict[str, Any],
) -> None:
    """論文検索テスト."""
    search_data = {
        "data": [mock_paper_data]
    }

    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = search_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.search_papers("test query")

        assert len(result) == 1
        assert result[0].paperId == "test-paper-1"


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_empty_response(client: SemanticScholarClient) -> None:
    """論文取得（空レスポンス）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.get_paper("test-paper-1")

        assert result is None


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_rate_limit(client: SemanticScholarClient) -> None:
    """論文取得（レート制限）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/test-paper-1"),
            response=Mock(status_code=429)
        )
        mock_get.return_value = mock_response

        with pytest.raises(ExternalAPIError):
            await client.get_paper("test-paper-1")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_server_error(client: SemanticScholarClient) -> None:
    """論文取得（サーバーエラー）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/test-paper-1"),
            response=Mock(status_code=500)
        )
        mock_get.return_value = mock_response

        with pytest.raises(ExternalAPIError):
            await client.get_paper("test-paper-1")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_unexpected_error(client: SemanticScholarClient) -> None:
    """論文取得（予期しないエラー）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(ExternalAPIError):
            await client.get_paper("test-paper-1")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_custom_fields(client: SemanticScholarClient) -> None:
    """論文取得（カスタムフィールド）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {"paperId": "test-paper-1", "title": "Test Paper"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.get_paper("test-paper-1", fields=["paperId", "title"])

        assert result is not None
        assert result.paperId == "test-paper-1"
        mock_get.assert_called_with("/paper/test-paper-1", params={"fields": "paperId,title"})


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_citations_empty(client: SemanticScholarClient) -> None:
    """引用論文取得（空）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.get_paper_citations("test-paper-1")

        assert len(result) == 0


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_citations_not_found(client: SemanticScholarClient) -> None:
    """引用論文取得（存在しない）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/nonexistent-paper/citations"),
            response=Mock(status_code=404)
        )
        mock_get.return_value = mock_response

        result = await client.get_paper_citations("nonexistent-paper")

        assert result == []


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_citations_rate_limit(client: SemanticScholarClient) -> None:
    """引用論文取得（レート制限）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/test-paper-1/citations"),
            response=Mock(status_code=429)
        )
        mock_get.return_value = mock_response

        with pytest.raises(ExternalAPIError):
            await client.get_paper_citations("test-paper-1")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_citations_server_error(client: SemanticScholarClient) -> None:
    """引用論文取得（サーバーエラー）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/test-paper-1/citations"),
            response=Mock(status_code=500)
        )
        mock_get.return_value = mock_response

        with pytest.raises(ExternalAPIError):
            await client.get_paper_citations("test-paper-1")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_citations_unexpected_error(client: SemanticScholarClient) -> None:
    """引用論文取得（予期しないエラー）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(ExternalAPIError):
            await client.get_paper_citations("test-paper-1")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_references(
    client: SemanticScholarClient,
    mock_paper_data: dict[str, Any],
) -> None:
    """参考文献取得テスト."""
    reference_data = {
        "data": [
            {"citedPaper": mock_paper_data}
        ]
    }

    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = reference_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.get_paper_references("test-paper-1")

        assert len(result) == 1
        assert result[0].paperId == "test-paper-1"


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_references_empty(client: SemanticScholarClient) -> None:
    """参考文献取得（空）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.get_paper_references("test-paper-1")

        assert len(result) == 0


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_references_not_found(client: SemanticScholarClient) -> None:
    """参考文献取得（存在しない）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/nonexistent-paper/references"),
            response=Mock(status_code=404)
        )
        mock_get.return_value = mock_response

        result = await client.get_paper_references("nonexistent-paper")

        assert result == []


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_references_rate_limit(client: SemanticScholarClient) -> None:
    """参考文献取得（レート制限）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/test-paper-1/references"),
            response=Mock(status_code=429)
        )
        mock_get.return_value = mock_response

        with pytest.raises(ExternalAPIError):
            await client.get_paper_references("test-paper-1")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_references_server_error(client: SemanticScholarClient) -> None:
    """参考文献取得（サーバーエラー）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/test-paper-1/references"),
            response=Mock(status_code=500)
        )
        mock_get.return_value = mock_response

        with pytest.raises(ExternalAPIError):
            await client.get_paper_references("test-paper-1")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_get_paper_references_unexpected_error(client: SemanticScholarClient) -> None:
    """参考文献取得（予期しないエラー）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(ExternalAPIError):
            await client.get_paper_references("test-paper-1")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_search_papers_empty(client: SemanticScholarClient) -> None:
    """論文検索（空）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.search_papers("test query")

        assert len(result) == 0


@pytest.mark.asyncio  # type: ignore[misc]
async def test_search_papers_with_filters(
    client: SemanticScholarClient,
    mock_paper_data: dict[str, Any],
) -> None:
    """論文検索（フィルタ付き）テスト."""
    search_data = {
        "data": [mock_paper_data]
    }

    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = search_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.search_papers(
            "test query",
            limit=50,
            offset=10,
            year_filter="2023",
            venue_filter="ICML"
        )

        assert len(result) == 1
        assert result[0].paperId == "test-paper-1"

        # パラメータが正しく設定されているか確認
        call_args = mock_get.call_args
        assert call_args[0][0] == "/paper/search"
        params = call_args[1]["params"]
        assert params["query"] == "test query"
        assert params["limit"] == 50
        assert params["offset"] == 10
        assert params["year"] == "2023"
        assert params["venue"] == "ICML"


@pytest.mark.asyncio  # type: ignore[misc]
async def test_search_papers_rate_limit(client: SemanticScholarClient) -> None:
    """論文検索（レート制限）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/search"),
            response=Mock(status_code=429)
        )
        mock_get.return_value = mock_response

        with pytest.raises(ExternalAPIError):
            await client.search_papers("test query")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_search_papers_server_error(client: SemanticScholarClient) -> None:
    """論文検索（サーバーエラー）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/search"),
            response=Mock(status_code=500)
        )
        mock_get.return_value = mock_response

        with pytest.raises(ExternalAPIError):
            await client.search_papers("test query")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_search_papers_unexpected_error(client: SemanticScholarClient) -> None:
    """論文検索（予期しないエラー）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_get.side_effect = Exception("Network error")

        with pytest.raises(ExternalAPIError):
            await client.search_papers("test query")


@pytest.mark.asyncio  # type: ignore[misc]
async def test_close(client: SemanticScholarClient) -> None:
    """クライアント終了テスト."""
    with patch.object(client.client, 'aclose') as mock_aclose:
        mock_aclose.return_value = None

        await client.close()

        mock_aclose.assert_called_once()


def test_get_headers_without_api_key() -> None:
    """APIキーなしヘッダーテスト."""
    client = SemanticScholarClient(api_key=None)
    headers = client._get_headers()

    assert "User-Agent" in headers
    assert "x-api-key" not in headers


def test_get_headers_with_api_key() -> None:
    """APIキーありヘッダーテスト."""
    client = SemanticScholarClient(api_key="test-key")
    headers = client._get_headers()

    assert "User-Agent" in headers
    assert "x-api-key" in headers
    assert headers["x-api-key"] == "test-key"


def test_client_initialization_with_api_key() -> None:
    """APIキーありクライアント初期化テスト."""
    client = SemanticScholarClient(api_key="test-key")

    assert client.api_key == "test-key"
    assert str(client.client.base_url).rstrip('/') == "https://api.semanticscholar.org/graph/v1"
    # timeoutオブジェクトの存在確認
    assert client.client.timeout is not None


def test_client_initialization_without_api_key() -> None:
    """APIキーなしクライアント初期化テスト."""
    with patch('refnet_crawler.clients.semantic_scholar.settings') as mock_settings:
        mock_settings.semantic_scholar_api_key = "settings-key"
        client = SemanticScholarClient()

        assert client.api_key == "settings-key"
