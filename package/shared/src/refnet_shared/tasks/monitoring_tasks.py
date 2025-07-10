"""監視・アラート統合タスク."""

import asyncio
from datetime import datetime
from typing import Any

import structlog
from celery import Task

from refnet_shared.celery_app import celery_app
from refnet_shared.utils.auto_recovery import check_system_health, get_auto_recovery_manager, trigger_recovery
from refnet_shared.utils.metrics import MetricsCollector

logger = structlog.get_logger(__name__)


class MonitoringTask(Task):
    """監視機能付きタスク基底クラス."""

    def on_success(self, retval: Any, task_id: str, args: Any, kwargs: Any) -> None:
        """タスク成功時の監視メトリクス更新."""
        MetricsCollector.track_task(self.name, "SUCCESS")
        logger.info("Task completed", task_name=self.name, task_id=task_id)

    def on_failure(self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        """タスク失敗時の監視メトリクス更新."""
        MetricsCollector.track_task(self.name, "FAILURE")
        logger.error("Task failed", task_name=self.name, task_id=task_id, error=str(exc))

        # 重要なタスクの失敗時はアラート送信
        critical_tasks = ["refnet.scheduled.database_maintenance", "refnet.scheduled.backup_database"]

        if self.name in critical_tasks:
            # アラート送信ロジック
            self._send_alert(f"Critical task failed: {self.name}", str(exc))

            # Auto-recovery triggers for specific failures
            self._trigger_auto_recovery(exc, task_id)

    def _send_alert(self, subject: str, message: str) -> None:
        """アラート送信."""
        # 実際の実装では、メール・Slack・Webhookなどにアラート送信
        logger.critical("ALERT", subject=subject, message=message)

    def _trigger_auto_recovery(self, exc: Exception, task_id: str) -> None:
        """Auto-recovery trigger based on failure type."""
        try:
            error_str = str(exc).lower()

            # Database connection failures
            if "database" in error_str or "connection" in error_str:
                asyncio.run(trigger_recovery("database_connection_failed", {"task_id": task_id, "error": str(exc)}))

            # Redis connection failures
            elif "redis" in error_str:
                asyncio.run(trigger_recovery("redis_connection_failed", {"task_id": task_id, "error": str(exc)}))

            # Disk space issues
            elif "disk" in error_str or "space" in error_str:
                asyncio.run(trigger_recovery("disk_space_low", {"task_id": task_id, "error": str(exc)}))

            # Memory issues
            elif "memory" in error_str or "oom" in error_str:
                asyncio.run(trigger_recovery("memory_exhausted", {"task_id": task_id, "error": str(exc)}))

        except Exception as recovery_error:
            logger.error("Auto-recovery trigger failed", task_id=task_id, error=str(recovery_error))


# 既存のタスクを監視機能付きに変更
@celery_app.task(base=MonitoringTask, name="refnet.scheduled.critical_system_check")  # type: ignore[misc]
def critical_system_check() -> dict[str, Any]:
    """重要なシステムチェック."""
    logger.info("Starting critical system check")

    try:
        # Use the new system health check
        health_status = check_system_health()

        # Determine overall health status
        critical_issues = []

        # Check database health
        if health_status.get("database") == "unhealthy":
            critical_issues.append("database")
            # Trigger database recovery
            asyncio.run(trigger_recovery("database_connection_failed", {"source": "critical_system_check"}))

        # Check Redis health
        if health_status.get("redis") == "unhealthy":
            critical_issues.append("redis")
            # Trigger Redis recovery
            asyncio.run(trigger_recovery("redis_connection_failed", {"source": "critical_system_check"}))

        # Check disk space (trigger if >90% used)
        disk_usage = health_status.get("disk_usage", 0)
        if isinstance(disk_usage, int | float) and disk_usage > 90:
            critical_issues.append("disk_space")
            # Trigger disk cleanup
            asyncio.run(trigger_recovery("disk_space_low", {"source": "critical_system_check", "disk_usage_percent": disk_usage}))

        # Check memory usage (trigger if >95% used)
        memory_usage = health_status.get("memory_usage", 0)
        if isinstance(memory_usage, int | float) and memory_usage > 95:
            critical_issues.append("memory")
            # Trigger cache clearing
            asyncio.run(trigger_recovery("redis_memory_high", {"source": "critical_system_check", "memory_usage_percent": memory_usage}))

        # Check CPU usage (log warning if >80% for extended period)
        cpu_usage = health_status.get("cpu_usage", 0)
        if isinstance(cpu_usage, int | float) and cpu_usage > 80:
            logger.warning("High CPU usage detected", cpu_usage=cpu_usage)

        # Determine overall status
        if critical_issues:
            status = "critical" if len(critical_issues) > 1 else "warning"
        else:
            status = "healthy"

        # Get auto-recovery statistics
        auto_recovery_manager = get_auto_recovery_manager()
        recovery_stats = auto_recovery_manager.get_recovery_statistics()

        return {
            "status": status,
            "health_status": health_status,
            "critical_issues": critical_issues,
            "recovery_stats": recovery_stats,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error("Critical system check failed", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


@celery_app.task(base=MonitoringTask, name="refnet.scheduled.auto_recovery_health_check")  # type: ignore[misc]
def auto_recovery_health_check() -> dict[str, Any]:
    """Auto-recovery system health check and maintenance."""
    logger.info("Starting auto-recovery health check")

    try:
        auto_recovery_manager = get_auto_recovery_manager()

        # Get recovery history and statistics
        recent_history = auto_recovery_manager.get_recovery_history(limit=50)
        stats = auto_recovery_manager.get_recovery_statistics()

        # Check for repeated failures
        failed_actions = [r for r in recent_history if r.status.value == "failed"]

        # Alert if too many failures
        if len(failed_actions) > 10:
            logger.warning("High auto-recovery failure rate", failed_count=len(failed_actions), total_count=len(recent_history))

        # Check cooldown timers
        active_cooldowns = {name: timer for name, timer in auto_recovery_manager.cooldown_timers.items() if timer > datetime.now().timestamp()}

        return {
            "status": "success",
            "recent_recovery_count": len(recent_history),
            "failed_recovery_count": len(failed_actions),
            "recovery_statistics": stats,
            "active_cooldowns": len(active_cooldowns),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error("Auto-recovery health check failed", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}
