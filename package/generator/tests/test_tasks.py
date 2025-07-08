"""Celeryタスクのテスト."""

from unittest.mock import Mock, patch

import pytest

from refnet_generator.tasks import batch_generate_task, generate_markdown_task


class TestCeleryTasks:
    """Celeryタスクのテストクラス."""

    @patch("refnet_generator.tasks.GeneratorService")
    @patch("refnet_generator.tasks.asyncio.run")
    def test_generate_markdown_task_success(
        self,
        mock_asyncio_run: Mock,
        mock_generator_service: Mock,
    ) -> None:
        """Markdown生成タスクの正常系テスト."""
        # モックの設定
        mock_asyncio_run.return_value = True

        # タスクの実行
        result = generate_markdown_task("paper123")

        # アサーション
        assert result is True
        mock_asyncio_run.assert_called_once()

    @patch("refnet_generator.tasks.logger")
    def test_generate_markdown_task_success_logging(
        self,
        mock_logger: Mock,
    ) -> None:
        """成功時のログ出力テスト."""
        with patch("refnet_generator.tasks.GeneratorService"):
            with patch("refnet_generator.tasks.asyncio.run", return_value=True):
                result = generate_markdown_task("test_paper")

                assert result is True
                mock_logger.info.assert_any_call(
                    "Starting markdown generation task", paper_id="test_paper"
                )
                mock_logger.info.assert_any_call(
                    "Markdown generation task completed", paper_id="test_paper", success=True
                )

    def test_generate_markdown_task_celery_retry_path(self) -> None:
        """Celeryリトライパスのテスト."""
        # Exception処理パスのカバレッジ確保のため
        # 簡略化したテスト

        mock_exception = Exception("Test exception")

        with patch("refnet_generator.tasks.GeneratorService"):
            with patch("refnet_generator.tasks.asyncio.run", side_effect=mock_exception):
                with patch("refnet_generator.tasks.logger") as mock_logger:
                    # Exception発生を確認
                    with pytest.raises(Exception, match="Test exception"):
                        generate_markdown_task("test_paper")

                    # エラーログが呼ばれることを確認
                    mock_logger.error.assert_called_with(
                        "Markdown generation task failed",
                        paper_id="test_paper",
                        error="Test exception",
                    )

    @patch("refnet_generator.tasks.generate_markdown_task.delay")
    def test_batch_generate_task(
        self,
        mock_generate_delay: Mock,
    ) -> None:
        """バッチ生成タスクのテスト."""
        # モックの設定
        mock_result1 = Mock()
        mock_result1.id = "task-id-1"
        mock_result2 = Mock()
        mock_result2.id = "task-id-2"
        mock_generate_delay.side_effect = [mock_result1, mock_result2]

        # タスクの実行
        paper_ids = ["paper123", "paper456"]
        results = batch_generate_task(paper_ids)

        # アサーション
        assert results == {"paper123": "task-id-1", "paper456": "task-id-2"}
        assert mock_generate_delay.call_count == 2
        mock_generate_delay.assert_any_call("paper123")
        mock_generate_delay.assert_any_call("paper456")

    def test_batch_generate_task_empty_list(self) -> None:
        """空のリストでのバッチ生成タスクのテスト."""
        # タスクの実行
        results = batch_generate_task([])

        # アサーション
        assert results == {}

    @patch("refnet_generator.tasks.generate_markdown_task.delay")
    def test_batch_generate_task_single_paper(
        self,
        mock_generate_delay: Mock,
    ) -> None:
        """単一論文でのバッチ生成タスクのテスト."""
        # モックの設定
        mock_result = Mock()
        mock_result.id = "task-id-1"
        mock_generate_delay.return_value = mock_result

        # タスクの実行
        results = batch_generate_task(["paper123"])

        # アサーション
        assert results == {"paper123": "task-id-1"}
        mock_generate_delay.assert_called_once_with("paper123")
