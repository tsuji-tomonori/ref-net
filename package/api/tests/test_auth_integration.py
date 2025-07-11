"""認証統合テスト."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from refnet_shared.auth.jwt_handler import jwt_handler
from refnet_shared.models.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from refnet_api.dependencies import get_db
from refnet_api.main import app


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """テスト用データベースセッション."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db: Session) -> Generator[TestClient, None, None]:
    """テスト用FastAPIクライアント."""
    app.dependency_overrides[get_db] = lambda: test_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_papers_endpoint_without_auth(client: TestClient) -> None:
    """認証なしでの論文一覧アクセステスト."""
    response = client.get("/api/v1/papers/")
    assert response.status_code == 403


def test_papers_endpoint_with_valid_token(client: TestClient) -> None:
    """有効なトークンでの論文一覧アクセステスト."""
    # テスト用トークン生成
    token = jwt_handler.create_access_token("test_user")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/papers/", headers=headers)
    assert response.status_code == 200


def test_papers_endpoint_with_invalid_token(client: TestClient) -> None:
    """無効なトークンでの論文一覧アクセステスト."""
    headers = {"Authorization": "Bearer invalid_token"}

    response = client.get("/api/v1/papers/", headers=headers)
    assert response.status_code == 401


def test_create_paper_endpoint_with_auth(client: TestClient) -> None:
    """認証付き論文作成エンドポイントテスト."""
    token = jwt_handler.create_access_token("test_user")
    headers = {"Authorization": f"Bearer {token}"}

    paper_data = {
        "paper_id": "test_paper_123",
        "title": "Test Paper",
        "arxiv_id": "test_arxiv_123",
        "authors": ["Test Author"],
        "abstract": "Test abstract",
        "published_date": "2023-01-01",
        "url": "https://example.com/paper",
        "pdf_url": "https://example.com/paper.pdf"
    }

    response = client.post("/api/v1/papers/", json=paper_data, headers=headers)
    assert response.status_code == 201


def test_create_paper_endpoint_without_auth(client: TestClient) -> None:
    """認証なし論文作成エンドポイントテスト."""
    paper_data = {
        "paper_id": "test_paper_456",
        "title": "Test Paper",
        "arxiv_id": "test_arxiv_456",
        "authors": ["Test Author"],
        "abstract": "Test abstract",
        "published_date": "2023-01-01",
        "url": "https://example.com/paper",
        "pdf_url": "https://example.com/paper.pdf"
    }

    response = client.post("/api/v1/papers/", json=paper_data)
    assert response.status_code == 403


def test_update_paper_endpoint_with_auth(client: TestClient) -> None:
    """認証付き論文更新エンドポイントテスト."""
    token = jwt_handler.create_access_token("test_user")
    headers = {"Authorization": f"Bearer {token}"}

    # まず論文を作成
    paper_data = {
        "paper_id": "test_paper_789",
        "title": "Test Paper",
        "arxiv_id": "test_arxiv_789",
        "authors": ["Test Author"],
        "abstract": "Test abstract",
        "published_date": "2023-01-01",
        "url": "https://example.com/paper",
        "pdf_url": "https://example.com/paper.pdf"
    }

    create_response = client.post("/api/v1/papers/", json=paper_data, headers=headers)
    assert create_response.status_code == 201

    # 更新テスト
    update_data = {
        "title": "Updated Test Paper",
        "abstract": "Updated abstract"
    }

    response = client.put("/api/v1/papers/test_paper_789", json=update_data, headers=headers)
    assert response.status_code == 200


def test_update_paper_endpoint_without_auth(client: TestClient) -> None:
    """認証なし論文更新エンドポイントテスト."""
    update_data = {
        "title": "Updated Test Paper",
        "abstract": "Updated abstract"
    }

    response = client.put("/api/v1/papers/test_paper_nonexistent", json=update_data)
    assert response.status_code == 403
