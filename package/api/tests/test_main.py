"""メインアプリケーションのテスト."""

import pytest
from fastapi.testclient import TestClient

from refnet_api.main import app


@pytest.fixture
def client() -> TestClient:
    """テストクライアント."""
    return TestClient(app)


def test_root_endpoint(client: TestClient) -> None:
    """ルートエンドポイントテスト."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "message" in data
    assert "RefNet API v0.1.0 -" in data["message"]


def test_health_check(client: TestClient) -> None:
    """ヘルスチェックテスト."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "message" in data


def test_openapi_docs(client: TestClient) -> None:
    """OpenAPI仕様書テスト."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_json(client: TestClient) -> None:
    """OpenAPI JSONテスト."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert data["info"]["title"] == "RefNet API"
