# Task: 要約サービス実装

## タスクの目的

PDF論文をダウンロードし、テキストを抽出してLLM APIで要約とキーワード生成を行う要約サービスを実装する。Phase 3の中核AI処理サービスとして機能する。

## 前提条件

- Phase 2 が完了している
- データベースモデルが利用可能
- 共通ライブラリ（shared）が利用可能
- 環境設定管理システムが動作
- 外部AI API（OpenAI・Anthropic）のAPIキーが設定済み

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
        """PDFコンテンツのハッシュ計算."""
        return hashlib.sha256(pdf_content).hexdigest()

    async def close(self) -> None:
        """リソースのクリーンアップ."""
        await self.client.aclose()
```

### 5. AI クライアント

`src/refnet_summarizer/clients/ai_client.py`:

```python
"""AI APIクライアント."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import openai
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
from refnet_shared.config.environment import load_environment_settings
from refnet_shared.exceptions import ExternalAPIError
import structlog


logger = structlog.get_logger(__name__)
settings = load_environment_settings()


class AIClient(ABC):
    """AI APIクライアントの基底クラス."""

    @abstractmethod
    async def generate_summary(self, text: str, max_tokens: int = 500) -> str:
        """要約生成."""
        pass

    @abstractmethod
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """キーワード抽出."""
        pass


class OpenAIClient(AIClient):
    """OpenAI APIクライアント."""

    def __init__(self, api_key: Optional[str] = None):
        """初期化."""
        self.client = openai.AsyncOpenAI(
            api_key=api_key or settings.openai_api_key
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def generate_summary(self, text: str, max_tokens: int = 500) -> str:
        """要約生成."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは論文要約の専門家です。以下の論文テキストを読んで、研究内容、手法、結果、意義を含む簡潔で有用な要約を作成してください。要約は日本語で記述し、専門用語は適切に説明してください。"
                    },
                    {
                        "role": "user",
                        "content": f"以下の論文テキストを要約してください（最大{max_tokens}トークン）:\n\n{text[:8000]}"  # APIの制限を考慮
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )

            summary = response.choices[0].message.content
            if not summary:
                raise ExternalAPIError("Empty response from OpenAI")

            logger.info("Summary generated successfully", model="gpt-4o-mini", tokens=len(summary.split()))
            return summary.strip()

        except openai.RateLimitError as e:
            logger.warning("OpenAI rate limit exceeded")
            raise ExternalAPIError("Rate limit exceeded") from e
        except openai.APIError as e:
            logger.error("OpenAI API error", error=str(e))
            raise ExternalAPIError(f"OpenAI API error: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error with OpenAI", error=str(e))
            raise ExternalAPIError(f"Unexpected error: {str(e)}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """キーワード抽出."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": f"以下の論文テキストから重要なキーワードを{max_keywords}個抽出してください。技術用語、手法名、概念名を優先し、カンマ区切りで返してください。"
                    },
                    {
                        "role": "user",
                        "content": text[:4000]  # APIの制限を考慮
                    }
                ],
                max_tokens=200,
                temperature=0.1,
            )

            keywords_text = response.choices[0].message.content
            if not keywords_text:
                return []

            keywords = [kw.strip() for kw in keywords_text.split(',')]
            keywords = [kw for kw in keywords if kw and len(kw) > 1][:max_keywords]

            logger.info("Keywords extracted successfully", count=len(keywords))
            return keywords

        except Exception as e:
            logger.error("Failed to extract keywords with OpenAI", error=str(e))
            return []


class AnthropicClient(AIClient):
    """Anthropic APIクライアント."""

    def __init__(self, api_key: Optional[str] = None):
        """初期化."""
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key or settings.anthropic_api_key
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def generate_summary(self, text: str, max_tokens: int = 500) -> str:
        """要約生成."""
        try:
            response = await self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=max_tokens,
                temperature=0.3,
                messages=[
                    {
                        "role": "user",
                        "content": f"以下の論文テキストを読んで、研究内容、手法、結果、意義を含む簡潔で有用な要約を日本語で作成してください:\n\n{text[:100000]}"
                    }
                ]
            )

            summary = response.content[0].text
            if not summary:
                raise ExternalAPIError("Empty response from Anthropic")

            logger.info("Summary generated successfully", model="claude-3-5-haiku", tokens=len(summary.split()))
            return summary.strip()

        except anthropic.RateLimitError as e:
            logger.warning("Anthropic rate limit exceeded")
            raise ExternalAPIError("Rate limit exceeded") from e
        except anthropic.APIError as e:
            logger.error("Anthropic API error", error=str(e))
            raise ExternalAPIError(f"Anthropic API error: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error with Anthropic", error=str(e))
            raise ExternalAPIError(f"Unexpected error: {str(e)}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> list[str]:
        """キーワード抽出."""
        try:
            response = await self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                temperature=0.1,
                messages=[
                    {
                        "role": "user",
                        "content": f"以下の論文テキストから重要なキーワードを{max_keywords}個抽出してください。技術用語、手法名、概念名を優先し、カンマ区切りで返してください:\n\n{text[:50000]}"
                    }
                ]
            )

            keywords_text = response.content[0].text
            if not keywords_text:
                return []

            keywords = [kw.strip() for kw in keywords_text.split(',')]
            keywords = [kw for kw in keywords if kw and len(kw) > 1][:max_keywords]

            logger.info("Keywords extracted successfully", count=len(keywords))
            return keywords

        except Exception as e:
            logger.error("Failed to extract keywords with Anthropic", error=str(e))
            return []


def create_ai_client() -> AIClient:
    """AI クライアントの作成."""
    if settings.openai_api_key:
        return OpenAIClient()
    elif settings.anthropic_api_key:
        return AnthropicClient()
    else:
        raise ExternalAPIError("No AI API key configured")
```

### 6. 要約サービス

`src/refnet_summarizer/services/summarizer_service.py`:

```python
"""要約サービス."""

from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from refnet_shared.models.database import Paper, ProcessingQueue
from refnet_shared.models.database_manager import db_manager
from refnet_summarizer.processors.pdf_processor import PDFProcessor
from refnet_summarizer.clients.ai_client import create_ai_client
import structlog


logger = structlog.get_logger(__name__)


class SummarizerService:
    """要約サービス."""

    def __init__(self):
        """初期化."""
        self.pdf_processor = PDFProcessor()
        self.ai_client = create_ai_client()

    async def summarize_paper(self, paper_id: str) -> bool:
        """論文要約処理."""
        try:
            with db_manager.get_session() as session:
                # 論文情報取得
                paper = session.query(Paper).filter_by(paper_id=paper_id).first()
                if not paper:
                    logger.warning("Paper not found", paper_id=paper_id)
                    return False

                # PDF URL チェック
                if not paper.pdf_url:
                    logger.warning("No PDF URL available", paper_id=paper_id)
                    await self._update_processing_status(session, paper_id, "summary", "failed", "No PDF URL")
                    return False

                # PDF ダウンロードとテキスト抽出
                pdf_content = await self.pdf_processor.download_pdf(paper.pdf_url)
                if not pdf_content:
                    logger.warning("Failed to download PDF", paper_id=paper_id)
                    await self._update_processing_status(session, paper_id, "summary", "failed", "PDF download failed")
                    return False

                # PDF 情報の更新
                paper.pdf_hash = self.pdf_processor.calculate_hash(pdf_content)
                paper.pdf_size = len(pdf_content)
                paper.pdf_status = "completed"

                # テキスト抽出
                text = self.pdf_processor.extract_text(pdf_content)
                if not text or len(text) < 100:
                    logger.warning("Failed to extract text or text too short", paper_id=paper_id, text_length=len(text))
                    await self._update_processing_status(session, paper_id, "summary", "failed", "Text extraction failed")
                    return False

                logger.info("Text extracted successfully", paper_id=paper_id, text_length=len(text))

                # AI要約生成
                summary = await self.ai_client.generate_summary(text, max_tokens=500)
                if not summary:
                    logger.warning("Failed to generate summary", paper_id=paper_id)
                    await self._update_processing_status(session, paper_id, "summary", "failed", "Summary generation failed")
                    return False

                # キーワード抽出
                keywords = await self.ai_client.extract_keywords(text, max_keywords=10)

                # 論文情報の更新
                paper.summary = summary
                paper.summary_model = self._get_ai_model_name()
                paper.summary_created_at = datetime.utcnow()
                paper.summary_status = "completed"

                # TODO: キーワードの保存（キーワードテーブルがある場合）

                session.commit()
                await self._update_processing_status(session, paper_id, "summary", "completed")

            logger.info("Paper summarized successfully", paper_id=paper_id, summary_length=len(summary), keywords_count=len(keywords))
            return True

        except Exception as e:
            logger.error("Failed to summarize paper", paper_id=paper_id, error=str(e))

            # エラー状態を記録
            with db_manager.get_session() as session:
                await self._update_processing_status(session, paper_id, "summary", "failed", str(e))

            return False

    def _get_ai_model_name(self) -> str:
        """使用中のAIモデル名を取得."""
        if hasattr(self.ai_client, 'client') and hasattr(self.ai_client.client, '_api_key'):
            if 'openai' in str(type(self.ai_client)):
                return "gpt-4o-mini"
            elif 'anthropic' in str(type(self.ai_client)):
                return "claude-3-5-haiku"
        return "unknown"

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
            if task_type == "summary":
                paper.summary_status = status

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
from refnet_shared.config.environment import load_environment_settings
from refnet_summarizer.services.summarizer_service import SummarizerService
import structlog


logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# Celeryアプリケーション
celery_app = Celery(
    "refnet_summarizer",
    broker=settings.celery_broker_url or settings.redis.url,
    backend=settings.celery_result_backend or settings.redis.url,
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
    task_time_limit=1800,  # 30分
    task_soft_time_limit=1500,  # 25分
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,  # メモリリーク対策
)


@celery_app.task(bind=True, name="refnet.summarizer.summarize_paper")
def summarize_paper_task(self, paper_id: str) -> bool:
    """論文要約タスク."""
    logger.info("Starting paper summarization task", paper_id=paper_id)

    async def _summarize():
        service = SummarizerService()
        try:
            return await service.summarize_paper(paper_id)
        finally:
            await service.close()

    try:
        result = asyncio.run(_summarize())
        logger.info("Paper summarization task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Paper summarization task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=300, max_retries=2)  # 5分後にリトライ


@celery_app.task(name="refnet.summarizer.batch_summarize")
def batch_summarize_task(paper_ids: list[str]) -> dict:
    """バッチ要約タスク."""
    logger.info("Starting batch summarization task", paper_count=len(paper_ids))

    results = {}
    for paper_id in paper_ids:
        # 個別タスクとして実行
        result = summarize_paper_task.delay(paper_id)
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
    return b"%PDF-1.4 mock pdf content"


@pytest.mark.asyncio
async def test_download_pdf_success(processor, mock_pdf_content):
    """PDF ダウンロード成功テスト."""
    with patch.object(processor.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.content = mock_pdf_content
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await processor.download_pdf("https://example.com/paper.pdf")

        assert result == mock_pdf_content


@pytest.mark.asyncio
async def test_download_pdf_invalid_content_type(processor):
    """PDF ダウンロード（無効なContent-Type）テスト."""
    with patch.object(processor.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.content = b"not a pdf"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await processor.download_pdf("https://example.com/notpdf.html")

        assert result is None


def test_calculate_hash(processor, mock_pdf_content):
    """ハッシュ計算テスト."""
    hash1 = processor.calculate_hash(mock_pdf_content)
    hash2 = processor.calculate_hash(mock_pdf_content)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256は64文字


def test_clean_text(processor):
    """テキストクリーニングテスト."""
    dirty_text = "Line 1\r\n\r\nLine 2\n\n\n\nLine 3    with   spaces"
    clean_text = processor._clean_text(dirty_text)

    assert "Line 1 Line 2 Line 3 with spaces" in clean_text
    assert "\r" not in clean_text
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

- PDF ダウンロード・テキスト抽出
- AI API を使用した要約生成
- キーワード抽出
- Celeryタスクの実装
- 基本的なテストケース

**スコープ外:**
- 高度なPDF レイアウト解析
- 画像・図表からのテキスト抽出
- 多言語対応
- 要約品質の詳細評価

## 参照するドキュメント

- `/docs/summarizer/ai-integration.md`
- `/docs/development/coding-standards.md`
- `/docs/tasks/phase_02/00_database_models.md`

## 完了条件

### 必須条件
- [ ] PDF処理機能が実装されている
- [ ] AI クライアントが実装されている
- [ ] 要約サービスが実装されている
- [ ] Celeryタスクが実装されている
- [ ] 基本的なテストケースが作成されている
- [ ] Dockerfileが作成されている
- [ ] `cd package/summarizer && moon run summarizer:check` が正常終了する

### 動作確認
- [ ] PDF ダウンロード・テキスト抽出が正常動作
- [ ] AI要約生成が正常動作
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

1. **AI API制限エラー**
   - 解決策: APIキー設定、レート制限設定を確認

2. **PDF テキスト抽出失敗**
   - 解決策: 複数のPDF処理ライブラリを順次試行

3. **メモリ使用量過多**
   - 解決策: バッチサイズ、worker設定を調整

## 次のタスクへの引き継ぎ

### Phase 4 への前提条件
- 要約サービスが動作確認済み
- 他のPhase 3サービスとの連携が確認済み
- 基本的なE2Eテストが完了

### 引き継ぎファイル
- `package/summarizer/` - 要約サービス実装
- AI API連携設定
- テストファイル・設定ファイル
