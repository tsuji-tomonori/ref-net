"""サービスクラスのテスト."""

from unittest.mock import Mock, patch

import pytest
from refnet_shared.models.database import Paper
from refnet_shared.models.schemas import PaperCreate
from sqlalchemy.orm import Session

from refnet_api.services.celery_service import CeleryService
from refnet_api.services.paper_service import PaperService


class TestPaperService:
    """論文サービステスト."""

    @pytest.fixture
    def mock_db(self):
        """モックデータベース."""
        return Mock(spec=Session)

    @pytest.fixture
    def paper_service(self, mock_db):
        """論文サービス."""
        with patch('refnet_api.services.paper_service.CeleryService'):
            return PaperService(mock_db)

    def test_get_papers(self, paper_service, mock_db):
        """論文一覧取得テスト."""
        # モック設定
        mock_papers = [Mock(spec=Paper), Mock(spec=Paper)]
        mock_db.query.return_value.offset.return_value.limit.return_value.all.return_value = (
            mock_papers
        )

        # テスト実行
        result = paper_service.get_papers(skip=0, limit=10)

        # 検証
        assert result == mock_papers
        mock_db.query.assert_called_once_with(Paper)

    def test_get_paper(self, paper_service, mock_db):
        """論文取得テスト."""
        # モック設定
        mock_paper = Mock(spec=Paper)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_paper

        # テスト実行
        result = paper_service.get_paper("test-paper-id")

        # 検証
        assert result == mock_paper
        mock_db.query.assert_called_once_with(Paper)

    def test_create_paper(self, paper_service, mock_db):
        """論文作成テスト."""
        # テストデータ
        paper_data = PaperCreate(
            paper_id="test-paper",
            title="Test Paper",
            year=2023
        )

        # テスト実行
        paper_service.create_paper(paper_data)

        # 検証 - 実際のPaperインスタンスが作成されることを確認
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        # 追加されたオブジェクトがPaperインスタンスであることを確認
        added_instance = mock_db.add.call_args[0][0]
        assert isinstance(added_instance, Paper)


class TestCeleryService:
    """Celeryサービステスト."""

    @pytest.fixture
    def celery_service(self):
        """Celeryサービス."""
        with patch('refnet_api.services.celery_service.Celery') as MockCelery:
            mock_app = Mock()
            MockCelery.return_value = mock_app
            service = CeleryService()
            service.celery_app = mock_app
            return service

    def test_queue_crawl_task(self, celery_service):
        """クローリングタスクキューテスト."""
        # モック設定
        mock_task = Mock()
        mock_task.id = "test-task-id"
        celery_service.celery_app.send_task.return_value = mock_task

        # テスト実行
        result = celery_service.queue_crawl_task("test-paper-id")

        # 検証
        assert result == "test-task-id"
        celery_service.celery_app.send_task.assert_called_once_with(
            "refnet.crawler.crawl_paper",
            args=["test-paper-id"],
            queue="crawl"
        )

    def test_get_task_status(self, celery_service):
        """タスク状態取得テスト."""
        # モック設定
        mock_task = Mock()
        mock_task.status = "SUCCESS"
        mock_task.result = {"result": "completed"}
        celery_service.celery_app.AsyncResult.return_value = mock_task

        # テスト実行
        result = celery_service.get_task_status("test-task-id")

        # 検証
        expected = {
            "task_id": "test-task-id",
            "status": "SUCCESS",
            "result": {"result": "completed"}
        }
        assert result == expected
