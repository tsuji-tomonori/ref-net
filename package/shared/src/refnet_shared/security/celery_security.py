"""Celery タスクセキュリティ機能."""

from collections.abc import Callable
from functools import wraps
from typing import Any

import structlog
from celery import current_task
from celery.exceptions import Reject

from refnet_shared.security.audit_logger import security_audit_logger

logger = structlog.get_logger(__name__)


class CeleryTaskPermission:
    """Celeryタスク権限管理."""

    # 管理者権限が必要なタスク
    ADMIN_REQUIRED_TASKS: set[str] = {
        "refnet.scheduled.database_maintenance",
        "refnet.scheduled.backup_database",
        "refnet.scheduled.system_health_check",
        "refnet.scheduled.cleanup_old_logs",
        "refnet.admin.reset_system",
        "refnet.admin.purge_cache",
        "refnet.admin.emergency_stop",
    }

    # 高リスク操作タスク
    HIGH_RISK_TASKS: set[str] = {
        "refnet.scheduled.database_maintenance",
        "refnet.scheduled.backup_database",
        "refnet.admin.reset_system",
        "refnet.admin.purge_cache",
        "refnet.admin.emergency_stop",
    }

    # 通常ユーザーが実行可能なタスク
    USER_ALLOWED_TASKS: set[str] = {
        "refnet.scheduled.collect_new_papers",
        "refnet.scheduled.process_pending_summaries",
        "refnet.scheduled.generate_markdown_files",
        "refnet.scheduled.generate_stats_report",
        "refnet.crawler.crawl_paper",
        "refnet.summarizer.summarize_paper",
        "refnet.generator.generate_markdown",
    }

    # システムタスク（自動実行のみ）
    SYSTEM_ONLY_TASKS: set[str] = {
        "refnet.scheduled.system_health_check",
        "refnet.scheduled.cleanup_old_logs",
        "refnet.internal.process_queue",
        "refnet.internal.monitor_system",
    }

    @classmethod
    def is_admin_required(cls, task_name: str) -> bool:
        """管理者権限が必要かチェック."""
        return task_name in cls.ADMIN_REQUIRED_TASKS

    @classmethod
    def is_high_risk(cls, task_name: str) -> bool:
        """高リスクタスクかチェック."""
        return task_name in cls.HIGH_RISK_TASKS

    @classmethod
    def is_user_allowed(cls, task_name: str) -> bool:
        """ユーザー実行可能タスクかチェック."""
        return task_name in cls.USER_ALLOWED_TASKS

    @classmethod
    def is_system_only(cls, task_name: str) -> bool:
        """システム専用タスクかチェック."""
        return task_name in cls.SYSTEM_ONLY_TASKS


def require_admin_permission(task_func: Callable) -> Callable:
    """管理者権限が必要なタスクのデコレーター."""

    @wraps(task_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not current_task:
            logger.error("Task context not available for permission check")
            raise Reject("Task context not available")

        task_name = current_task.name

        # 管理者権限チェック（実際の実装では認証システムと連携）
        user_id = kwargs.get("user_id")
        is_admin = _check_admin_permission(user_id)

        if not is_admin:
            logger.error("Admin permission required for task", task_name=task_name, user_id=user_id)

            # セキュリティ監査ログに記録
            security_audit_logger.log_authorization_failed(
                user_id=user_id,
                ip_address=kwargs.get("ip_address", "unknown"),
                endpoint=f"celery_task:{task_name}",
                action="execute",
                resource=task_name,
                reason="admin_permission_required"
            )

            raise Reject("Admin permission required")

        # 管理者アクションをログに記録
        if user_id:
            security_audit_logger.log_admin_action(
                user_id=user_id,
                ip_address=kwargs.get("ip_address", "unknown"),
                action="execute_task",
                resource=task_name,
                details={"task_args": args, "task_kwargs": kwargs}
            )

        return task_func(*args, **kwargs)

    return wrapper


def require_user_permission(task_func: Callable) -> Callable:
    """ユーザー権限が必要なタスクのデコレーター."""

    @wraps(task_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not current_task:
            logger.error("Task context not available for permission check")
            raise Reject("Task context not available")

        task_name = current_task.name

        # ユーザー権限チェック
        user_id = kwargs.get("user_id")
        is_authenticated = _check_user_permission(user_id)

        if not is_authenticated:
            logger.error("User permission required for task", task_name=task_name, user_id=user_id)

            # セキュリティ監査ログに記録
            security_audit_logger.log_authorization_failed(
                user_id=user_id,
                ip_address=kwargs.get("ip_address", "unknown"),
                endpoint=f"celery_task:{task_name}",
                action="execute",
                resource=task_name,
                reason="user_permission_required"
            )

            raise Reject("User permission required")

        return task_func(*args, **kwargs)

    return wrapper


def system_task_only(task_func: Callable) -> Callable:
    """システム専用タスクのデコレーター."""

    @wraps(task_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not current_task:
            logger.error("Task context not available for permission check")
            raise Reject("Task context not available")

        task_name = current_task.name

        # システム実行チェック（スケジュール実行のみ許可）
        is_scheduled = _is_scheduled_execution()

        if not is_scheduled:
            logger.error("System task executed manually", task_name=task_name)

            # セキュリティ監査ログに記録
            security_audit_logger.log_suspicious_activity(
                user_id=kwargs.get("user_id"),
                ip_address=kwargs.get("ip_address", "unknown"),
                activity_type="manual_system_task_execution",
                details={"task_name": task_name}
            )

            raise Reject("System task cannot be executed manually")

        return task_func(*args, **kwargs)

    return wrapper


def log_task_execution(task_func: Callable) -> Callable:
    """タスク実行をログに記録するデコレーター."""

    @wraps(task_func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not current_task:
            return task_func(*args, **kwargs)

        task_name = current_task.name
        task_id = current_task.request.id

        logger.info("Task execution started", task_name=task_name, task_id=task_id)

        try:
            result = task_func(*args, **kwargs)
            logger.info("Task execution completed", task_name=task_name, task_id=task_id)
            return result
        except Exception as e:
            logger.error("Task execution failed", task_name=task_name, task_id=task_id, error=str(e))
            raise

    return wrapper


def _check_admin_permission(user_id: str | None) -> bool:
    """管理者権限チェック（実装要）."""
    # 実際の実装では認証システムと連携
    # 現在は環境変数やデータベースから管理者リストを取得
    if not user_id:
        return False

    # 暫定的な実装：環境変数から管理者リストを取得
    admin_users = ["admin", "system", "root"]
    return user_id in admin_users


def _check_user_permission(user_id: str | None) -> bool:
    """ユーザー権限チェック（実装要）."""
    # 実際の実装では認証システムと連携
    # 現在は基本的な認証チェックのみ
    return user_id is not None and len(user_id) > 0


def _is_scheduled_execution() -> bool:
    """スケジュール実行かチェック."""
    if not current_task:
        return False

    # Celery Beatからの実行かチェック
    # 実際の実装では、リクエストヘッダーや実行コンテキストを確認
    request = current_task.request

    # Celery Beatからの実行の場合、特定のヘッダーや属性が設定される
    # 暫定的な実装：eta やcountdownが設定されていればスケジュール実行と判定
    return hasattr(request, 'eta') or hasattr(request, 'countdown')


class CelerySecurityMiddleware:
    """Celeryセキュリティミドルウェア."""

    def __init__(self) -> None:
        """初期化."""
        self.permission_checker = CeleryTaskPermission()

    def check_task_permission(self, task_name: str, user_id: str | None = None) -> bool:
        """タスク実行権限チェック."""
        # 管理者権限が必要なタスク
        if self.permission_checker.is_admin_required(task_name):
            return _check_admin_permission(user_id)

        # システム専用タスク
        if self.permission_checker.is_system_only(task_name):
            return _is_scheduled_execution()

        # ユーザー実行可能タスク
        if self.permission_checker.is_user_allowed(task_name):
            return _check_user_permission(user_id)

        # 未定義タスクは拒否
        return False

    def get_task_security_info(self, task_name: str) -> dict[str, Any]:
        """タスクセキュリティ情報を取得."""
        return {
            "admin_required": self.permission_checker.is_admin_required(task_name),
            "high_risk": self.permission_checker.is_high_risk(task_name),
            "user_allowed": self.permission_checker.is_user_allowed(task_name),
            "system_only": self.permission_checker.is_system_only(task_name),
        }


# グローバルインスタンス
celery_security = CelerySecurityMiddleware()
