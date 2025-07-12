"""Celeryタスクのテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from refnet_summarizer.tasks import (
    batch_summarize_task,
    summarize_paper_task,
)


@pytest.fixture
def mock_celery_app():  # type: ignore
    """モックCeleryアプリケーション."""
    with patch('refnet_summarizer.tasks.celery_app') as mock_app:
        yield mock_app


def test_summarize_paper_task_success():  # type: ignore
    """論文要約タスク成功テスト."""
    with patch('refnet_summarizer.tasks.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.return_value = True
        mock_service.close.return_value = None

        result = summarize_paper_task("test-paper-123")

        assert result is True
        mock_service.summarize_paper.assert_called_once_with("test-paper-123")
        mock_service.close.assert_called_once()


def test_summarize_paper_task_failure():  # type: ignore
    """論文要約タスク失敗テスト."""
    # タスクが例外をキャッチして適切にログを出力することをテスト

    # SummarizerServiceをモック化してより直接的にテスト
    with patch('refnet_summarizer.tasks.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.side_effect = Exception("Service error")

        with patch('refnet_summarizer.tasks.logger') as mock_logger:
            with patch('structlog.get_logger', return_value=mock_logger):
                # Celeryタスクのretryメカニズムをモック化
                with patch.object(
                    summarize_paper_task, 'retry', side_effect=Exception("Retry")
                ):  # type: ignore
                    with pytest.raises(Exception) as exc_info:
                        summarize_paper_task("test-paper-123")

                    # リトライ例外が発生することを確認
                    assert "Retry" in str(exc_info.value)
                    # ログが呼ばれることを確認
                    mock_logger.info.assert_called()
                    mock_logger.error.assert_called()


def test_batch_summarize_task():  # type: ignore
    """バッチ要約タスクテスト."""
    paper_ids = ["paper-1", "paper-2", "paper-3"]

    # ロガーとstructlogをモック化して警告を回避
    with patch('refnet_summarizer.tasks.logger') as mock_logger:
        with patch('structlog.get_logger', return_value=mock_logger):
            with patch.object(summarize_paper_task, 'delay') as mock_delay:
                mock_task = MagicMock()
                mock_task.id = "task-id"
                mock_delay.return_value = mock_task

                result = batch_summarize_task(paper_ids)

                assert len(result) == 3
                assert result["paper-1"] == "task-id"
                assert result["paper-2"] == "task-id"
                assert result["paper-3"] == "task-id"
                assert mock_delay.call_count == 3


def test_celery_app_configuration():  # type: ignore
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


def test_summarize_paper_task_exception_in_service():  # type: ignore
    """サービス内で例外が発生した場合のテスト."""
    # SummarizerServiceをモック化してより直接的にテスト
    with patch('refnet_summarizer.tasks.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.side_effect = Exception("Service error")

        with patch.object(
            summarize_paper_task, 'retry', side_effect=Exception("Retry")
        ):  # type: ignore
            with pytest.raises(Exception):  # type: ignore  # noqa: B017
                summarize_paper_task("test-paper-123")


def test_batch_summarize_task_multiple_papers():  # type: ignore
    """複数論文のバッチ要約テスト。"""
    paper_ids = ["paper-1", "paper-2", "paper-3", "paper-4", "paper-5"]

    with patch.object(summarize_paper_task, 'delay') as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "task-id"
        mock_delay.return_value = mock_task

        result = batch_summarize_task(paper_ids)

        assert len(result) == 5
        for paper_id in paper_ids:
            assert result[paper_id] == "task-id"
        assert mock_delay.call_count == 5


def test_batch_summarize_task_empty_list():  # type: ignore
    """空のリストでのバッチ要約テスト."""
    paper_ids: list[str] = []

    with patch.object(summarize_paper_task, 'delay') as mock_delay:
        result = batch_summarize_task(paper_ids)

        assert len(result) == 0
        assert mock_delay.call_count == 0


def test_summarize_paper_task_with_settings():  # type: ignore
    """設定を含むタスクテスト."""
    from refnet_summarizer.tasks import settings

    # 設定が正しく読み込まれていることを確認
    assert settings is not None

    with patch('refnet_summarizer.tasks.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.return_value = True
        mock_service.close.return_value = None

        result = summarize_paper_task("test-paper-123")

        assert result is True
        mock_service.summarize_paper.assert_called_once_with("test-paper-123")
        mock_service.close.assert_called_once()
