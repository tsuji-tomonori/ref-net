# Task: 要約サービス実装

## タスクの目的

PDF論文をダウンロードし、テキストを抽出してLLM APIで要約とキーワード生成を行う要約サービスを実装する。

## 実施内容

### 1. パッケージ構造の作成

```bash
cd package/summarizer
mkdir -p src/refnet_summarizer/{services,tasks,clients,processors}
touch src/refnet_summarizer/__init__.py
touch src/refnet_summarizer/main.py
touch src/refnet_summarizer/services/__init__.py
touch src/refnet_summarizer/tasks/__init__.py
touch src/refnet_summarizer/clients/__init__.py
touch src/refnet_summarizer/processors/__init__.py
```

### 2. pyproject.toml の設定

```toml
[project]
name = "refnet-summarizer"
version = "0.1.0"
description = "RefNet PDF Summarizer Service"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "celery>=5.3.0",
    "redis>=5.0.0",
    "httpx>=0.27.0",
    "pypdf2>=3.0.0",
    "pdfplumber>=0.11.0",
    "openai>=1.0.0",
    "anthropic>=0.25.0",
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
refnet-summarizer = "refnet_summarizer.main:main"

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
    command: celery -A refnet_summarizer.tasks.celery_app worker --loglevel=info --queue=summarize
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
    command: docker build -t refnet-summarizer .
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

### 4. PDFプロセッサー

`src/refnet_summarizer/processors/pdf_processor.py`:

```python
"""PDF処理モジュール."""

import hashlib
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import httpx
import PyPDF2
import pdfplumber
from refnet_shared.exceptions import ExternalAPIError
import structlog


logger = structlog.get_logger(__name__)


class PDFProcessor:
    """PDF処理クラス."""

    def __init__(self):
        """初期化."""
        self.client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
        )

    async def download_pdf(self, url: str) -> Optional[bytes]:
        """PDFをダウンロード."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()

            # Content-Typeチェック
            content_type = response.headers.get("content-type", "")
            if "application/pdf" not in content_type:
                logger.warning("Invalid content type", url=url, content_type=content_type)
                return None

            logger.info("PDF downloaded successfully", url=url, size=len(response.content))
            return response.content

        except httpx.HTTPError as e:
            logger.error("Failed to download PDF", url=url, error=str(e))
            return None
        except Exception as e:
            logger.error("Unexpected error downloading PDF", url=url, error=str(e))
            return None

    def extract_text_pypdf2(self, pdf_content: bytes) -> str:
        """PyPDF2でテキスト抽出."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
                tmp_file.write(pdf_content)
                tmp_file.flush()

                with open(tmp_file.name, "rb") as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""

                    for page_num, page in enumerate(pdf_reader.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                        except Exception as e:
                            logger.warning("Failed to extract text from page", page_num=page_num, error=str(e))

                    return text.strip()

        except Exception as e:
            logger.error("Failed to extract text with PyPDF2", error=str(e))
            return ""

    def extract_text_pdfplumber(self, pdf_content: bytes) -> str:
        """pdfplumberでテキスト抽出."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
                tmp_file.write(pdf_content)
                tmp_file.flush()

                with pdfplumber.open(tmp_file.name) as pdf:
                    text = ""

                    for page_num, page in enumerate(pdf.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                text += page_text + "\n"
                        except Exception as e:
                            logger.warning("Failed to extract text from page", page_num=page_num, error=str(e))

                    return text.strip()

        except Exception as e:
            logger.error("Failed to extract text with pdfplumber", error=str(e))
            return ""

    def extract_text(self, pdf_content: bytes) -> str:
        """テキスト抽出（複数手法を試行）."""
        # まずpdfplumberを試行
        text = self.extract_text_pdfplumber(pdf_content)

        # 失敗した場合はPyPDF2を試行
        if not text or len(text) < 100:
            logger.info("Fallback to PyPDF2 for text extraction")
            text = self.extract_text_pypdf2(pdf_content)

        # テキストの後処理
        if text:
            text = self._clean_text(text)

        return text

    def _clean_text(self, text: str) -> str:
        """テキストのクリーニング."""
        # 改行の正規化
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 連続する改行を制限
        lines = text.split("\n")
        cleaned_lines = []
        empty_count = 0

        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
                empty_count = 0
            else:
                empty_count += 1
                if empty_count <= 1:  # 連続する空行は1つまで
                    cleaned_lines.append("")

        # 連続するスペースを制限
        text = "\n".join(cleaned_lines)
        text = " ".join(text.split())

        return text

    def calculate_hash(self, pdf_content: bytes) -> str:
        """PDFのハッシュ値計算."""
        return hashlib.sha256(pdf_content).hexdigest()

    def extract_metadata(self, pdf_content: bytes) -> dict:
        """PDFメタデータ抽出."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_file:
                tmp_file.write(pdf_content)
                tmp_file.flush()

                with open(tmp_file.name, "rb") as file:
                    pdf_reader = PyPDF2.PdfReader(file)

                    metadata = {
                        "page_count": len(pdf_reader.pages),
                        "encrypted": pdf_reader.is_encrypted,
                        "hash": self.calculate_hash(pdf_content),
                        "size": len(pdf_content),
                    }

                    # メタデータ情報の抽出
                    if pdf_reader.metadata:
                        metadata.update({
                            "title": pdf_reader.metadata.get("/Title", ""),
                            "author": pdf_reader.metadata.get("/Author", ""),
                            "subject": pdf_reader.metadata.get("/Subject", ""),
                            "creator": pdf_reader.metadata.get("/Creator", ""),
                            "producer": pdf_reader.metadata.get("/Producer", ""),
                            "creation_date": str(pdf_reader.metadata.get("/CreationDate", "")),
                            "modification_date": str(pdf_reader.metadata.get("/ModDate", "")),
                        })

                    return metadata

        except Exception as e:
            logger.error("Failed to extract PDF metadata", error=str(e))
            return {
                "page_count": 0,
                "encrypted": False,
                "hash": self.calculate_hash(pdf_content),
                "size": len(pdf_content),
            }

    async def process_pdf(self, url: str) -> Optional[Tuple[str, dict]]:
        """PDFの完全処理."""
        # ダウンロード
        pdf_content = await self.download_pdf(url)
        if not pdf_content:
            return None

        # テキスト抽出
        text = self.extract_text(pdf_content)
        if not text:
            logger.warning("No text extracted from PDF", url=url)
            return None

        # メタデータ抽出
        metadata = self.extract_metadata(pdf_content)

        logger.info("PDF processed successfully", url=url, text_length=len(text), **metadata)
        return text, metadata

    async def close(self) -> None:
        """リソースのクリーンアップ."""
        await self.client.aclose()
```

### 5. LLMクライアント

`src/refnet_summarizer/clients/llm_client.py`:

```python
"""LLM APIクライアント."""

from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
import openai
import anthropic
from refnet_shared.config import settings
from refnet_shared.exceptions import ExternalAPIError
import structlog


logger = structlog.get_logger(__name__)


class LLMClient(ABC):
    """LLM APIクライアントの基底クラス."""

    @abstractmethod
    async def generate_summary(self, text: str, max_tokens: int = 500) -> str:
        """要約生成."""
        pass

    @abstractmethod
    async def generate_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """キーワード生成."""
        pass


class OpenAIClient(LLMClient):
    """OpenAI APIクライアント."""

    def __init__(self, api_key: Optional[str] = None):
        """初期化."""
        self.client = openai.AsyncOpenAI(
            api_key=api_key or settings.openai_api_key
        )

    async def generate_summary(self, text: str, max_tokens: int = 500) -> str:
        """要約生成."""
        try:
            # テキストの長さ制限
            if len(text) > 12000:  # GPT-4の制限を考慮
                text = text[:12000] + "..."

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a research assistant. Summarize the following academic paper "
                            "focusing on the main contribution, methodology, and key findings. "
                            "Keep the summary concise and academic in tone."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Please summarize this academic paper:\n\n{text}"
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )

            summary = response.choices[0].message.content.strip()
            logger.info("Summary generated successfully", length=len(summary))
            return summary

        except Exception as e:
            logger.error("Failed to generate summary", error=str(e))
            raise ExternalAPIError(f"OpenAI API error: {str(e)}") from e

    async def generate_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """キーワード生成."""
        try:
            # テキストの長さ制限
            if len(text) > 12000:
                text = text[:12000] + "..."

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a research assistant. Extract key terms and concepts from "
                            "the following academic paper. Return only the keywords/phrases, "
                            "separated by commas, without any additional explanation."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Extract {max_keywords} keywords from this paper:\n\n{text}"
                    }
                ],
                max_tokens=200,
                temperature=0.2,
            )

            keywords_text = response.choices[0].message.content.strip()
            keywords = [kw.strip() for kw in keywords_text.split(",")]
            keywords = [kw for kw in keywords if kw and len(kw) > 2][:max_keywords]

            logger.info("Keywords generated successfully", count=len(keywords))
            return keywords

        except Exception as e:
            logger.error("Failed to generate keywords", error=str(e))
            raise ExternalAPIError(f"OpenAI API error: {str(e)}") from e


class AnthropicClient(LLMClient):
    """Anthropic APIクライアント."""

    def __init__(self, api_key: Optional[str] = None):
        """初期化."""
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.anthropic_api_key
        )

    async def generate_summary(self, text: str, max_tokens: int = 500) -> str:
        """要約生成."""
        try:
            # テキストの長さ制限
            if len(text) > 100000:  # Claudeの制限を考慮
                text = text[:100000] + "..."

            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=max_tokens,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Please summarize the following academic paper focusing on the main "
                            "contribution, methodology, and key findings. Keep the summary "
                            "concise and academic in tone.\n\n"
                            f"Paper content:\n{text}"
                        )
                    }
                ],
            )

            summary = response.content[0].text.strip()
            logger.info("Summary generated successfully", length=len(summary))
            return summary

        except Exception as e:
            logger.error("Failed to generate summary", error=str(e))
            raise ExternalAPIError(f"Anthropic API error: {str(e)}") from e

    async def generate_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """キーワード生成."""
        try:
            # テキストの長さ制限
            if len(text) > 100000:
                text = text[:100000] + "..."

            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                temperature=0.2,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Extract {max_keywords} key terms and concepts from the following "
                            "academic paper. Return only the keywords/phrases, separated by "
                            "commas, without any additional explanation.\n\n"
                            f"Paper content:\n{text}"
                        )
                    }
                ],
            )

            keywords_text = response.content[0].text.strip()
            keywords = [kw.strip() for kw in keywords_text.split(",")]
            keywords = [kw for kw in keywords if kw and len(kw) > 2][:max_keywords]

            logger.info("Keywords generated successfully", count=len(keywords))
            return keywords

        except Exception as e:
            logger.error("Failed to generate keywords", error=str(e))
            raise ExternalAPIError(f"Anthropic API error: {str(e)}") from e


class LLMClientFactory:
    """LLMクライアントファクトリー."""

    @staticmethod
    def create_client(provider: str = "openai") -> LLMClient:
        """クライアント作成."""
        if provider == "openai":
            return OpenAIClient()
        elif provider == "anthropic":
            return AnthropicClient()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
```

### 6. 要約サービス

`src/refnet_summarizer/services/summarizer_service.py`:

```python
"""要約サービス."""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from refnet_shared.models.database import Paper, PaperKeyword, ProcessingQueue
from refnet_shared.models.database_manager import db_manager
from refnet_summarizer.processors.pdf_processor import PDFProcessor
from refnet_summarizer.clients.llm_client import LLMClientFactory
import structlog


logger = structlog.get_logger(__name__)


class SummarizerService:
    """要約サービス."""

    def __init__(self, llm_provider: str = "openai"):
        """初期化."""
        self.pdf_processor = PDFProcessor()
        self.llm_client = LLMClientFactory.create_client(llm_provider)

    async def summarize_paper(self, paper_id: str) -> bool:
        """論文要約処理."""
        try:
            # 論文情報取得
            with db_manager.get_session() as session:
                paper = session.query(Paper).filter_by(paper_id=paper_id).first()
                if not paper:
                    logger.error("Paper not found", paper_id=paper_id)
                    return False

                if not paper.pdf_url:
                    logger.warning("PDF URL not available", paper_id=paper_id)
                    await self._update_processing_status(session, paper_id, "summarize", "failed", "PDF URL not available")
                    return False

                # 処理状態を更新
                await self._update_processing_status(session, paper_id, "summarize", "running")

            # PDF処理
            result = await self.pdf_processor.process_pdf(paper.pdf_url)
            if not result:
                logger.error("Failed to process PDF", paper_id=paper_id)
                with db_manager.get_session() as session:
                    await self._update_processing_status(session, paper_id, "summarize", "failed", "Failed to process PDF")
                return False

            text, metadata = result

            # 要約生成
            summary = await self.llm_client.generate_summary(text)

            # キーワード生成
            keywords = await self.llm_client.generate_keywords(text)

            # 結果保存
            with db_manager.get_session() as session:
                await self._save_summary_results(session, paper_id, summary, keywords, metadata)
                await self._update_processing_status(session, paper_id, "summarize", "completed")

            logger.info("Paper summarized successfully", paper_id=paper_id)
            return True

        except Exception as e:
            logger.error("Failed to summarize paper", paper_id=paper_id, error=str(e))

            with db_manager.get_session() as session:
                await self._update_processing_status(session, paper_id, "summarize", "failed", str(e))

            return False

    async def _save_summary_results(
        self,
        session: Session,
        paper_id: str,
        summary: str,
        keywords: list[str],
        metadata: Dict[str, Any]
    ) -> None:
        """要約結果を保存."""
        # 論文の要約を更新
        paper = session.query(Paper).filter_by(paper_id=paper_id).first()
        if paper:
            paper.summary = summary
            paper.pdf_hash = metadata.get("hash")
            paper.summary_status = "completed"

        # 既存キーワードを削除
        session.query(PaperKeyword).filter_by(paper_id=paper_id).delete()

        # 新しいキーワードを追加
        for keyword in keywords:
            if keyword:
                paper_keyword = PaperKeyword(
                    paper_id=paper_id,
                    keyword=keyword,
                    relevance_score=1.0  # 実際の実装では関連度スコアを計算
                )
                session.add(paper_keyword)

        session.commit()

    async def _update_processing_status(
        self,
        session: Session,
        paper_id: str,
        task_type: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """処理状態を更新."""
        # 処理キューの更新
        queue_item = session.query(ProcessingQueue).filter_by(
            paper_id=paper_id,
            task_type=task_type
        ).first()

        if queue_item:
            queue_item.status = status
            if error_message:
                queue_item.error_message = error_message
                queue_item.retry_count += 1

        # 論文テーブルの状態更新
        paper = session.query(Paper).filter_by(paper_id=paper_id).first()
        if paper and task_type == "summarize":
            paper.summary_status = status

        session.commit()

    async def get_summary_status(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """要約状態取得."""
        with db_manager.get_session() as session:
            paper = session.query(Paper).filter_by(paper_id=paper_id).first()
            if not paper:
                return None

            return {
                "paper_id": paper_id,
                "summary_status": paper.summary_status,
                "has_summary": bool(paper.summary),
                "summary_length": len(paper.summary) if paper.summary else 0,
                "keyword_count": len(paper.keywords),
            }

    async def close(self) -> None:
        """リソースのクリーンアップ."""
        await self.pdf_processor.close()
```

### 7. Celeryタスク定義

`src/refnet_summarizer/tasks/__init__.py`:

```python
"""Celeryタスク定義."""

import asyncio
from celery import Celery
from refnet_shared.config import settings
from refnet_summarizer.services.summarizer_service import SummarizerService
import structlog


logger = structlog.get_logger(__name__)

# Celeryアプリケーション
celery_app = Celery(
    "refnet_summarizer",
    broker=settings.redis.url,
    backend=settings.redis.url,
    include=["refnet_summarizer.tasks"]
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
    worker_max_tasks_per_child=100,
)


@celery_app.task(bind=True, name="refnet.summarizer.summarize_paper")
def summarize_paper_task(self, paper_id: str, llm_provider: str = "openai") -> bool:
    """論文要約タスク."""
    logger.info("Starting paper summarization task", paper_id=paper_id)

    async def _summarize():
        summarizer = SummarizerService(llm_provider)
        try:
            return await summarizer.summarize_paper(paper_id)
        finally:
            await summarizer.close()

    try:
        result = asyncio.run(_summarize())
        logger.info("Paper summarization task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Paper summarization task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(name="refnet.summarizer.batch_summarize")
def batch_summarize_task(paper_ids: list[str], llm_provider: str = "openai") -> dict:
    """バッチ要約タスク."""
    logger.info("Starting batch summarization task", paper_count=len(paper_ids))

    results = {}
    for paper_id in paper_ids:
        result = summarize_paper_task.delay(paper_id, llm_provider)
        results[paper_id] = result.id

    return results
```

### 8. テストの作成

`tests/test_pdf_processor.py`:

```python
"""PDF処理のテスト."""

import pytest
from unittest.mock import AsyncMock, patch, mock_open
from refnet_summarizer.processors.pdf_processor import PDFProcessor


@pytest.fixture
def processor():
    """テスト用プロセッサー."""
    return PDFProcessor()


@pytest.fixture
def mock_pdf_content():
    """モックPDFコンテンツ."""
    return b"%PDF-1.4\ntest content"


@pytest.mark.asyncio
async def test_download_pdf_success(processor, mock_pdf_content):
    """PDF ダウンロード成功テスト."""
    with patch.object(processor.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.content = mock_pdf_content
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await processor.download_pdf("https://example.com/test.pdf")

        assert result == mock_pdf_content


@pytest.mark.asyncio
async def test_download_pdf_invalid_content_type(processor):
    """PDF ダウンロード（不正なコンテンツタイプ）テスト."""
    with patch.object(processor.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.content = b"not pdf content"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await processor.download_pdf("https://example.com/test.pdf")

        assert result is None


def test_calculate_hash(processor, mock_pdf_content):
    """ハッシュ計算テスト."""
    hash_value = processor.calculate_hash(mock_pdf_content)

    assert len(hash_value) == 64  # SHA256ハッシュ
    assert hash_value == processor.calculate_hash(mock_pdf_content)  # 同じ内容は同じハッシュ


def test_clean_text(processor):
    """テキストクリーニングテスト."""
    dirty_text = "line1\n\n\nline2\r\nline3\r\r\nline4"
    cleaned = processor._clean_text(dirty_text)

    assert "\r" not in cleaned
    assert "\n\n\n" not in cleaned
    assert "line1" in cleaned
    assert "line4" in cleaned


@pytest.mark.asyncio
async def test_process_pdf_success(processor, mock_pdf_content):
    """PDF処理成功テスト."""
    with patch.object(processor, 'download_pdf') as mock_download, \
         patch.object(processor, 'extract_text') as mock_extract, \
         patch.object(processor, 'extract_metadata') as mock_metadata:

        mock_download.return_value = mock_pdf_content
        mock_extract.return_value = "extracted text"
        mock_metadata.return_value = {"page_count": 1}

        result = await processor.process_pdf("https://example.com/test.pdf")

        assert result is not None
        text, metadata = result
        assert text == "extracted text"
        assert metadata["page_count"] == 1
```

`tests/test_llm_client.py`:

```python
"""LLMクライアントのテスト."""

import pytest
from unittest.mock import AsyncMock, patch
from refnet_summarizer.clients.llm_client import OpenAIClient, AnthropicClient


@pytest.fixture
def openai_client():
    """テスト用OpenAIクライアント."""
    return OpenAIClient()


@pytest.fixture
def anthropic_client():
    """テスト用Anthropicクライアント."""
    return AnthropicClient()


@pytest.mark.asyncio
async def test_openai_generate_summary(openai_client):
    """OpenAI要約生成テスト."""
    with patch.object(openai_client.client.chat.completions, 'create') as mock_create:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = "Generated summary"
        mock_create.return_value = mock_response

        result = await openai_client.generate_summary("Test paper content")

        assert result == "Generated summary"
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_openai_generate_keywords(openai_client):
    """OpenAIキーワード生成テスト."""
    with patch.object(openai_client.client.chat.completions, 'create') as mock_create:
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message.content = "keyword1, keyword2, keyword3"
        mock_create.return_value = mock_response

        result = await openai_client.generate_keywords("Test paper content")

        assert result == ["keyword1", "keyword2", "keyword3"]
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_anthropic_generate_summary(anthropic_client):
    """Anthropic要約生成テスト."""
    with patch.object(anthropic_client.client.messages, 'create') as mock_create:
        mock_response = AsyncMock()
        mock_response.content = [AsyncMock()]
        mock_response.content[0].text = "Generated summary"
        mock_create.return_value = mock_response

        result = await anthropic_client.generate_summary("Test paper content")

        assert result == "Generated summary"
        mock_create.assert_called_once()
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
CMD ["celery", "-A", "refnet_summarizer.tasks.celery_app", "worker", "--loglevel=info", "--queue=summarize"]
```

## スコープ

- PDF処理（ダウンロード・テキスト抽出）
- LLM API統合（OpenAI・Anthropic）
- 要約・キーワード生成
- Celeryタスク実装
- 基本的なテストケース

**スコープ外:**
- 画像・図表の処理
- 高度な自然言語処理
- カスタムLLMモデル対応
- 大規模PDF処理最適化

## 参照するドキュメント

- `/docs/summarizer/llm-integration.md`
- `/docs/development/coding-standards.md`
- `/docs/tasks/10_database_models.md`

## 完了条件

### 機能要件
- [ ] PDF処理機能が実装されている
- [ ] LLMクライアントが実装されている
- [ ] 要約サービスが実装されている
- [ ] Celeryタスクが実装されている
- [ ] 基本的なテストケースが作成されている
- [ ] Dockerfileが作成されている

### パフォーマンス要件
- [ ] PDF解析処理時間が10MB以下のファイルで30秒以内である
- [ ] LLM要約生成時間が1論文あたり60秒以内である（GPT-4 Turbo）
- [ ] テキスト抽出精度が95%以上である（目視確認ベース）
- [ ] 同時処理可能な要約タスク数が10件以上である
- [ ] バッチ処理で1時間に50論文の要約生成が可能である

### 品質要件
- [ ] 要約文字数が400-800文字の範囲に収まる
- [ ] 要約品質スコアが0.8以上である（手動評価ベース）
- [ ] PDF処理エラー率が5%未満である
- [ ] LLM API呼び出し成功率が98%以上である

### システム要件
- [ ] `cd package/summarizer && moon check` が正常終了する
- [ ] テストカバレッジが80%以上である
- [ ] メモリ使用量がタスクあたり1GB以下である
- [ ] ディスク使用量がタスクあたり100MB以下である（一時ファイル除く）

## レビュー観点

### 技術的正確性
- [ ] PDF処理ライブラリ（PyPDF2、pdfplumber）の実装が適切である
- [ ] OpenAI・Anthropic APIクライアントの実装が正しい
- [ ] HTTPクライアント（httpx）による非同期ダウンロードが適切である
- [ ] Celeryタスクの定義とエラーハンドリングが正しい
- [ ] テキスト抽出の精度向上のための複数手法実装がある

### 実装可能性
- [ ] 大きなPDFファイルの処理が可能である
- [ ] LLM APIの制限（トークン数、レート制限）に対応している
- [ ] メモリ効率的なPDF処理が実装されている
- [ ] 長時間実行タスクのタイムアウト設定が適切である

### 統合考慮事項
- [ ] データベースモデルとの整合性が保たれている
- [ ] クローラーサービスからのデータ受け取りが適切である
- [ ] 共通ライブラリ（refnet-shared）との依存関係が適切である
- [ ] ファイルシステムや一時ファイルの管理が適切である

### 品質基準
- [ ] PDFの破損やテキスト抽出失敗への対応が適切である
- [ ] LLM APIエラーへの適切な対応がある
- [ ] ログ出力が適切で監視・デバッグに役立つ
- [ ] テストでモック化が適切に行われている

### セキュリティ考慮事項
- [ ] API キーが安全に管理されている
- [ ] ダウンロードするPDFの検証が行われている
- [ ] 一時ファイルが適切にクリーンアップされている
- [ ] 悪意のあるPDFに対する防御が考慮されている

### パフォーマンス考慮事項
- [ ] PDF処理とLLM API呼び出しの最適化がされている
- [ ] テキスト長制限に応じた適切な分割処理がある
- [ ] キーワード抽出の精度と処理時間のバランスが適切である
- [ ] バッチ処理による効率化が考慮されている

### 保守性
- [ ] 新しいLLMプロバイダーの追加が容易である
- [ ] PDFライブラリの変更・追加が容易である
- [ ] プロンプトの変更・改善が容易である
- [ ] エラー発生時の調査・復旧が容易である
