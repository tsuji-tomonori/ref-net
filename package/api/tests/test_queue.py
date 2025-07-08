"""キューエンドポイントのテスト."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from refnet_shared.models.database import Base, ProcessingQueue
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from refnet_api.dependencies import get_db
from refnet_api.main import app


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """テスト用データベースセッション."""
    engine = create_engine("sqlite:///:memory:")
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
def sample_queue_items(test_db: Session) -> list[ProcessingQueue]:
    """サンプルキューアイテム."""
    items = []
    for i in range(3):
        item = ProcessingQueue(
            paper_id=f"paper-{i}",
            task_type="crawl" if i % 2 == 0 else "pdf",
            status="pending" if i == 0 else "completed",
        )
        test_db.add(item)
        items.append(item)
    test_db.commit()
    return items


def test_get_queue_status(client: TestClient, sample_queue_items: list[ProcessingQueue]) -> None:
    """キューステータス取得のテスト."""
    response = client.get("/api/v1/queue/")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 3
    assert len(data["queue_items"]) == 3

    # アイテムの内容を確認
    for item in data["queue_items"]:
        assert "id" in item
        assert "paper_id" in item
        assert "status" in item
        assert "task_type" in item
        assert "created_at" in item
        assert "updated_at" in item


def test_get_queue_status_with_filters(
    client: TestClient, sample_queue_items: list[ProcessingQueue]
) -> None:
    """フィルタ付きキューステータス取得のテスト."""
    # ステータスでフィルタ
    response = client.get("/api/v1/queue/?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["queue_items"][0]["status"] == "pending"

    # タスクタイプでフィルタ
    response = client.get("/api/v1/queue/?task_type=crawl")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(item["task_type"] == "crawl" for item in data["queue_items"])


def test_get_queue_status_with_pagination(client: TestClient, test_db: Session) -> None:
    """ページネーション付きキューステータス取得のテスト."""
    # 多数のキューアイテムを作成
    for i in range(10):
        item = ProcessingQueue(
            paper_id=f"paper-{i}",
            task_type="crawl",
            status="pending",
        )
        test_db.add(item)
    test_db.commit()

    # ページネーションテスト
    response = client.get("/api/v1/queue/?skip=5&limit=3")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 10
    assert len(data["queue_items"]) == 3


def test_get_task_status(client: TestClient) -> None:
    """タスクステータス取得のテスト."""
    with patch(
        "refnet_api.services.celery_service.CeleryService.get_task_status"
    ) as mock_get_status:
        mock_get_status.return_value = {
            "status": "SUCCESS",
            "result": {"paper_id": "test-paper", "message": "Crawling completed"},
            "progress": 100.0,
        }

        response = client.get("/api/v1/queue/tasks/test-task-id")
        assert response.status_code == 200

        data = response.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "SUCCESS"
        assert data["result"]["paper_id"] == "test-paper"
        assert data["progress"] == 100.0


def test_get_task_status_with_error(client: TestClient) -> None:
    """エラー付きタスクステータス取得のテスト."""
    with patch(
        "refnet_api.services.celery_service.CeleryService.get_task_status"
    ) as mock_get_status:
        mock_get_status.return_value = {
            "status": "FAILURE",
            "error": "Connection timeout",
        }

        response = client.get("/api/v1/queue/tasks/failed-task-id")
        assert response.status_code == 200

        data = response.json()
        assert data["task_id"] == "failed-task-id"
        assert data["status"] == "FAILURE"
        assert data["error"] == "Connection timeout"


def test_get_paper_queue_status(client: TestClient, test_db: Session) -> None:
    """論文のキューステータス取得のテスト."""
    # 特定の論文のキューアイテムを作成
    paper_id = "specific-paper"
    for _, (task_type, status) in enumerate([
        ("crawl", "completed"),
        ("pdf", "processing"),
        ("summary", "pending"),
    ]):
        item = ProcessingQueue(
            paper_id=paper_id,
            task_type=task_type,
            status=status,
        )
        test_db.add(item)
    test_db.commit()

    response = client.get(f"/api/v1/queue/papers/{paper_id}/queue")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 3
    assert len(data["queue_items"]) == 3

    # 全てのアイテムが同じpaper_idを持つことを確認
    assert all(item["paper_id"] == paper_id for item in data["queue_items"])

    # タスクタイプとステータスの確認
    task_types = {item["task_type"] for item in data["queue_items"]}
    statuses = {item["status"] for item in data["queue_items"]}
    assert task_types == {"crawl", "pdf", "summary"}
    assert statuses == {"completed", "processing", "pending"}


def test_get_paper_queue_status_not_found(client: TestClient) -> None:
    """キューアイテムが存在しない論文のテスト."""
    response = client.get("/api/v1/queue/papers/non-existent-paper/queue")
    assert response.status_code == 404
    assert response.json()["detail"] == "No queue items found for this paper"


def test_get_paper_queue_status_empty_db(client: TestClient) -> None:
    """空のデータベースでの論文キューステータス取得テスト."""
    response = client.get("/api/v1/queue/papers/any-paper/queue")
    assert response.status_code == 404
    assert response.json()["detail"] == "No queue items found for this paper"
