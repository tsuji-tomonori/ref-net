"""生成タスクのテスト."""

from unittest.mock import MagicMock, patch

import pytest

from refnet_generator.tasks.generate_task import generate_markdown, generate_pending_markdowns


class TestGenerateTask:
    """生成タスクのテストクラス."""

    @patch("refnet_generator.tasks.generate_task.db_manager")
    def test_generate_pending_markdowns_success(self, mock_db_manager: MagicMock) -> None:
        """generate_pending_markdowns正常系テスト."""
        # モックの設定
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session

        # 生成待ちの論文をモック
        mock_paper = MagicMock()
        mock_paper.paper_id = "test-paper-id"
        mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = [
            mock_paper
        ]

        # apply_asyncのモック
        with patch(
            "refnet_generator.tasks.generate_task.generate_markdown.apply_async"
        ) as mock_apply:
            result = generate_pending_markdowns()

            # 結果の検証
            assert result["status"] == "success"
            assert result["scheduled_papers"] == 1
            assert "timestamp" in result

            # apply_asyncが呼ばれたか確認
            mock_apply.assert_called_once_with(args=["test-paper-id"], queue="generator")

    @patch("refnet_generator.tasks.generate_task.db_manager")
    def test_generate_pending_markdowns_no_papers(self, mock_db_manager: MagicMock) -> None:
        """generate_pending_markdowns生成待ち論文なしテスト."""
        # モックの設定
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter.return_value.limit.return_value.all.return_value = []

        result = generate_pending_markdowns()

        assert result["status"] == "success"
        assert result["scheduled_papers"] == 0

    @patch("refnet_generator.tasks.generate_task.db_manager")
    def test_generate_pending_markdowns_exception(self, mock_db_manager: MagicMock) -> None:
        """generate_pending_markdowns例外発生テスト."""
        # 例外を発生させる
        mock_db_manager.get_session.side_effect = Exception("Database error")

        # retryをモック
        with patch(
            "refnet_generator.tasks.generate_task.generate_pending_markdowns.retry"
        ) as mock_retry:
            mock_retry.side_effect = Exception("Retry exception")

            with pytest.raises(Exception, match="Retry exception"):
                generate_pending_markdowns()

    @patch("refnet_generator.tasks.generate_task.db_manager")
    @patch("refnet_generator.tasks.generate_task.GeneratorService")
    def test_generate_markdown_success(
        self, mock_generator_service: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """generate_markdown正常系テスト."""
        # データベースセッションのモック
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session

        # 論文データのモック
        mock_paper = MagicMock()
        mock_paper.paper_id = "test-paper-id"
        mock_paper.title = "Test Paper"
        mock_paper.crawl_depth = 0  # 明示的に数値を設定
        mock_session.query.return_value.filter.return_value.first.return_value = mock_paper

        # 関連論文のモック
        mock_session.query.return_value.join.return_value.filter.return_value.all.return_value = []

        # GeneratorServiceのモック
        mock_service = MagicMock()
        mock_generator_service.return_value = mock_service
        mock_service.generate_paper_markdown_sync.return_value = "# Test Markdown"

        with patch("refnet_generator.tasks.generate_task.Path.mkdir"), \
             patch("refnet_generator.tasks.generate_task.open", create=True):
            result = generate_markdown("test-paper-id")

        assert result["status"] == "success"

    @patch("refnet_generator.tasks.generate_task.db_manager")
    @patch("refnet_generator.tasks.generate_task.GeneratorService")
    def test_generate_markdown_failure(
        self, mock_generator_service: MagicMock, mock_db_manager: MagicMock
    ) -> None:
        """generate_markdown失敗テスト（論文が見つからない場合）."""
        # データベースセッションのモック
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session

        # 論文が見つからない場合
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # retryをモック
        with patch(
            "refnet_generator.tasks.generate_task.generate_markdown.retry"
        ) as mock_retry:
            mock_retry.side_effect = Exception("Retry exception")

            with pytest.raises(Exception, match="Retry exception"):
                generate_markdown("test-paper-id")

    @patch("refnet_generator.tasks.generate_task.GeneratorService")
    def test_generate_markdown_exception(self, mock_generator_service: MagicMock) -> None:
        """generate_markdown例外発生テスト."""
        # 例外を発生させる
        mock_service = MagicMock()
        mock_generator_service.return_value = mock_service
        mock_service.generate_markdown.side_effect = Exception("Generation error")

        # retryをモック
        with patch(
            "refnet_generator.tasks.generate_task.generate_markdown.retry"
        ) as mock_retry:
            mock_retry.side_effect = Exception("Retry exception")

            with pytest.raises(Exception, match="Retry exception"):
                generate_markdown("test-paper-id")
