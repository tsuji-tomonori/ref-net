"""Celeryタスクのテスト."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from celery.exceptions import Retry
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

    @patch("refnet_generator.tasks.generate_markdown_task.retry")
    @patch("refnet_generator.tasks.GeneratorService")
    @patch("refnet_generator.tasks.asyncio.run")
    def test_generate_markdown_task_failure_with_retry(
        self,
        mock_asyncio_run: Mock,
        mock_generator_service: Mock,
        mock_retry: Mock,
    ) -> None:
        """Markdown生成タスクの失敗とリトライのテスト."""
        # モックの設定
        mock_asyncio_run.side_effect = Exception("Generation failed")
        mock_retry.side_effect = Retry("Retrying...")

        # タスクの実行とリトライの確認
        with pytest.raises(Retry):
            generate_markdown_task("paper123")

        mock_retry.assert_called_once()

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
