# Task: APIサービス実装

## タスクの目的

FastAPIを使用してAPIゲートウェイを実装し、論文検索・登録・処理状態管理のエンドポイントを提供する。

## 実施内容

### 1. パッケージ構造の作成

```bash
cd package/api
mkdir -p src/refnet_api/{routers,services,dependencies}
touch src/refnet_api/__init__.py
touch src/refnet_api/main.py
touch src/refnet_api/routers/__init__.py
touch src/refnet_api/services/__init__.py
touch src/refnet_api/dependencies/__init__.py
```

### 2. pyproject.toml の設定

```toml
[project]
name = "refnet-api"
version = "0.1.0"
description = "RefNet API Gateway Service"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.24.0",
    "sqlalchemy>=2.0.0",
    "psycopg2-binary>=2.9.0",
    "celery>=5.3.0",
    "redis>=5.0.0",
    "pydantic>=2.0.0",
    "structlog>=23.0.0",
    "refnet-shared",
    "mypy>=1.16.1",
    "pytest>=8.4.1",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "ruff>=0.12.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
refnet-api = "refnet_api.main:run"

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

  dev:
    command: uvicorn refnet_api.main:app --reload --host 0.0.0.0 --port 8000
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
    command: docker build -t refnet-api .
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

### 4. FastAPIアプリケーション本体

`src/refnet_api/main.py`:

```python
"""RefNet APIメインアプリケーション."""

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from refnet_shared.config import settings
from refnet_shared.utils import setup_logging
from refnet_api.routers import papers, authors, queue


# ロギング設定
setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションライフサイクル管理."""
    logger.info("Starting RefNet API")
    yield
    logger.info("Shutting down RefNet API")


# FastAPIアプリケーション
app = FastAPI(
    title="RefNet API",
    description="論文関係性可視化システム API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に設定
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(papers.router, prefix="/api/v1/papers", tags=["papers"])
app.include_router(authors.router, prefix="/api/v1/authors", tags=["authors"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["queue"])


@app.get("/")
async def root():
    """ルートエンドポイント."""
    return {"message": "RefNet API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """ヘルスチェック."""
    return {"status": "healthy"}


def run() -> None:
    """開発サーバー起動."""
    import uvicorn
    uvicorn.run(
        "refnet_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
```

### 5. 依存関係の定義

`src/refnet_api/dependencies/__init__.py`:

```python
"""FastAPI依存関係."""

from typing import Generator
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from refnet_shared.models.database_manager import db_manager
from refnet_shared.exceptions import DatabaseError
import structlog


logger = structlog.get_logger(__name__)


def get_db() -> Generator[Session, None, None]:
    """データベースセッション取得."""
    try:
        with db_manager.get_session() as session:
            yield session
    except DatabaseError as e:
        logger.error("Database error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection failed"
        )


def get_current_user():
    """現在のユーザー取得（認証実装時に使用）."""
    # TODO: 認証実装
    return {"user_id": "system"}
```

### 6. 論文関連エンドポイント

`src/refnet_api/routers/papers.py`:

```python
"""論文関連エンドポイント."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from refnet_shared.models.database import Paper, Author
from refnet_shared.models.schemas import (
    PaperResponse, PaperCreate, PaperUpdate
)
from refnet_api.dependencies import get_db
from refnet_api.services.paper_service import PaperService
import structlog


logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=List[PaperResponse])
async def get_papers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """論文一覧取得."""
    service = PaperService(db)
    papers = service.get_papers(skip=skip, limit=limit)
    return papers


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(
    paper_id: str,
    db: Session = Depends(get_db)
):
    """論文詳細取得."""
    service = PaperService(db)
    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found"
        )
    return paper


@router.post("/", response_model=PaperResponse)
async def create_paper(
    paper: PaperCreate,
    db: Session = Depends(get_db)
):
    """論文作成."""
    service = PaperService(db)

    # 既存チェック
    existing_paper = service.get_paper(paper.paper_id)
    if existing_paper:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Paper already exists"
        )

    created_paper = service.create_paper(paper)
    return created_paper


@router.put("/{paper_id}", response_model=PaperResponse)
async def update_paper(
    paper_id: str,
    paper_update: PaperUpdate,
    db: Session = Depends(get_db)
):
    """論文更新."""
    service = PaperService(db)

    # 存在チェック
    existing_paper = service.get_paper(paper_id)
    if not existing_paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found"
        )

    updated_paper = service.update_paper(paper_id, paper_update)
    return updated_paper


@router.post("/{paper_id}/process")
async def process_paper(
    paper_id: str,
    db: Session = Depends(get_db)
):
    """論文処理開始."""
    service = PaperService(db)

    # 存在チェック
    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found"
        )

    # 処理キューに追加
    task_id = service.queue_paper_processing(paper_id)

    return {
        "message": "Paper processing started",
        "paper_id": paper_id,
        "task_id": task_id
    }


@router.get("/{paper_id}/status")
async def get_paper_status(
    paper_id: str,
    db: Session = Depends(get_db)
):
    """論文処理状態取得."""
    service = PaperService(db)

    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found"
        )

    return {
        "paper_id": paper_id,
        "crawl_status": paper.crawl_status,
        "pdf_status": paper.pdf_status,
        "summary_status": paper.summary_status,
    }


@router.get("/{paper_id}/relations")
async def get_paper_relations(
    paper_id: str,
    relation_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """論文関係取得."""
    service = PaperService(db)

    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found"
        )

    relations = service.get_paper_relations(paper_id, relation_type)
    return relations
```

### 7. 論文サービスクラス

`src/refnet_api/services/paper_service.py`:

```python
"""論文サービスクラス."""

from typing import List, Optional
from sqlalchemy.orm import Session
from refnet_shared.models.database import Paper, PaperRelation, ProcessingQueue
from refnet_shared.models.schemas import PaperCreate, PaperUpdate
from refnet_api.services.celery_service import CeleryService
import structlog


logger = structlog.get_logger(__name__)


class PaperService:
    """論文サービス."""

    def __init__(self, db: Session):
        """初期化."""
        self.db = db
        self.celery_service = CeleryService()

    def get_papers(self, skip: int = 0, limit: int = 100) -> List[Paper]:
        """論文一覧取得."""
        return self.db.query(Paper).offset(skip).limit(limit).all()

    def get_paper(self, paper_id: str) -> Optional[Paper]:
        """論文取得."""
        return self.db.query(Paper).filter(Paper.paper_id == paper_id).first()

    def create_paper(self, paper_data: PaperCreate) -> Paper:
        """論文作成."""
        paper = Paper(**paper_data.model_dump())
        self.db.add(paper)
        self.db.commit()
        self.db.refresh(paper)

        logger.info("Paper created", paper_id=paper.paper_id)
        return paper

    def update_paper(self, paper_id: str, paper_update: PaperUpdate) -> Paper:
        """論文更新."""
        paper = self.get_paper(paper_id)
        if not paper:
            raise ValueError("Paper not found")

        update_data = paper_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(paper, field, value)

        self.db.commit()
        self.db.refresh(paper)

        logger.info("Paper updated", paper_id=paper.paper_id)
        return paper

    def queue_paper_processing(self, paper_id: str) -> str:
        """論文処理をキューに追加."""
        # クローリングタスクを追加
        task_id = self.celery_service.queue_crawl_task(paper_id)

        # 処理キューに記録
        queue_item = ProcessingQueue(
            paper_id=paper_id,
            task_type="crawl",
            status="pending"
        )
        self.db.add(queue_item)
        self.db.commit()

        logger.info("Paper processing queued", paper_id=paper_id, task_id=task_id)
        return task_id

    def get_paper_relations(
        self,
        paper_id: str,
        relation_type: Optional[str] = None
    ) -> List[PaperRelation]:
        """論文関係取得."""
        query = self.db.query(PaperRelation).filter(
            (PaperRelation.source_paper_id == paper_id) |
            (PaperRelation.target_paper_id == paper_id)
        )

        if relation_type:
            query = query.filter(PaperRelation.relation_type == relation_type)

        return query.all()
```

### 8. Celery統合サービス

`src/refnet_api/services/celery_service.py`:

```python
"""Celery統合サービス."""

from celery import Celery
from refnet_shared.config import settings
import structlog


logger = structlog.get_logger(__name__)


class CeleryService:
    """Celery統合サービス."""

    def __init__(self):
        """初期化."""
        self.celery_app = Celery(
            "refnet",
            broker=settings.redis.url,
            backend=settings.redis.url,
        )

    def queue_crawl_task(self, paper_id: str) -> str:
        """クローリングタスクをキューに追加."""
        task = self.celery_app.send_task(
            "refnet.crawler.crawl_paper",
            args=[paper_id],
            queue="crawl"
        )
        return task.id

    def queue_summarize_task(self, paper_id: str) -> str:
        """要約タスクをキューに追加."""
        task = self.celery_app.send_task(
            "refnet.summarizer.summarize_paper",
            args=[paper_id],
            queue="summarize"
        )
        return task.id

    def queue_generate_task(self, paper_id: str) -> str:
        """生成タスクをキューに追加."""
        task = self.celery_app.send_task(
            "refnet.generator.generate_markdown",
            args=[paper_id],
            queue="generate"
        )
        return task.id

    def get_task_status(self, task_id: str) -> dict:
        """タスク状態取得."""
        task = self.celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": task.status,
            "result": task.result,
        }
```

### 9. テストの作成

`tests/test_papers.py`:

```python
"""論文エンドポイントのテスト."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from refnet_shared.models.database import Base
from refnet_api.main import app
from refnet_api.dependencies import get_db


# テスト用データベース
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """テスト用DB依存関係."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    """テストクライアント."""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def test_create_paper(client):
    """論文作成テスト."""
    paper_data = {
        "paper_id": "test-paper-1",
        "title": "Test Paper",
        "abstract": "Test abstract",
        "year": 2023,
        "citation_count": 10
    }

    response = client.post("/api/v1/papers/", json=paper_data)
    assert response.status_code == 200

    data = response.json()
    assert data["paper_id"] == "test-paper-1"
    assert data["title"] == "Test Paper"


def test_get_paper(client):
    """論文取得テスト."""
    # 論文作成
    paper_data = {
        "paper_id": "test-paper-2",
        "title": "Test Paper 2",
        "year": 2023
    }
    client.post("/api/v1/papers/", json=paper_data)

    # 取得
    response = client.get("/api/v1/papers/test-paper-2")
    assert response.status_code == 200

    data = response.json()
    assert data["paper_id"] == "test-paper-2"
    assert data["title"] == "Test Paper 2"


def test_get_paper_not_found(client):
    """論文取得（存在しない）テスト."""
    response = client.get("/api/v1/papers/nonexistent")
    assert response.status_code == 404


def test_health_check(client):
    """ヘルスチェックテスト."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
```

### 10. Dockerfileの作成

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

# ポート
EXPOSE 8000

# 起動コマンド
CMD ["uvicorn", "refnet_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## スコープ

- FastAPIアプリケーション実装
- 論文・著者・キュー管理エンドポイント
- Celeryタスク統合
- 基本的なテストケース
- Docker化

**スコープ外:**
- 認証・認可機能
- レート制限
- 詳細なエラーハンドリング
- パフォーマンス最適化

## 参照するドキュメント

- `/docs/api/endpoints.md`
- `/docs/development/coding-standards.md`
- `/docs/tasks/10_database_models.md`

## 完了条件

### 機能要件
- [ ] FastAPIアプリケーションが実装されている
- [ ] 論文関連エンドポイントが実装されている
- [ ] 基本的なテストケースが作成されている
- [ ] Dockerfileが作成されている

### パフォーマンス要件
- [ ] 論文検索API（GET /papers）の応答時間が200ms以下である
- [ ] 論文詳細API（GET /papers/{id}）の応答時間が100ms以下である
- [ ] 同時リクエスト処理数が100req/secを維持できる
- [ ] 論文登録API（POST /papers）の応答時間が300ms以下である
- [ ] ヘルスチェックAPI（GET /health）の応答時間が50ms以下である
- [ ] API レート制限（100req/min）が正常に動作する

### スループット要件
- [ ] 1日1,000件の論文処理キュー登録に対応できる
- [ ] ピーク時の同時接続数500に対応できる
- [ ] 平均メモリ使用量が500MB以下である
- [ ] CPU使用率が平均50%以下である（通常時）

### 品質要件
- [ ] `cd package/api && moon check` が正常終了する
- [ ] `cd package/api && moon dev` でサーバーが起動する
- [ ] テストカバレッジが80%以上である
- [ ] APIドキュメント（OpenAPI）が正しく生成される

## レビュー観点

### 技術的正確性
- [ ] FastAPIのルーティングと依存関係注入が適切に実装されている
- [ ] Pydanticモデルによるリクエスト・レスポンス検証が正しく動作する
- [ ] SQLAlchemyセッション管理が適切である
- [ ] Celeryタスクの非同期実行が正しく実装されている
- [ ] エラーハンドリングとHTTPステータスコードが適切である

### 実装可能性
- [ ] データベース接続プールの管理が適切である
- [ ] Celery統合による非同期処理が実装可能である
- [ ] CORSポリシーが開発・本番環境に適している
- [ ] アプリケーションライフサイクル管理が適切である

### 統合考慮事項
- [ ] 他のマイクロサービスとの連携が考慮されている
- [ ] 共通ライブラリ（refnet-shared）の依存関係が適切である
- [ ] データベースとRedisへの接続が確実に行われる
- [ ] Docker環境での動作が保証されている

### 品質基準
- [ ] OpenAPIドキュメントが自動生成され、適切に記述されている
- [ ] バリデーションエラーが適切にハンドリングされている
- [ ] ログ出力が構造化され、監視に適している
- [ ] テストが単体テストと統合テストに分離されている

### セキュリティ考慮事項
- [ ] 入力検証が適切に実装されている
- [ ] SQLインジェクション対策が施されている
- [ ] CORS設定が本番環境で適切に制限されている
- [ ] ログに機密情報が出力されないよう配慮されている

### パフォーマンス考慮事項
- [ ] データベースクエリが効率的である（N+1問題回避）
- [ ] レスポンス時間が適切である
- [ ] ページネーションが実装されている
- [ ] 非同期処理によりAPIの応答性が確保されている

### 保守性
- [ ] サービス層とルーター層の責務が適切に分離されている
- [ ] 新しいエンドポイントの追加が容易である
- [ ] エラーメッセージが開発者にとって理解しやすい
- [ ] 設定の変更が環境変数で制御できる
