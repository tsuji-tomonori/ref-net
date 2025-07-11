"""セキュリティ監査ログのテスト."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import structlog

from refnet_shared.security.audit_logger import (
    SecurityAuditEvent,
    SecurityAuditLogger,
    SecurityEventType,
    security_audit_logger,
)


class TestSecurityAuditLogger:
    """SecurityAuditLoggerのテスト."""

    def test_log_event_critical(self) -> None:
        """criticalレベルのイベントログ記録テスト."""
        logger = SecurityAuditLogger()
        with patch.object(logger.logger, "critical") as mock_critical:
            event = SecurityAuditEvent(
                event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
                timestamp=datetime.now(),
                user_id="test_user",
                ip_address="192.168.1.1",
                result="detected",
                risk_level="critical",
            )
            logger.log_event(event)
            mock_critical.assert_called_once()

    def test_log_event_high(self) -> None:
        """highレベルのイベントログ記録テスト."""
        logger = SecurityAuditLogger()
        with patch.object(logger.logger, "error") as mock_error:
            event = SecurityAuditEvent(
                event_type=SecurityEventType.AUTHORIZATION_FAILED,
                timestamp=datetime.now(),
                user_id="test_user",
                ip_address="192.168.1.1",
                result="failed",
                risk_level="high",
            )
            logger.log_event(event)
            mock_error.assert_called_once()

    def test_log_event_medium(self) -> None:
        """mediumレベルのイベントログ記録テスト."""
        logger = SecurityAuditLogger()
        with patch.object(logger.logger, "warning") as mock_warning:
            event = SecurityAuditEvent(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                timestamp=datetime.now(),
                user_id="test_user",
                ip_address="192.168.1.1",
                result="blocked",
                risk_level="medium",
            )
            logger.log_event(event)
            mock_warning.assert_called_once()

    def test_log_event_low(self) -> None:
        """lowレベルのイベントログ記録テスト."""
        logger = SecurityAuditLogger()
        with patch.object(logger.logger, "info") as mock_info:
            event = SecurityAuditEvent(
                event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
                timestamp=datetime.now(),
                user_id="test_user",
                ip_address="192.168.1.1",
                result="success",
                risk_level="low",
            )
            logger.log_event(event)
            mock_info.assert_called_once()

    def test_log_authentication_success(self) -> None:
        """認証成功ログ記録テスト."""
        with patch.object(security_audit_logger, "log_event") as mock_log:
            security_audit_logger.log_authentication_success(
                user_id="test_user",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                session_id="test_session",
            )
            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == SecurityEventType.AUTHENTICATION_SUCCESS
            assert event.risk_level == "low"

    def test_log_authentication_failed(self) -> None:
        """認証失敗ログ記録テスト."""
        with patch.object(security_audit_logger, "log_event") as mock_log:
            security_audit_logger.log_authentication_failed(
                user_id="test_user",
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                reason="invalid_password",
            )
            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == SecurityEventType.AUTHENTICATION_FAILED
            assert event.risk_level == "medium"
            assert event.details == {"reason": "invalid_password"}

    def test_log_authorization_failed(self) -> None:
        """認可失敗ログ記録テスト."""
        with patch.object(security_audit_logger, "log_event") as mock_log:
            security_audit_logger.log_authorization_failed(
                user_id="test_user",
                ip_address="192.168.1.1",
                endpoint="/api/admin",
                action="delete",
                resource="users",
                reason="insufficient_permissions",
            )
            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == SecurityEventType.AUTHORIZATION_FAILED
            assert event.risk_level == "high"

    def test_log_rate_limit_exceeded(self) -> None:
        """レート制限超過ログ記録テスト."""
        with patch.object(security_audit_logger, "log_event") as mock_log:
            security_audit_logger.log_rate_limit_exceeded(
                user_id="test_user",
                ip_address="192.168.1.1",
                endpoint="/api/papers",
                limit_type="burst",
                current_requests=101,
                limit=100,
            )
            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == SecurityEventType.RATE_LIMIT_EXCEEDED
            assert event.risk_level == "medium"

    def test_log_suspicious_activity(self) -> None:
        """疑わしい活動ログ記録テスト."""
        with patch.object(security_audit_logger, "log_event") as mock_log:
            security_audit_logger.log_suspicious_activity(
                user_id="test_user",
                ip_address="192.168.1.1",
                activity_type="sql_injection_attempt",
                details={"query": "SELECT * FROM users WHERE 1=1"},
            )
            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == SecurityEventType.SUSPICIOUS_ACTIVITY
            assert event.risk_level == "high"

    def test_log_admin_action(self) -> None:
        """管理者アクションログ記録テスト."""
        with patch.object(security_audit_logger, "log_event") as mock_log:
            security_audit_logger.log_admin_action(
                user_id="admin_user",
                ip_address="192.168.1.1",
                action="delete_user",
                resource="user:12345",
                details={"reason": "policy_violation"},
            )
            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == SecurityEventType.ADMIN_ACTION
            assert event.risk_level == "medium"

    def test_log_flower_access(self) -> None:
        """Flowerアクセスログ記録テスト."""
        with patch.object(security_audit_logger, "log_event") as mock_log:
            security_audit_logger.log_flower_access(
                user_id="test_user",
                ip_address="192.168.1.1",
                path="/flower/tasks",
                success=True,
                details={"method": "GET"},
            )
            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == SecurityEventType.FLOWER_ACCESS
            assert event.result == "success"

    def test_log_api_access(self) -> None:
        """APIアクセスログ記録テスト."""
        with patch.object(security_audit_logger, "log_event") as mock_log:
            security_audit_logger.log_api_access(
                user_id="test_user",
                ip_address="192.168.1.1",
                method="POST",
                endpoint="/api/papers",
                status_code=201,
                response_time=0.123,
                details={"paper_id": "12345"},
            )
            mock_log.assert_called_once()
            event = mock_log.call_args[0][0]
            assert event.event_type == SecurityEventType.API_ACCESS
            assert event.result == "success"
            assert event.risk_level == "low"

    def test_log_api_access_error_status(self) -> None:
        """APIアクセスエラーステータスログ記録テスト."""
        with patch.object(security_audit_logger, "log_event") as mock_log:
            # 4xx エラー
            security_audit_logger.log_api_access(
                user_id=None,
                ip_address="192.168.1.1",
                method="GET",
                endpoint="/api/papers/invalid",
                status_code=404,
            )
            event = mock_log.call_args[0][0]
            assert event.risk_level == "medium"

            # 5xx エラー
            security_audit_logger.log_api_access(
                user_id=None,
                ip_address="192.168.1.1",
                method="GET",
                endpoint="/api/papers",
                status_code=500,
            )
            event = mock_log.call_args[0][0]
            assert event.risk_level == "high"
