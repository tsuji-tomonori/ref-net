"""セキュリティ監査ログ機能."""

from datetime import datetime
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel

logger = structlog.get_logger("security_audit")


class SecurityEventType(str, Enum):
    """セキュリティイベントタイプ."""

    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_SUCCESS = "authorization_success"
    AUTHORIZATION_FAILED = "authorization_failed"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_ACCESS = "data_access"
    ADMIN_ACTION = "admin_action"
    FLOWER_ACCESS = "flower_access"
    API_ACCESS = "api_access"


class SecurityAuditEvent(BaseModel):
    """セキュリティ監査イベント."""

    event_type: SecurityEventType
    timestamp: datetime
    user_id: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    endpoint: str | None = None
    method: str | None = None
    resource: str | None = None
    action: str | None = None
    result: str  # success, failed, blocked
    risk_level: str  # low, medium, high, critical
    details: dict[str, Any] | None = None

    class Config:
        """Pydantic設定."""
        use_enum_values = True


class SecurityAuditLogger:
    """セキュリティ監査ログクラス."""

    def __init__(self) -> None:
        """初期化."""
        self.logger = structlog.get_logger("security_audit")

    def log_event(self, event: SecurityAuditEvent) -> None:
        """セキュリティイベントをログに記録."""
        event_data = {
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "user_id": event.user_id,
            "session_id": event.session_id,
            "ip_address": event.ip_address,
            "user_agent": event.user_agent,
            "endpoint": event.endpoint,
            "method": event.method,
            "resource": event.resource,
            "action": event.action,
            "result": event.result,
            "risk_level": event.risk_level,
            "details": event.details or {}
        }

        # リスクレベルに応じたログレベル
        if event.risk_level == "critical":
            self.logger.critical("Security audit event", **event_data)
        elif event.risk_level == "high":
            self.logger.error("Security audit event", **event_data)
        elif event.risk_level == "medium":
            self.logger.warning("Security audit event", **event_data)
        else:
            self.logger.info("Security audit event", **event_data)

    def log_authentication_success(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str | None = None,
        session_id: str | None = None
    ) -> None:
        """認証成功をログに記録."""
        event = SecurityAuditEvent(
            event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
            timestamp=datetime.now(),
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            result="success",
            risk_level="low"
        )
        self.log_event(event)

    def log_authentication_failed(
        self,
        user_id: str | None,
        ip_address: str,
        user_agent: str | None = None,
        reason: str | None = None
    ) -> None:
        """認証失敗をログに記録."""
        event = SecurityAuditEvent(
            event_type=SecurityEventType.AUTHENTICATION_FAILED,
            timestamp=datetime.now(),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            result="failed",
            risk_level="medium",
            details={"reason": reason} if reason else None
        )
        self.log_event(event)

    def log_authorization_failed(
        self,
        user_id: str | None,
        ip_address: str,
        endpoint: str,
        action: str,
        resource: str | None = None,
        reason: str | None = None
    ) -> None:
        """認可失敗をログに記録."""
        event = SecurityAuditEvent(
            event_type=SecurityEventType.AUTHORIZATION_FAILED,
            timestamp=datetime.now(),
            user_id=user_id,
            ip_address=ip_address,
            endpoint=endpoint,
            action=action,
            resource=resource,
            result="failed",
            risk_level="high",
            details={"reason": reason} if reason else None
        )
        self.log_event(event)

    def log_rate_limit_exceeded(
        self,
        user_id: str | None,
        ip_address: str,
        endpoint: str,
        limit_type: str,
        current_requests: int,
        limit: int
    ) -> None:
        """レート制限超過をログに記録."""
        event = SecurityAuditEvent(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            timestamp=datetime.now(),
            user_id=user_id,
            ip_address=ip_address,
            endpoint=endpoint,
            result="blocked",
            risk_level="medium",
            details={
                "limit_type": limit_type,
                "current_requests": current_requests,
                "limit": limit
            }
        )
        self.log_event(event)

    def log_suspicious_activity(
        self,
        user_id: str | None,
        ip_address: str,
        activity_type: str,
        details: dict[str, Any] | None = None
    ) -> None:
        """疑わしい活動をログに記録."""
        event = SecurityAuditEvent(
            event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
            timestamp=datetime.now(),
            user_id=user_id,
            ip_address=ip_address,
            result="detected",
            risk_level="high",
            details={"activity_type": activity_type, **(details or {})}
        )
        self.log_event(event)

    def log_admin_action(
        self,
        user_id: str,
        ip_address: str,
        action: str,
        resource: str | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """管理者アクションをログに記録."""
        event = SecurityAuditEvent(
            event_type=SecurityEventType.ADMIN_ACTION,
            timestamp=datetime.now(),
            user_id=user_id,
            ip_address=ip_address,
            action=action,
            resource=resource,
            result="success",
            risk_level="medium",
            details=details
        )
        self.log_event(event)

    def log_flower_access(
        self,
        user_id: str | None,
        ip_address: str,
        path: str,
        success: bool = True,
        details: dict[str, Any] | None = None
    ) -> None:
        """Flower UIアクセスをログに記録."""
        event = SecurityAuditEvent(
            event_type=SecurityEventType.FLOWER_ACCESS,
            timestamp=datetime.now(),
            user_id=user_id,
            ip_address=ip_address,
            endpoint=path,
            result="success" if success else "failed",
            risk_level="medium",
            details=details
        )
        self.log_event(event)

    def log_api_access(
        self,
        user_id: str | None,
        ip_address: str,
        method: str,
        endpoint: str,
        status_code: int,
        response_time: float | None = None,
        details: dict[str, Any] | None = None
    ) -> None:
        """API アクセスをログに記録."""
        risk_level = "low"
        if status_code >= 400:
            risk_level = "medium"
        if status_code >= 500:
            risk_level = "high"

        event = SecurityAuditEvent(
            event_type=SecurityEventType.API_ACCESS,
            timestamp=datetime.now(),
            user_id=user_id,
            ip_address=ip_address,
            method=method,
            endpoint=endpoint,
            result="success" if status_code < 400 else "failed",
            risk_level=risk_level,
            details={
                "status_code": status_code,
                "response_time": response_time,
                **(details or {})
            }
        )
        self.log_event(event)


# グローバルインスタンス
security_audit_logger = SecurityAuditLogger()
