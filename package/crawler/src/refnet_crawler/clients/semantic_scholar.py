"""Semantic Scholar APIクライアント."""

import httpx
import structlog
from refnet_shared.config.environment import load_environment_settings
from refnet_shared.exceptions import ExternalAPIError
from tenacity import retry, stop_after_attempt, wait_exponential

from refnet_crawler.models.paper_data import SemanticScholarPaper

logger = structlog.get_logger(__name__)
settings = load_environment_settings()


class SemanticScholarClient:
    """Semantic Scholar APIクライアント."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: str | None = None):
        """初期化."""
        self.api_key = api_key or settings.semantic_scholar_api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self._get_headers(),
            timeout=30.0,
        )

    def _get_headers(self) -> dict[str, str]:
        """HTTPヘッダー取得."""
        headers = {
            "User-Agent": "RefNet/0.1.0 (research paper network visualization)",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    @retry(  # type: ignore[misc]
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def get_paper(
        self, paper_id: str, fields: list[str] | None = None
    ) -> SemanticScholarPaper | None:
        """論文情報取得."""
        if not fields:
            fields = [
                "paperId",
                "title",
                "abstract",
                "year",
                "citationCount",
                "referenceCount",
                "authors",
                "venue",
                "journal",
                "externalIds",
                "fieldsOfStudy",
                "url",
            ]

        try:
            response = await self.client.get(
                f"/paper/{paper_id}", params={"fields": ",".join(fields)}
            )
            response.raise_for_status()

            data = response.json()
            if not data:
                return None

            return SemanticScholarPaper.model_validate(data)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Paper not found", paper_id=paper_id)
                return None
            elif e.response.status_code == 429:
                logger.warning("Rate limit exceeded", paper_id=paper_id)
                raise ExternalAPIError("Rate limit exceeded") from e
            else:
                logger.error("HTTP error", paper_id=paper_id, status_code=e.response.status_code)
                raise ExternalAPIError(f"HTTP error: {e.response.status_code}") from e
        except Exception as e:
            logger.error("Unexpected error", paper_id=paper_id, error=str(e))
            raise ExternalAPIError(f"Unexpected error: {str(e)}") from e

    @retry(  # type: ignore[misc]
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def get_paper_citations(
        self, paper_id: str, limit: int = 1000, offset: int = 0, fields: list[str] | None = None
    ) -> list[SemanticScholarPaper]:
        """論文の引用論文取得."""
        if not fields:
            fields = [
                "paperId",
                "title",
                "abstract",
                "year",
                "citationCount",
                "referenceCount",
                "authors",
                "venue",
                "journal",
                "externalIds",
                "fieldsOfStudy",
            ]

        try:
            response = await self.client.get(
                f"/paper/{paper_id}/citations",
                params={
                    "fields": ",".join(fields),
                    "limit": limit,
                    "offset": offset,
                },
            )
            response.raise_for_status()

            data = response.json()
            citations = []

            for item in data.get("data", []):
                citing_paper = item.get("citingPaper")
                if citing_paper:
                    citations.append(SemanticScholarPaper.model_validate(citing_paper))

            return citations

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Paper citations not found", paper_id=paper_id)
                return []
            elif e.response.status_code == 429:
                logger.warning("Rate limit exceeded", paper_id=paper_id)
                raise ExternalAPIError("Rate limit exceeded") from e
            else:
                logger.error("HTTP error", paper_id=paper_id, status_code=e.response.status_code)
                raise ExternalAPIError(f"HTTP error: {e.response.status_code}") from e
        except Exception as e:
            logger.error("Unexpected error", paper_id=paper_id, error=str(e))
            raise ExternalAPIError(f"Unexpected error: {str(e)}") from e

    @retry(  # type: ignore[misc]
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def get_paper_references(
        self, paper_id: str, limit: int = 1000, offset: int = 0, fields: list[str] | None = None
    ) -> list[SemanticScholarPaper]:
        """論文の参考文献取得."""
        if not fields:
            fields = [
                "paperId",
                "title",
                "abstract",
                "year",
                "citationCount",
                "referenceCount",
                "authors",
                "venue",
                "journal",
                "externalIds",
                "fieldsOfStudy",
            ]

        try:
            response = await self.client.get(
                f"/paper/{paper_id}/references",
                params={
                    "fields": ",".join(fields),
                    "limit": limit,
                    "offset": offset,
                },
            )
            response.raise_for_status()

            data = response.json()
            references = []

            for item in data.get("data", []):
                cited_paper = item.get("citedPaper")
                if cited_paper:
                    references.append(SemanticScholarPaper.model_validate(cited_paper))

            return references

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("Paper references not found", paper_id=paper_id)
                return []
            elif e.response.status_code == 429:
                logger.warning("Rate limit exceeded", paper_id=paper_id)
                raise ExternalAPIError("Rate limit exceeded") from e
            else:
                logger.error("HTTP error", paper_id=paper_id, status_code=e.response.status_code)
                raise ExternalAPIError(f"HTTP error: {e.response.status_code}") from e
        except Exception as e:
            logger.error("Unexpected error", paper_id=paper_id, error=str(e))
            raise ExternalAPIError(f"Unexpected error: {str(e)}") from e

    async def search_papers(
        self,
        query: str,
        limit: int = 100,
        offset: int = 0,
        fields: list[str] | None = None,
        year_filter: str | None = None,
        venue_filter: str | None = None,
    ) -> list[SemanticScholarPaper]:
        """論文検索."""
        if not fields:
            fields = [
                "paperId",
                "title",
                "abstract",
                "year",
                "citationCount",
                "referenceCount",
                "authors",
                "venue",
                "journal",
                "externalIds",
                "fieldsOfStudy",
            ]

        params: dict[str, str | int] = {
            "query": query,
            "fields": ",".join(fields),
            "limit": limit,
            "offset": offset,
        }

        if year_filter:
            params["year"] = year_filter
        if venue_filter:
            params["venue"] = venue_filter

        try:
            response = await self.client.get("/paper/search", params=params)
            response.raise_for_status()

            data = response.json()
            papers = []

            for item in data.get("data", []):
                papers.append(SemanticScholarPaper.model_validate(item))

            return papers

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Rate limit exceeded", query=query)
                raise ExternalAPIError("Rate limit exceeded") from e
            else:
                logger.error("HTTP error", query=query, status_code=e.response.status_code)
                raise ExternalAPIError(f"HTTP error: {e.response.status_code}") from e
        except Exception as e:
            logger.error("Unexpected error", query=query, error=str(e))
            raise ExternalAPIError(f"Unexpected error: {str(e)}") from e

    async def close(self) -> None:
        """クライアント終了."""
        await self.client.aclose()
