"""monitoring_tasksモジュールの包括的テスト."""

from unittest.mock import MagicMock, patch

from refnet_shared.tasks.monitoring_tasks import (
    MonitoringTask,
    auto_recovery_health_check,
    critical_system_check,
)


class TestMonitoringTask:
    """MonitoringTaskクラスのテスト."""

    def test_on_success(self) -> None:
        """on_success正常系テスト."""
        task = MonitoringTask()
        task.name = "test_task"

        with patch("refnet_shared.tasks.monitoring_tasks.MetricsCollector.track_task") as mock_track:
            task.on_success("result", "task-123", [], {})
            mock_track.assert_called_once_with("test_task", "SUCCESS")

    def test_on_failure_normal_task(self) -> None:
        """on_failure通常タスクテスト."""
        task = MonitoringTask()
        task.name = "test_task"

        with patch("refnet_shared.tasks.monitoring_tasks.MetricsCollector.track_task") as mock_track:
            exc = Exception("Test error")
            task.on_failure(exc, "task-123", [], {}, None)

            mock_track.assert_called_once_with("test_task", "FAILURE")

    def test_on_failure_critical_task(self) -> None:
        """on_failure重要タスクテスト."""
        task = MonitoringTask()
        task.name = "refnet.scheduled.database_maintenance"

        with patch("refnet_shared.tasks.monitoring_tasks.MetricsCollector.track_task") as mock_track, \
             patch.object(task, "_send_alert") as mock_alert, \
             patch.object(task, "_trigger_auto_recovery") as mock_recovery:

            exc = Exception("Database error")
            task.on_failure(exc, "task-123", [], {}, None)

            mock_track.assert_called_once_with("refnet.scheduled.database_maintenance", "FAILURE")
            mock_alert.assert_called_once()
            mock_recovery.assert_called_once()

    def test_send_alert(self) -> None:
        """_send_alertテスト."""
        task = MonitoringTask()

        with patch("refnet_shared.tasks.monitoring_tasks.logger.critical") as mock_log:
            task._send_alert("Test subject", "Test message")
            mock_log.assert_called_once()

    def test_trigger_auto_recovery_database(self) -> None:
        """_trigger_auto_recovery データベースエラーテスト."""
        task = MonitoringTask()

        with patch("refnet_shared.tasks.monitoring_tasks.asyncio.run") as mock_run, \
             patch("refnet_shared.tasks.monitoring_tasks.trigger_recovery"):

            exc = Exception("Database connection failed")
            task._trigger_auto_recovery(exc, "task-123")

            mock_run.assert_called_once()

    def test_trigger_auto_recovery_redis(self) -> None:
        """_trigger_auto_recovery Redisエラーテスト."""
        task = MonitoringTask()

        with patch("refnet_shared.tasks.monitoring_tasks.asyncio.run") as mock_run:
            exc = Exception("Redis connection timeout")
            task._trigger_auto_recovery(exc, "task-123")

            mock_run.assert_called_once()

    def test_trigger_auto_recovery_exception(self) -> None:
        """_trigger_auto_recovery 例外テスト."""
        task = MonitoringTask()

        with patch("refnet_shared.tasks.monitoring_tasks.asyncio.run") as mock_run, \
             patch("refnet_shared.tasks.monitoring_tasks.logger.error") as mock_log:

            mock_run.side_effect = Exception("Recovery failed")
            exc = Exception("Test error")
            task._trigger_auto_recovery(exc, "task-123")

            mock_log.assert_called_once()


class TestCriticalSystemCheck:
    """critical_system_checkのテスト."""

    @patch("refnet_shared.tasks.monitoring_tasks.check_system_health")
    @patch("refnet_shared.tasks.monitoring_tasks.get_auto_recovery_manager")
    def test_critical_system_check_healthy(self, mock_manager: MagicMock, mock_health: MagicMock) -> None:
        """critical_system_check正常系テスト."""
        mock_health.return_value = {
            "database": "healthy",
            "redis": "healthy",
            "disk_usage": 50,
            "memory_usage": 60,
            "cpu_usage": 30
        }

        mock_mgr = MagicMock()
        mock_mgr.get_recovery_statistics.return_value = {"total_recoveries": 0}
        mock_manager.return_value = mock_mgr

        result = critical_system_check()

        assert result["status"] == "healthy"
        assert result["critical_issues"] == []

    @patch("refnet_shared.tasks.monitoring_tasks.check_system_health")
    @patch("refnet_shared.tasks.monitoring_tasks.get_auto_recovery_manager")
    @patch("refnet_shared.tasks.monitoring_tasks.asyncio.run")
    def test_critical_system_check_unhealthy(self, mock_run: MagicMock, mock_manager: MagicMock, mock_health: MagicMock) -> None:
        """critical_system_check異常系テスト."""
        mock_health.return_value = {
            "database": "unhealthy",
            "redis": "healthy",
            "disk_usage": 95,
            "memory_usage": 97,
            "cpu_usage": 85
        }

        mock_mgr = MagicMock()
        mock_mgr.get_recovery_statistics.return_value = {"total_recoveries": 5}
        mock_manager.return_value = mock_mgr

        result = critical_system_check()

        assert result["status"] == "critical"
        assert "database" in result["critical_issues"]
        assert "disk_space" in result["critical_issues"]
        assert "memory" in result["critical_issues"]

    @patch("refnet_shared.tasks.monitoring_tasks.check_system_health")
    def test_critical_system_check_exception(self, mock_health: MagicMock) -> None:
        """critical_system_check例外テスト."""
        mock_health.side_effect = Exception("Health check failed")

        result = critical_system_check()

        assert result["status"] == "error"
        assert "Health check failed" in result["error"]


class TestAutoRecoveryHealthCheck:
    """auto_recovery_health_checkのテスト."""

    @patch("refnet_shared.tasks.monitoring_tasks.get_auto_recovery_manager")
    def test_auto_recovery_health_check_success(self, mock_manager: MagicMock) -> None:
        """auto_recovery_health_check成功テスト."""
        mock_mgr = MagicMock()
        mock_mgr.get_recovery_history.return_value = [
            MagicMock(status=MagicMock(value="success")),
            MagicMock(status=MagicMock(value="success"))
        ]
        mock_mgr.get_recovery_statistics.return_value = {"total_recoveries": 2}
        mock_mgr.cooldown_timers = {}
        mock_manager.return_value = mock_mgr

        result = auto_recovery_health_check()

        assert result["status"] == "success"
        assert result["recent_recovery_count"] == 2
        assert result["failed_recovery_count"] == 0

    @patch("refnet_shared.tasks.monitoring_tasks.get_auto_recovery_manager")
    def test_auto_recovery_health_check_high_failures(self, mock_manager: MagicMock) -> None:
        """auto_recovery_health_check高失敗率テスト."""
        failed_recoveries = [MagicMock(status=MagicMock(value="failed")) for _ in range(15)]

        mock_mgr = MagicMock()
        mock_mgr.get_recovery_history.return_value = failed_recoveries
        mock_mgr.get_recovery_statistics.return_value = {"total_recoveries": 15}
        mock_mgr.cooldown_timers = {"database": 1000000000}  # Future timestamp
        mock_manager.return_value = mock_mgr

        with patch("refnet_shared.tasks.monitoring_tasks.logger.warning") as mock_warn:
            result = auto_recovery_health_check()

            assert result["status"] == "success"
            assert result["failed_recovery_count"] == 15
            mock_warn.assert_called_once()

    @patch("refnet_shared.tasks.monitoring_tasks.get_auto_recovery_manager")
    def test_auto_recovery_health_check_exception(self, mock_manager: MagicMock) -> None:
        """auto_recovery_health_check例外テスト."""
        mock_manager.side_effect = Exception("Recovery manager failed")

        result = auto_recovery_health_check()

        assert result["status"] == "error"
        assert "Recovery manager failed" in result["error"]
