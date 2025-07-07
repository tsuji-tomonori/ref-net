"""メインアプリケーションのテスト."""

import pytest
from fastapi.testclient import TestClient

from refnet_api.main import app


@pytest.fixture
def client():
    """テストクライアント."""
    return TestClient(app)


def test_root_endpoint(client):
    """ルートエンドポイントテスト."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "environment" in data
    assert data["message"] == "RefNet API"
    assert data["version"] == "0.1.0"


def test_health_check(client):
    """ヘルスチェックテスト."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_openapi_docs(client):
    """OpenAPI仕様書テスト."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_json(client):
    """OpenAPI JSONテスト."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert data["info"]["title"] == "RefNet API"
