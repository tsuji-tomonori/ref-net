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
