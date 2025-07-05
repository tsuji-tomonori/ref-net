# Task: クローラーサービス実装

## タスクの目的

Semantic Scholar APIを使用して論文メタデータを収集し、引用・被引用関係を再帰的に収集するクローラーサービスを実装する。Phase 3の中核データ収集サービスとして機能する。

## 前提条件

- Phase 2 が完了している
- データベースモデルが利用可能
- 共通ライブラリ（shared）が利用可能
- 環境設定管理システムが動作

## 実施内容

### 1. パッケージ構造の作成

```bash
cd package/crawler
mkdir -p src/refnet_crawler/{clients,services,tasks,models}
touch src/refnet_crawler/__init__.py
touch src/refnet_crawler/main.py
touch src/refnet_crawler/clients/__init__.py
touch src/refnet_crawler/services/__init__.py
touch src/refnet_crawler/tasks/__init__.py
touch src/refnet_crawler/models/__init__.py
```

### 2. pyproject.toml の設定

```toml
[project]
name = "refnet-crawler"
version = "0.1.0"
description = "RefNet Crawler Service"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "celery>=5.3.0",
    "redis>=5.0.0",
    "httpx>=0.27.0",
    "tenacity>=8.0.0",
    "sqlalchemy>=2.0.0",
    "psycopg2-binary>=2.9.0",
    "structlog>=23.0.0",
    "pydantic>=2.0.0",
    "refnet-shared",
    "mypy>=1.16.1",
    "pytest>=8.4.1",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.12.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
refnet-crawler = "refnet_crawler.main:main"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
extra_checks = true
```

### 3. moon.yml の設定

```yaml
type: application
language: python

dependsOn:
  - shared

tasks:
  install:
    command: uv sync
    inputs:
      - "pyproject.toml"
      - "uv.lock"

  worker:
    command: celery -A refnet_crawler.tasks.celery_app worker --loglevel=info --queue=crawl
    inputs:
      - "src/**/*.py"
    local: true

  beat:
    command: celery -A refnet_crawler.tasks.celery_app beat --loglevel=info
    inputs:
      - "src/**/*.py"
    local: true

  lint:
    command: ruff check src/
    inputs:
      - "src/**/*.py"

  format:
    command: ruff format src/
    inputs:
      - "src/**/*.py"

  typecheck:
    command: mypy src/
    inputs:
      - "src/**/*.py"

  test:
    command: pytest tests/
    inputs:
      - "src/**/*.py"
      - "tests/**/*.py"

  build:
    command: docker build -t refnet-crawler .
    inputs:
      - "src/**/*.py"
      - "Dockerfile"
    outputs:
      - "dist/"

  check:
    deps:
      - lint
      - typecheck
      - test
```

### 4. Semantic Scholar APIクライアント

`src/refnet_crawler/clients/semantic_scholar.py`:

```python
"""Semantic Scholar APIクライアント."""

from typing import Dict, List, Optional, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from refnet_shared.config.environment import load_environment_settings
from refnet_shared.exceptions import ExternalAPIError
from refnet_crawler.models.paper_data import SemanticScholarPaper
import structlog


logger = structlog.get_logger(__name__)
settings = load_environment_settings()


class SemanticScholarClient:
    """Semantic Scholar APIクライアント."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None):
        """初期化."""
        self.api_key = api_key or settings.semantic_scholar_api_key
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=self._get_headers(),
            timeout=30.0,
        )

    def _get_headers(self) -> Dict[str, str]:
        """HTTPヘッダー取得."""
        headers = {
            "User-Agent": "RefNet/0.1.0 (research paper network visualization)",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def get_paper(self, paper_id: str, fields: Optional[List[str]] = None) -> Optional[SemanticScholarPaper]:
        """論文情報取得."""
        if not fields:
            fields = [
                "paperId", "title", "abstract", "year", "citationCount", "referenceCount",
                "authors", "venue", "journal", "externalIds", "fieldsOfStudy", "url"
            ]

        try:
            response = await self.client.get(
                f"/paper/{paper_id}",
                params={"fields": ",".join(fields)}
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def get_paper_citations(
        self,
        paper_id: str,
        limit: int = 1000,
        offset: int = 0,
        fields: Optional[List[str]] = None
    ) -> List[SemanticScholarPaper]:
        """論文の引用論文取得."""
        if not fields:
            fields = [
                "paperId", "title", "abstract", "year", "citationCount", "referenceCount",
                "authors", "venue", "journal", "externalIds", "fieldsOfStudy"
            ]

        try:
            response = await self.client.get(
                f"/paper/{paper_id}/citations",
                params={
                    "fields": ",".join(fields),
                    "limit": limit,
                    "offset": offset,
                }
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def get_paper_references(
        self,
        paper_id: str,
        limit: int = 1000,
        offset: int = 0,
        fields: Optional[List[str]] = None
    ) -> List[SemanticScholarPaper]:
        """論文の参考文献取得."""
        if not fields:
            fields = [
                "paperId", "title", "abstract", "year", "citationCount", "referenceCount",
                "authors", "venue", "journal", "externalIds", "fieldsOfStudy"
            ]

        try:
            response = await self.client.get(
                f"/paper/{paper_id}/references",
                params={
                    "fields": ",".join(fields),
                    "limit": limit,
                    "offset": offset,
                }
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
        fields: Optional[List[str]] = None,
        year_filter: Optional[str] = None,
        venue_filter: Optional[str] = None,
    ) -> List[SemanticScholarPaper]:
        """論文検索."""
        if not fields:
            fields = [
                "paperId", "title", "abstract", "year", "citationCount", "referenceCount",
                "authors", "venue", "journal", "externalIds", "fieldsOfStudy"
            ]

        params = {
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
```

### 5. データモデル定義

`src/refnet_crawler/models/paper_data.py`:

```python
"""Semantic Scholar APIレスポンス用データモデル."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SemanticScholarAuthor(BaseModel):
    """Semantic Scholar著者モデル."""
    authorId: Optional[str] = None
    name: Optional[str] = None


class SemanticScholarVenue(BaseModel):
    """Semantic Scholar会場モデル."""
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    alternate_names: Optional[List[str]] = None
    issn: Optional[str] = None
    url: Optional[str] = None


class SemanticScholarJournal(BaseModel):
    """Semantic Scholarジャーナルモデル."""
    name: Optional[str] = None
    pages: Optional[str] = None
    volume: Optional[str] = None


class SemanticScholarPaper(BaseModel):
    """Semantic Scholar論文モデル."""
    paperId: str
    title: Optional[str] = None
    abstract: Optional[str] = None
    year: Optional[int] = None
    citationCount: Optional[int] = None
    referenceCount: Optional[int] = None
    authors: Optional[List[SemanticScholarAuthor]] = None
    venue: Optional[SemanticScholarVenue] = None
    journal: Optional[SemanticScholarJournal] = None
    externalIds: Optional[Dict[str, str]] = None
    fieldsOfStudy: Optional[List[str]] = None
    url: Optional[str] = None

    def to_paper_create_dict(self) -> Dict[str, Any]:
        """データベース作成用辞書に変換."""
        return {
            "paper_id": self.paperId,
            "title": self.title or "",
            "abstract": self.abstract,
            "year": self.year,
            "citation_count": self.citationCount or 0,
            "reference_count": self.referenceCount or 0,
        }
```

### 6. クローラーサービス

`src/refnet_crawler/services/crawler_service.py`:

```python
"""クローラーサービス."""

from typing import List, Optional
import asyncio
from sqlalchemy.orm import Session
from refnet_shared.models.database import Paper, Author, PaperRelation, ProcessingQueue
from refnet_shared.models.database_manager import db_manager
from refnet_crawler.clients.semantic_scholar import SemanticScholarClient
from refnet_crawler.models.paper_data import SemanticScholarPaper
import structlog


logger = structlog.get_logger(__name__)


class CrawlerService:
    """クローラーサービス."""

    def __init__(self):
        """初期化."""
        self.client = SemanticScholarClient()

    async def crawl_paper(self, paper_id: str, hop_count: int = 0, max_hops: int = 3) -> bool:
        """論文情報を収集."""
        try:
            # 論文情報取得
            paper_data = await self.client.get_paper(paper_id)
            if not paper_data:
                logger.warning("Paper not found", paper_id=paper_id)
                return False

            # データベース保存
            with db_manager.get_session() as session:
                await self._save_paper_data(session, paper_data)

                # 引用関係の収集（再帰的）
                if hop_count < max_hops:
                    await self._crawl_citations(session, paper_id, hop_count + 1, max_hops)
                    await self._crawl_references(session, paper_id, hop_count + 1, max_hops)

                # 処理状態を更新
                await self._update_processing_status(session, paper_id, "crawl", "completed")

            logger.info("Paper crawled successfully", paper_id=paper_id, hop_count=hop_count)
            return True

        except Exception as e:
            logger.error("Failed to crawl paper", paper_id=paper_id, error=str(e))

            # エラー状態を記録
            with db_manager.get_session() as session:
                await self._update_processing_status(session, paper_id, "crawl", "failed", str(e))

            return False

    async def _save_paper_data(self, session: Session, paper_data: SemanticScholarPaper) -> None:
        """論文データを保存."""
        # 既存チェック
        existing_paper = session.query(Paper).filter_by(paper_id=paper_data.paperId).first()

        if existing_paper:
            # 既存論文の更新
            existing_paper.title = paper_data.title or existing_paper.title
            existing_paper.abstract = paper_data.abstract or existing_paper.abstract
            existing_paper.year = paper_data.year or existing_paper.year
            existing_paper.citation_count = paper_data.citationCount or existing_paper.citation_count
            existing_paper.reference_count = paper_data.referenceCount or existing_paper.reference_count
            existing_paper.crawl_status = "completed"
        else:
            # 新規論文の作成
            paper_dict = paper_data.to_paper_create_dict()
            paper_dict["crawl_status"] = "completed"
            paper = Paper(**paper_dict)
            session.add(paper)

        # 著者情報の保存
        if paper_data.authors:
            await self._save_authors(session, paper_data.paperId, paper_data.authors)

        session.commit()

    async def _save_authors(self, session: Session, paper_id: str, authors_data: List) -> None:
        """著者情報を保存."""
        for position, author_data in enumerate(authors_data):
            if not author_data.authorId:
                continue

            # 既存著者チェック
            existing_author = session.query(Author).filter_by(author_id=author_data.authorId).first()

            if not existing_author:
                author = Author(
                    author_id=author_data.authorId,
                    name=author_data.name or "Unknown"
                )
                session.add(author)

            # 論文-著者関係の作成（重複チェック）
            from refnet_shared.models.database import paper_authors
            existing_relation = session.execute(
                paper_authors.select().where(
                    paper_authors.c.paper_id == paper_id,
                    paper_authors.c.author_id == author_data.authorId
                )
            ).fetchone()

            if not existing_relation:
                session.execute(
                    paper_authors.insert().values(
                        paper_id=paper_id,
                        author_id=author_data.authorId,
                        position=position
                    )
                )

    async def _crawl_citations(self, session: Session, paper_id: str, hop_count: int, max_hops: int) -> None:
        """引用論文の収集."""
        try:
            citations = await self.client.get_paper_citations(paper_id, limit=100)

            for citation in citations:
                # 関係の保存
                await self._save_paper_relation(
                    session,
                    source_paper_id=citation.paperId,
                    target_paper_id=paper_id,
                    relation_type="citation",
                    hop_count=hop_count
                )

                # 優先度に基づく再帰的収集
                if await self._should_crawl_recursively(citation, hop_count, max_hops):
                    await self._queue_paper_for_crawling(session, citation.paperId, hop_count)

        except Exception as e:
            logger.error("Failed to crawl citations", paper_id=paper_id, error=str(e))

    async def _crawl_references(self, session: Session, paper_id: str, hop_count: int, max_hops: int) -> None:
        """参考文献の収集."""
        try:
            references = await self.client.get_paper_references(paper_id, limit=100)

            for reference in references:
                # 関係の保存
                await self._save_paper_relation(
                    session,
                    source_paper_id=paper_id,
                    target_paper_id=reference.paperId,
                    relation_type="reference",
                    hop_count=hop_count
                )

                # 優先度に基づく再帰的収集
                if await self._should_crawl_recursively(reference, hop_count, max_hops):
                    await self._queue_paper_for_crawling(session, reference.paperId, hop_count)

        except Exception as e:
            logger.error("Failed to crawl references", paper_id=paper_id, error=str(e))

    async def _save_paper_relation(
        self,
        session: Session,
        source_paper_id: str,
        target_paper_id: str,
        relation_type: str,
        hop_count: int
    ) -> None:
        """論文関係を保存."""
        # 重複チェック
        existing_relation = session.query(PaperRelation).filter_by(
            source_paper_id=source_paper_id,
            target_paper_id=target_paper_id,
            relation_type=relation_type
        ).first()

        if not existing_relation:
            relation = PaperRelation(
                source_paper_id=source_paper_id,
                target_paper_id=target_paper_id,
                relation_type=relation_type,
                hop_count=hop_count
            )
            session.add(relation)

    async def _should_crawl_recursively(
        self,
        paper_data: SemanticScholarPaper,
        hop_count: int,
        max_hops: int
    ) -> bool:
        """再帰的収集の判定."""
        if hop_count >= max_hops:
            return False

        # 優先度計算（引用数、発行年、ホップ数を考慮）
        citation_count = paper_data.citationCount or 0
        year = paper_data.year or 1900

        # 重み付けスコア計算
        citation_score = min(citation_count / 100, 1.0)  # 正規化
        year_score = max(0, (year - 1990) / 34)  # 1990年以降を重視
        hop_penalty = 0.5 ** (hop_count - 1)  # ホップ数による減衰

        priority_score = (citation_score * 0.5 + year_score * 0.3) * hop_penalty

        # 閾値を超えた場合のみ収集
        return priority_score > 0.1

    async def _queue_paper_for_crawling(self, session: Session, paper_id: str, hop_count: int) -> None:
        """論文をクローリングキューに追加."""
        # 既存キューチェック
        existing_queue = session.query(ProcessingQueue).filter_by(
            paper_id=paper_id,
            task_type="crawl",
            status="pending"
        ).first()

        if not existing_queue:
            priority = max(0, 100 - hop_count * 10)  # ホップ数が少ないほど高優先度
            queue_item = ProcessingQueue(
                paper_id=paper_id,
                task_type="crawl",
                priority=priority,
                status="pending"
            )
            session.add(queue_item)

    async def _update_processing_status(
        self,
        session: Session,
        paper_id: str,
        task_type: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """処理状態を更新."""
        queue_item = session.query(ProcessingQueue).filter_by(
            paper_id=paper_id,
            task_type=task_type
        ).first()

        if queue_item:
            queue_item.status = status
            if error_message:
                queue_item.error_message = error_message
                queue_item.retry_count += 1

        # 論文テーブルの状態も更新
        paper = session.query(Paper).filter_by(paper_id=paper_id).first()
        if paper:
            if task_type == "crawl":
                paper.crawl_status = status

    async def close(self) -> None:
        """リソースのクリーンアップ."""
        await self.client.close()
```

### 7. Celeryタスク定義

`src/refnet_crawler/tasks/__init__.py`:

```python
"""Celeryタスク定義."""

import asyncio
from celery import Celery
from refnet_shared.config.environment import load_environment_settings
from refnet_crawler.services.crawler_service import CrawlerService
import structlog


logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# Celeryアプリケーション
celery_app = Celery(
    "refnet_crawler",
    broker=settings.celery_broker_url or settings.redis.url,
    backend=settings.celery_result_backend or settings.redis.url,
    include=["refnet_crawler.tasks"]
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1時間
    task_soft_time_limit=3300,  # 55分
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(bind=True, name="refnet.crawler.crawl_paper")
def crawl_paper_task(self, paper_id: str, hop_count: int = 0, max_hops: int = 3) -> bool:
    """論文クローリングタスク."""
    logger.info("Starting paper crawl task", paper_id=paper_id, hop_count=hop_count)

    async def _crawl():
        crawler = CrawlerService()
        try:
            return await crawler.crawl_paper(paper_id, hop_count, max_hops)
        finally:
            await crawler.close()

    try:
        result = asyncio.run(_crawl())
        logger.info("Paper crawl task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Paper crawl task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(name="refnet.crawler.batch_crawl")
def batch_crawl_task(paper_ids: list[str], hop_count: int = 0, max_hops: int = 3) -> dict:
    """バッチクローリングタスク."""
    logger.info("Starting batch crawl task", paper_count=len(paper_ids))

    results = {}
    for paper_id in paper_ids:
        # 個別タスクとして実行
        result = crawl_paper_task.delay(paper_id, hop_count, max_hops)
        results[paper_id] = result.id

    return results
```

### 8. テストの作成

`tests/test_semantic_scholar_client.py`:

```python
"""Semantic Scholar APIクライアントのテスト."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch
from refnet_crawler.clients.semantic_scholar import SemanticScholarClient
from refnet_crawler.models.paper_data import SemanticScholarPaper


@pytest.fixture
def client():
    """テスト用クライアント."""
    return SemanticScholarClient()


@pytest.fixture
def mock_paper_data():
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
async def test_get_paper_success(client, mock_paper_data):
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
async def test_get_paper_not_found(client):
    """論文取得（存在しない）テスト."""
    with patch.object(client.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=None,
            response=AsyncMock(status_code=404)
        )
        mock_get.return_value = mock_response

        result = await client.get_paper("nonexistent-paper")

        assert result is None


@pytest.mark.asyncio
async def test_get_paper_citations(client, mock_paper_data):
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
async def test_search_papers(client, mock_paper_data):
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
```

### 9. Dockerfileの作成

`Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# システム依存関係
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係
COPY pyproject.toml uv.lock ./
RUN pip install uv
RUN uv sync --frozen

# アプリケーションコピー
COPY src/ ./src/

# 環境変数
ENV PYTHONPATH=/app/src

# 起動コマンド
CMD ["celery", "-A", "refnet_crawler.tasks.celery_app", "worker", "--loglevel=info", "--queue=crawl"]
```

## スコープ

- Semantic Scholar APIクライアント実装
- 論文データの収集・保存
- 引用関係の再帰的収集
- Celeryタスクの実装
- 基本的なテストケース

**スコープ外:**
- 詳細なレート制限対応
- 高度な優先度制御
- 複数API統合
- 大規模データ処理最適化

## 参照するドキュメント

- `/docs/crawler/semantic-scholar-api.md`
- `/docs/development/coding-standards.md`
- `/docs/tasks/phase_02/00_database_models.md`

## 完了条件

### 必須条件
- [ ] Semantic Scholar APIクライアントが実装されている
- [ ] クローラーサービスが実装されている
- [ ] Celeryタスクが実装されている
- [ ] 基本的なテストケースが作成されている
- [ ] Dockerfileが作成されている
- [ ] `cd package/crawler && moon run crawler:check` が正常終了する

### 動作確認
- [ ] 論文データ取得が正常動作
- [ ] 引用・参考文献収集が正常動作
- [ ] Celeryワーカーが正常動作
- [ ] エラーハンドリングが適切に動作

### テスト条件
- [ ] 単体テストが作成されている
- [ ] 統合テストが作成されている
- [ ] テストカバレッジが80%以上
- [ ] 型チェックが通る
- [ ] リントチェックが通る

## トラブルシューティング

### よくある問題

1. **Semantic Scholar API制限エラー**
   - 解決策: APIキー設定、レート制限設定を確認

2. **Celeryタスク実行失敗**
   - 解決策: Redis接続、ワーカー起動状態を確認

3. **データベース保存エラー**
   - 解決策: 外部キー制約、データ型を確認

## 次のタスクへの引き継ぎ

### Phase 4 への前提条件
- クローラーサービスが動作確認済み
- 他のPhase 3サービスとの連携が確認済み
- 基本的なE2Eテストが完了

### 引き継ぎファイル
- `package/crawler/` - クローラーサービス実装
- Semantic Scholar API連携設定
- テストファイル・設定ファイル
