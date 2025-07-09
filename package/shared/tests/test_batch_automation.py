"""バッチ自動化テスト."""

import pytest
from celery.result import EagerResult

from refnet_shared.celery_app import celery_app
from refnet_shared.tasks.scheduled_tasks import (
    CallbackTask,
    backup_database,
    cleanup_old_logs,
    collect_new_papers,
    database_maintenance,
    generate_markdown_files,
    generate_stats_report,
    process_pending_summaries,
    system_health_check,
)


class TestBatchAutomation:
    """バッチ自動化テスト."""

    def test_collect_new_papers_task(self):
        """新規論文収集タスクテスト."""
        # Celeryをeagerモードに設定
        celery_app.conf.task_always_eager = True

        result = collect_new_papers.delay(max_papers=10)
        assert isinstance(result, EagerResult)
        assert result.successful()

        response = result.get()
        assert response["status"] in ["success", "error"]
        if response["status"] == "success":
            assert "papers_scheduled" in response

    def test_system_health_check_task(self):
        """システムヘルスチェックタスクテスト."""
        celery_app.conf.task_always_eager = True

        result = system_health_check.delay()
        assert result.successful()

        response = result.get()
        assert "services" in response
        assert "metrics" in response
        assert "overall_status" in response

    def test_database_maintenance_task(self):
        """データベースメンテナンスタスクテスト."""
        celery_app.conf.task_always_eager = True

        result = database_maintenance.delay()
        assert result.successful()

        response = result.get()
        assert response["status"] in ["success", "error"]
        if response["status"] == "success":
            assert "maintenance_tasks" in response

    @pytest.mark.slow
    def test_beat_schedule_configuration(self):
        """Beat スケジュール設定テスト."""
        schedule = celery_app.conf.beat_schedule

        # 必要なスケジュールタスクが設定されているかチェック
        required_tasks = [
            "daily-paper-collection",
            "daily-summarization",
            "daily-markdown-generation",
            "weekly-db-maintenance",
            "system-health-check",
        ]

        for task_name in required_tasks:
            assert task_name in schedule, f"Missing scheduled task: {task_name}"
            assert "task" in schedule[task_name]
            assert "schedule" in schedule[task_name]

    def test_cleanup_old_logs_task(self):
        """ログクリーンアップタスクテスト."""
        celery_app.conf.task_always_eager = True

        result = cleanup_old_logs.delay(days_to_keep=7)
        assert result.successful()

        response = result.get()
        assert response["status"] in ["success", "error"]
        if response["status"] == "success":
            assert "files_cleaned" in response

    def test_process_pending_summaries_task(self):
        """要約処理タスクテスト."""
        celery_app.conf.task_always_eager = True

        result = process_pending_summaries.delay(batch_size=10)
        assert result.successful()

        response = result.get()
        assert response["status"] in ["success", "error"]
        if response["status"] == "success":
            assert "summaries_scheduled" in response

    def test_generate_markdown_files_task(self):
        """Markdown生成タスクテスト."""
        celery_app.conf.task_always_eager = True

        result = generate_markdown_files.delay(batch_size=10)
        assert result.successful()

        response = result.get()
        assert response["status"] in ["success", "error"]
        if response["status"] == "success":
            assert "markdown_files_scheduled" in response

    def test_generate_stats_report_task(self):
        """統計レポート生成タスクテスト."""
        celery_app.conf.task_always_eager = True

        result = generate_stats_report.delay()
        assert result.successful()

        response = result.get()
        assert response["status"] in ["success", "error"]
        if response["status"] == "success":
            assert "stats" in response
            assert "report_file" in response

    def test_backup_database_task_non_production(self):
        """データベースバックアップタスクテスト（非本番環境）."""
        celery_app.conf.task_always_eager = True

        result = backup_database.delay()
        assert result.successful()

        response = result.get()
        # 非本番環境ではスキップされるはず
        assert response["status"] in ["skipped", "success", "error"]

    def test_callback_task_success(self):
        """CallbackTaskの成功時コールバックテスト."""
        task = CallbackTask()

        # 例外が発生しないことを確認
        try:
            task.on_success(retval={"status": "success"}, task_id="test-id", args=(), kwargs={})
        except Exception as e:
            pytest.fail(f"on_success callback failed: {e}")

    def test_callback_task_failure(self):
        """CallbackTaskの失敗時コールバックテスト."""
        task = CallbackTask()

        # 例外が発生しないことを確認
        try:
            task.on_failure(exc=Exception("Test error"), task_id="test-id", args=(), kwargs={}, einfo=None)
        except Exception as e:
            pytest.fail(f"on_failure callback failed: {e}")

    def test_celery_configuration(self):
        """Celery設定のテスト."""
        config = celery_app.conf

        # 基本設定
        assert config.task_serializer == "json"
        assert config.accept_content == ["json"]
        assert config.result_serializer == "json"
        assert config.timezone == "Asia/Tokyo"
        assert config.enable_utc is True
        assert config.task_track_started is True

        # タイムアウト設定
        assert config.task_time_limit == 3600
        assert config.task_soft_time_limit == 3300

        # ワーカー設定
        assert config.worker_prefetch_multiplier == 1
        assert config.worker_max_tasks_per_child == 1000
