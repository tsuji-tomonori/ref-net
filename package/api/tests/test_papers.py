"""論文エンドポイントのテスト."""

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


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """認証ヘッダー."""
    token = jwt_handler.create_access_token("test_user")
    return {"Authorization": f"Bearer {token}"}


def test_create_paper(client: TestClient, auth_headers: dict[str, str]) -> None:
    """論文作成テスト."""
    paper_data = {
        "paper_id": "test-paper-1",
        "title": "Test Paper",
        "abstract": "Test abstract",
        "year": 2023,
        "citation_count": 10
    }

    response = client.post("/api/v1/papers/", json=paper_data, headers=auth_headers)
    assert response.status_code == 201

    data = response.json()
    assert data["paper_id"] == "test-paper-1"
    assert "message" in data


def test_get_paper(client: TestClient, auth_headers: dict[str, str]) -> None:
    """論文取得テスト."""
    # 論文作成
    paper_data = {
        "paper_id": "test-paper-2",
        "title": "Test Paper 2",
        "year": 2023
    }
    client.post("/api/v1/papers/", json=paper_data, headers=auth_headers)

    # 取得
    response = client.get("/api/v1/papers/test-paper-2")
    assert response.status_code == 200

    data = response.json()
    assert data["paper_id"] == "test-paper-2"
    assert data["title"] == "Test Paper 2"


def test_get_paper_not_found(client: TestClient) -> None:
    """論文取得（存在しない）テスト."""
    response = client.get("/api/v1/papers/nonexistent")
    assert response.status_code == 404


def test_health_check(client: TestClient) -> None:
    """ヘルスチェックテスト."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] in ["healthy", "unhealthy"]
    assert "message" in data
