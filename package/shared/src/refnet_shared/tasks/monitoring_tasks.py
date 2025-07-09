"""監視・アラート統合タスク."""

from datetime import datetime
from typing import Any

import structlog
from celery import Task

from refnet_shared.celery_app import celery_app
from refnet_shared.utils.metrics import MetricsCollector

logger = structlog.get_logger(__name__)


class MonitoringTask(Task):
    """監視機能付きタスク基底クラス."""

    def on_success(self, retval, task_id, args, kwargs):
        """タスク成功時の監視メトリクス更新."""
        MetricsCollector.track_task(self.name, "SUCCESS")
        logger.info("Task completed", task_name=self.name, task_id=task_id)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """タスク失敗時の監視メトリクス更新."""
        MetricsCollector.track_task(self.name, "FAILURE")
        logger.error("Task failed", task_name=self.name, task_id=task_id, error=str(exc))

        # 重要なタスクの失敗時はアラート送信
        critical_tasks = ["refnet.scheduled.database_maintenance", "refnet.scheduled.backup_database"]

        if self.name in critical_tasks:
            # アラート送信ロジック
            self._send_alert(f"Critical task failed: {self.name}", str(exc))

    def _send_alert(self, subject: str, message: str) -> None:
        """アラート送信."""
        # 実際の実装では、メール・Slack・Webhookなどにアラート送信
        logger.critical("ALERT", subject=subject, message=message)


# 既存のタスクを監視機能付きに変更
@celery_app.task(base=MonitoringTask, name="refnet.scheduled.critical_system_check")
def critical_system_check() -> dict[str, Any]:
    """重要なシステムチェック."""
    logger.info("Starting critical system check")

    try:
        from refnet_shared.models.database_manager import db_manager

        # データベース接続、Redis接続、ディスク容量など
        # 重要なシステム要素をチェック
        checks = {"database": False, "redis": False, "disk_space": False}

        # データベース接続チェック
        try:
            with db_manager.get_session() as session:
                from sqlalchemy import text
                session.execute(text("SELECT 1"))
                checks["database"] = True
        except Exception as e:
            logger.error("Database connection failed", error=str(e))

        # Redis接続チェック
        try:
            from refnet_shared.middleware.rate_limiter import rate_limiter

            rate_limiter.redis_client.ping()
            checks["redis"] = True
        except Exception as e:
            logger.error("Redis connection failed", error=str(e))

        # ディスク容量チェック
        import shutil

        try:
            disk_usage = shutil.disk_usage("/")
            free_percentage = (disk_usage.free / disk_usage.total) * 100
            if free_percentage > 10:  # 10%以上の空きがあればOK
                checks["disk_space"] = True
            else:
                logger.warning("Low disk space", free_percentage=free_percentage)
        except Exception as e:
            logger.error("Disk space check failed", error=str(e))

        all_healthy = all(checks.values())

        return {"status": "success" if all_healthy else "warning", "checks": checks, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("Critical system check failed", error=str(e))
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}
