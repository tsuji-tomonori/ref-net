"""Semantic Scholar APIクライアントのテスト."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from refnet_crawler.clients.semantic_scholar import SemanticScholarClient


@pytest.fixture
def client() -> SemanticScholarClient:
    """テスト用クライアント."""
    return SemanticScholarClient()


@pytest.fixture
def mock_paper_data() -> dict[str, str | int | list[dict[str, str]]]:
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


@pytest.mark.asyncio
async def test_get_paper_success(
    client: SemanticScholarClient,
    mock_paper_data: dict[str, str | int | list[dict[str, str]]],
) -> None:
    """論文取得成功テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_paper_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.get_paper("test-paper-1")

        assert result is not None
        assert result.paperId == "test-paper-1"
        assert result.title == "Test Paper"
        assert result.citationCount == 10


@pytest.mark.asyncio
async def test_get_paper_not_found(client: SemanticScholarClient) -> None:
    """論文取得（存在しない）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=httpx.Request("GET", "https://api.semanticscholar.org/graph/v1/paper/nonexistent-paper"),
            response=AsyncMock(status_code=404)
        )
        mock_get.return_value = mock_response

        result = await client.get_paper("nonexistent-paper")

        assert result is None


@pytest.mark.asyncio
async def test_get_paper_citations(
    client: SemanticScholarClient,
    mock_paper_data: dict[str, str | int | list[dict[str, str]]],
) -> None:
    """引用論文取得テスト."""
    citation_data = {
        "data": [
            {"citingPaper": mock_paper_data}
        ]
    }

    with patch.object(client.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.json.return_value = citation_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.get_paper_citations("test-paper-1")

        assert len(result) == 1
        assert result[0].paperId == "test-paper-1"


@pytest.mark.asyncio
async def test_search_papers(
    client: SemanticScholarClient,
    mock_paper_data: dict[str, str | int | list[dict[str, str]]],
) -> None:
    """論文検索テスト."""
    search_data = {
        "data": [mock_paper_data]
    }

    with patch.object(client.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.json.return_value = search_data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await client.search_papers("test query")

        assert len(result) == 1
        assert result[0].paperId == "test-paper-1"
