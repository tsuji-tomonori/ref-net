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
    def mock_db(self) -> Mock:
        """モックデータベース."""
        return Mock(spec=Session)

    @pytest.fixture
    def paper_service(self, mock_db: Mock) -> PaperService:
        """論文サービス."""
        with patch('refnet_api.services.paper_service.CeleryService'):
            return PaperService(mock_db)

    def test_get_papers(self, paper_service: PaperService, mock_db: Mock) -> None:
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

    def test_get_paper(self, paper_service: PaperService, mock_db: Mock) -> None:
        """論文取得テスト."""
        # モック設定
        mock_paper = Mock(spec=Paper)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_paper

        # テスト実行
        result = paper_service.get_paper("test-paper-id")

        # 検証
        assert result == mock_paper
        mock_db.query.assert_called_once_with(Paper)

    def test_create_paper(self, paper_service: PaperService, mock_db: Mock) -> None:
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

    def test_update_paper(self, paper_service: PaperService, mock_db: Mock) -> None:
        """論文更新テスト."""
        from refnet_shared.models.schemas import PaperUpdate

        # モック設定
        mock_paper = Mock(spec=Paper)
        mock_paper.paper_id = "test-paper"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_paper

        # テストデータ
        update_data = PaperUpdate(
            title="Updated Title",
            citation_count=100
        )

        # テスト実行
        result = paper_service.update_paper("test-paper", update_data)

        # 検証
        assert result == mock_paper
        assert mock_paper.title == "Updated Title"
        assert mock_paper.citation_count == 100
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_paper)

    def test_update_paper_not_found(self, paper_service: PaperService, mock_db: Mock) -> None:
        """存在しない論文の更新テスト."""
        from refnet_shared.models.schemas import PaperUpdate

        # モック設定
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # テストデータ
        update_data = PaperUpdate(title="Updated Title")

        # テスト実行（例外が発生することを期待）
        with pytest.raises(ValueError, match="Paper not found"):
            paper_service.update_paper("non-existent", update_data)

        # 検証
        mock_db.commit.assert_not_called()

    def test_queue_paper_processing(self, paper_service: PaperService, mock_db: Mock) -> None:
        """論文処理キューイングテスト."""
        from refnet_shared.models.database import ProcessingQueue

        # モック設定
        with patch.object(
            paper_service.celery_service, 'queue_crawl_task', return_value="task-123"
        ) as mock_queue:
            # テスト実行
            result = paper_service.queue_paper_processing("test-paper")

            # 検証
            assert result == "task-123"
            mock_queue.assert_called_once_with("test-paper")

            # ProcessingQueueが追加されたことを確認
            mock_db.add.assert_called_once()
            added_item = mock_db.add.call_args[0][0]
            assert isinstance(added_item, ProcessingQueue)
            assert added_item.paper_id == "test-paper"
            assert added_item.task_type == "crawl"
            assert added_item.status == "pending"
            mock_db.commit.assert_called_once()

    def test_get_paper_relations(self, paper_service: PaperService, mock_db: Mock) -> None:
        """論文関係取得テスト."""
        from refnet_shared.models.database import PaperRelation

        # モック設定
        mock_relations = [Mock(spec=PaperRelation), Mock(spec=PaperRelation)]
        mock_query = Mock()
        mock_query.all.return_value = mock_relations
        mock_db.query.return_value.filter.return_value = mock_query

        # テスト実行
        result = paper_service.get_paper_relations("test-paper")

        # 検証
        assert result == mock_relations
        mock_db.query.assert_called_once_with(PaperRelation)

    def test_get_paper_relations_with_type_filter(
        self, paper_service: PaperService, mock_db: Mock
    ) -> None:
        """タイプフィルタ付き論文関係取得テスト."""
        from refnet_shared.models.database import PaperRelation

        # モック設定
        mock_relations = [Mock(spec=PaperRelation)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_relations
        mock_db.query.return_value.filter.return_value = mock_query

        # テスト実行
        result = paper_service.get_paper_relations("test-paper", "citation")

        # 検証
        assert result == mock_relations
        # filterが2回呼ばれることを確認（1回目: paper_id、2回目: relation_type）
        assert mock_query.filter.call_count == 1


class TestCeleryService:
    """Celeryサービステスト."""

    @pytest.fixture
    def celery_service(self) -> CeleryService:
        """Celeryサービス."""
        with patch('refnet_api.services.celery_service.Celery') as MockCelery:
            mock_app = Mock()
            MockCelery.return_value = mock_app
            service = CeleryService()
            service.celery_app = mock_app
            return service

    def test_queue_crawl_task(self, celery_service: CeleryService) -> None:
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

    def test_get_task_status(self, celery_service: CeleryService) -> None:
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

    def test_queue_summarize_task(self, celery_service: CeleryService) -> None:
        """要約タスクキューテスト."""
        # モック設定
        mock_task = Mock()
        mock_task.id = "summary-task-id"
        celery_service.celery_app.send_task.return_value = mock_task

        # テスト実行
        result = celery_service.queue_summarize_task("test-paper-id")

        # 検証
        assert result == "summary-task-id"
        celery_service.celery_app.send_task.assert_called_once_with(
            "refnet.summarizer.summarize_paper",
            args=["test-paper-id"],
            queue="summarize"
        )

    def test_queue_generate_task(self, celery_service: CeleryService) -> None:
        """生成タスクキューテスト."""
        # モック設定
        mock_task = Mock()
        mock_task.id = "generate-task-id"
        celery_service.celery_app.send_task.return_value = mock_task

        # テスト実行
        result = celery_service.queue_generate_task("test-paper-id")

        # 検証
        assert result == "generate-task-id"
        celery_service.celery_app.send_task.assert_called_once_with(
            "refnet.generator.generate_markdown",
            args=["test-paper-id"],
            queue="generate"
        )
