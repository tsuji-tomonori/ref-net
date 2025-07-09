"""監視タスクテスト."""

from unittest.mock import patch

import pytest

from refnet_shared.tasks.monitoring_tasks import MonitoringTask, critical_system_check


class TestMonitoringTasks:
    """監視タスクテスト."""

    def test_monitoring_task_on_success(self):
        """MonitoringTaskの成功時コールバックテスト."""
        task = MonitoringTask()
        task.name = "test_task"

        # メトリクス収集をモック
        with patch('refnet_shared.tasks.monitoring_tasks.MetricsCollector') as mock_metrics:
            task.on_success(
                retval={"status": "success"},
                task_id="test-task-id",
                args=(),
                kwargs={}
            )

            mock_metrics.track_task.assert_called_once_with("test_task", "SUCCESS")

    def test_monitoring_task_on_failure(self):
        """MonitoringTaskの失敗時コールバックテスト."""
        task = MonitoringTask()
        task.name = "test_task"

        # メトリクス収集をモック
        with patch('refnet_shared.tasks.monitoring_tasks.MetricsCollector') as mock_metrics:
            task.on_failure(
                exc=Exception("Test error"),
                task_id="test-task-id",
                args=(),
                kwargs={},
                einfo=None
            )

            mock_metrics.track_task.assert_called_once_with("test_task", "FAILURE")

    def test_monitoring_task_on_failure_critical_task(self):
        """重要タスクの失敗時アラートテスト."""
        task = MonitoringTask()
        task.name = "refnet.scheduled.database_maintenance"

        # _send_alertメソッドをモック
        with patch.object(task, '_send_alert') as mock_alert:
            with patch('refnet_shared.tasks.monitoring_tasks.MetricsCollector'):
                task.on_failure(
                    exc=Exception("Test error"),
                    task_id="test-task-id",
                    args=(),
                    kwargs={},
                    einfo=None
                )

                mock_alert.assert_called_once()

    def test_monitoring_task_send_alert(self):
        """アラート送信メソッドのテスト."""
        task = MonitoringTask()

        # ログ出力をキャプチャ
        try:
            task._send_alert("Test Subject", "Test Message")
        except Exception as e:
            pytest.fail(f"_send_alert failed: {e}")

    def test_critical_system_check_import(self):
        """重要システムチェックのインポートテスト."""
        try:
            from refnet_shared.tasks.monitoring_tasks import critical_system_check
            assert critical_system_check is not None
        except ImportError as e:
            pytest.fail(f"Failed to import critical_system_check: {e}")

    def test_critical_system_check_task_execution(self):
        """重要システムチェックタスクの実行テスト."""
        from refnet_shared.celery_app import celery_app

        # Celeryをeagerモードに設定
        celery_app.conf.task_always_eager = True

        # タスクを実行
        result = critical_system_check.delay()

        # タスクが正常に実行されることを確認
        assert result.successful()
        response = result.get()
        assert "status" in response
        assert "timestamp" in response

    def test_monitoring_task_base_class(self):
        """MonitoringTaskベースクラスのテスト."""
        # インスタンス作成
        task = MonitoringTask()

        # メソッドが存在することを確認
        assert hasattr(task, 'on_success')
        assert hasattr(task, 'on_failure')
        assert hasattr(task, '_send_alert')
        assert callable(task.on_success)
        assert callable(task.on_failure)
        assert callable(task._send_alert)

    def test_monitoring_task_attributes(self):
        """MonitoringTaskの属性テスト."""
        task = MonitoringTask()

        # 必要な属性が存在することを確認
        assert hasattr(task, 'name')

    def test_monitoring_imports(self):
        """監視タスクモジュールのインポートテスト."""
        try:
            from refnet_shared.tasks.monitoring_tasks import MetricsCollector, MonitoringTask, critical_system_check, logger

            # すべてのインポートが成功することを確認
            assert MonitoringTask is not None
            assert critical_system_check is not None
            assert logger is not None
            assert MetricsCollector is not None

        except ImportError as e:
            pytest.fail(f"Failed to import monitoring tasks components: {e}")

    def test_monitoring_task_celery_decorator(self):
        """監視タスクのCeleryデコレーターテスト."""
        # critical_system_checkがCeleryタスクとして登録されているかチェック
        assert hasattr(critical_system_check, 'delay')
        assert callable(critical_system_check.delay)

    def test_monitoring_task_name_attribute(self):
        """監視タスクの名前属性テスト."""
        # タスクの名前が正しく設定されているかチェック
        assert hasattr(critical_system_check, 'name')
        assert critical_system_check.name == "refnet.scheduled.critical_system_check"
