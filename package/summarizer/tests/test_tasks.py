"""Celeryタスクのテスト."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from refnet_summarizer.tasks import (
    summarize_paper_task,
    batch_summarize_task,
    celery_app
)


@pytest.fixture
def mock_celery_app():
    """モックCeleryアプリケーション."""
    with patch('refnet_summarizer.tasks.celery_app') as mock_app:
        yield mock_app


@pytest.mark.asyncio
async def test_summarize_paper_task_success():
    """論文要約タスク成功テスト."""
    with patch('refnet_summarizer.tasks.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.return_value = True

        # asyncio.runをモック
        with patch('asyncio.run') as mock_run:
            mock_run.return_value = True

            result = summarize_paper_task("test-paper-123")

            assert result is True
            mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_paper_task_failure():
    """論文要約タスク失敗・リトライテスト."""
    mock_self = MagicMock()
    mock_self.retry = MagicMock(side_effect=Exception("Retry"))

    with patch('refnet_summarizer.tasks.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.side_effect = Exception("Test error")

        with patch('asyncio.run', side_effect=Exception("Test error")):
            with pytest.raises(Exception) as exc_info:
                summarize_paper_task.bind(mock_self)("test-paper-123")

            assert "Retry" in str(exc_info.value)
            mock_self.retry.assert_called_once()


def test_batch_summarize_task():
    """バッチ要約タスクテスト."""
    paper_ids = ["paper-1", "paper-2", "paper-3"]

    with patch.object(summarize_paper_task, 'delay') as mock_delay:
        mock_delay.return_value = MagicMock(id="task-id")

        result = batch_summarize_task(paper_ids)

        assert len(result) == 3
        assert result["paper-1"] == "task-id"
        assert result["paper-2"] == "task-id"
        assert result["paper-3"] == "task-id"
        assert mock_delay.call_count == 3


def test_celery_app_configuration():
    """Celeryアプリケーション設定テスト."""
    from refnet_summarizer.tasks import celery_app

    # 基本設定の確認
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True

    # タイムアウト設定の確認
    assert celery_app.conf.task_time_limit == 1800  # 30分
    assert celery_app.conf.task_soft_time_limit == 1500  # 25分

    # ワーカー設定の確認
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.worker_max_tasks_per_child == 100
