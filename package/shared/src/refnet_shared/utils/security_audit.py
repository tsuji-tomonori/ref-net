"""
Security audit logging utility for RefNet system.

This module provides comprehensive security audit logging functionality
for tracking security events, authentication attempts, and suspicious activities.
"""

import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..config.environment import load_environment_settings


class SecurityEventType(Enum):
    """Security event types for audit logging."""

    # Authentication events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_INVALID_TOKEN = "auth_invalid_token"
    AUTH_EXPIRED_TOKEN = "auth_expired_token"
    AUTH_LOGOUT = "auth_logout"

    # Authorization events
    AUTHZ_SUCCESS = "authz_success"
    AUTHZ_FAILURE = "authz_failure"
    AUTHZ_PRIVILEGE_ESCALATION = "authz_privilege_escalation"

    # Data access events
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"

    # System events
    SYSTEM_LOGIN = "system_login"
    SYSTEM_LOGOUT = "system_logout"
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    SYSTEM_ADMIN_ACTION = "system_admin_action"

    # Suspicious activities
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    MULTIPLE_FAILED_ATTEMPTS = "multiple_failed_attempts"
    UNUSUAL_ACCESS_PATTERN = "unusual_access_pattern"

    # Security incidents
    SECURITY_INCIDENT = "security_incident"
    POTENTIAL_ATTACK = "potential_attack"
    MALICIOUS_REQUEST = "malicious_request"


class SecurityLevel(Enum):
    """Security event severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ALERT = "alert"


class SecurityAuditLogger:
    """Security audit logger for tracking security events."""

    def __init__(self, service_name: str = "refnet-security"):
        self.service_name = service_name
        self.logger = logging.getLogger(f"security.{service_name}")
        self.logger.setLevel(logging.INFO)

        # Create security-specific handler if it doesn't exist
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_security_event(
        self,
        event_type: SecurityEventType,
        level: SecurityLevel,
        message: str,
        user_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        resource: str | None = None,
        additional_data: dict[str, Any] | None = None,
    ) -> None:
        """Log a security event with structured data."""

        event_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type.value,
            "level": level.value,
            "service": self.service_name,
            "message": message,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "request_id": request_id,
            "resource": resource,
            "environment": load_environment_settings().environment.value,
            "additional_data": additional_data or {},
        }

        # Remove None values for cleaner logs
        event_data = {k: v for k, v in event_data.items() if v is not None}

        # Log based on security level
        if level == SecurityLevel.INFO:
            self.logger.info(json.dumps(event_data))
        elif level == SecurityLevel.WARNING:
            self.logger.warning(json.dumps(event_data))
        elif level == SecurityLevel.CRITICAL:
            self.logger.critical(json.dumps(event_data))
        elif level == SecurityLevel.ALERT:
            self.logger.error(json.dumps(event_data))

    def log_auth_success(self, user_id: str, ip_address: str, user_agent: str | None = None, request_id: str | None = None) -> None:
        """Log successful authentication."""
        self.log_security_event(
            SecurityEventType.AUTH_SUCCESS,
            SecurityLevel.INFO,
            f"User {user_id} authenticated successfully",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )

    def log_auth_failure(
        self, username: str, ip_address: str, reason: str, user_agent: str | None = None, request_id: str | None = None
    ) -> None:
        """Log authentication failure."""
        self.log_security_event(
            SecurityEventType.AUTH_FAILURE,
            SecurityLevel.WARNING,
            f"Authentication failed for user {username}: {reason}",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            additional_data={"username": username, "reason": reason},
        )

    def log_data_access(
        self, user_id: str, resource: str, action: str, ip_address: str, success: bool = True, request_id: str | None = None
    ) -> None:
        """Log data access events."""
        level = SecurityLevel.INFO if success else SecurityLevel.WARNING
        message = f"User {user_id} {action} {resource}"
        if not success:
            message += " (FAILED)"

        self.log_security_event(
            SecurityEventType.DATA_ACCESS,
            level,
            message,
            user_id=user_id,
            ip_address=ip_address,
            resource=resource,
            request_id=request_id,
            additional_data={"action": action, "success": success},
        )

    def log_suspicious_activity(
        self,
        activity_type: str,
        description: str,
        ip_address: str,
        user_id: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        severity: SecurityLevel = SecurityLevel.WARNING,
    ) -> None:
        """Log suspicious activity."""
        self.log_security_event(
            SecurityEventType.SUSPICIOUS_ACTIVITY,
            severity,
            f"Suspicious activity detected: {description}",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            additional_data={"activity_type": activity_type},
        )

    def log_rate_limit_exceeded(self, ip_address: str, endpoint: str, user_id: str | None = None, request_id: str | None = None) -> None:
        """Log rate limit exceeded events."""
        self.log_security_event(
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            SecurityLevel.WARNING,
            f"Rate limit exceeded for endpoint {endpoint}",
            user_id=user_id,
            ip_address=ip_address,
            resource=endpoint,
            request_id=request_id,
        )

    def log_admin_action(self, user_id: str, action: str, target: str, ip_address: str, request_id: str | None = None) -> None:
        """Log administrative actions."""
        self.log_security_event(
            SecurityEventType.SYSTEM_ADMIN_ACTION,
            SecurityLevel.INFO,
            f"Admin action: {action} on {target}",
            user_id=user_id,
            ip_address=ip_address,
            resource=target,
            request_id=request_id,
            additional_data={"action": action},
        )

    def log_security_incident(
        self,
        incident_type: str,
        description: str,
        ip_address: str,
        user_id: str | None = None,
        severity: SecurityLevel = SecurityLevel.CRITICAL,
        request_id: str | None = None,
    ) -> None:
        """Log security incidents."""
        self.log_security_event(
            SecurityEventType.SECURITY_INCIDENT,
            severity,
            f"Security incident - {incident_type}: {description}",
            user_id=user_id,
            ip_address=ip_address,
            request_id=request_id,
            additional_data={"incident_type": incident_type},
        )


class SecurityMetrics:
    """Security metrics collection for monitoring."""

    def __init__(self) -> None:
        self.failed_auth_attempts: dict[str, list[float]] = {}
        self.suspicious_ips: set[str] = set()
        self.rate_limit_violations: dict[str, list[float]] = {}

    def track_failed_auth(self, ip_address: str, username: str) -> int:
        """Track failed authentication attempts."""
        key = f"{ip_address}:{username}"
        if key not in self.failed_auth_attempts:
            self.failed_auth_attempts[key] = []

        current_time = time.time()
        # Keep only attempts from the last hour
        self.failed_auth_attempts[key] = [t for t in self.failed_auth_attempts[key] if current_time - t < 3600]

        self.failed_auth_attempts[key].append(current_time)
        return len(self.failed_auth_attempts[key])

    def is_suspicious_ip(self, ip_address: str) -> bool:
        """Check if IP is marked as suspicious."""
        return ip_address in self.suspicious_ips

    def mark_suspicious_ip(self, ip_address: str) -> None:
        """Mark IP as suspicious."""
        self.suspicious_ips.add(ip_address)

    def track_rate_limit_violation(self, ip_address: str, endpoint: str) -> int:
        """Track rate limit violations."""
        key = f"{ip_address}:{endpoint}"
        if key not in self.rate_limit_violations:
            self.rate_limit_violations[key] = []

        current_time = time.time()
        # Keep only violations from the last hour
        self.rate_limit_violations[key] = [t for t in self.rate_limit_violations[key] if current_time - t < 3600]

        self.rate_limit_violations[key].append(current_time)
        return len(self.rate_limit_violations[key])


# Global instances
_security_logger = SecurityAuditLogger()
_security_metrics = SecurityMetrics()


def get_security_logger(service_name: str | None = None) -> SecurityAuditLogger:
    """Get security audit logger instance."""
    if service_name:
        return SecurityAuditLogger(service_name)
    return _security_logger


def get_security_metrics() -> SecurityMetrics:
    """Get security metrics instance."""
    return _security_metrics


def log_security_event(event_type: SecurityEventType, level: SecurityLevel, message: str, **kwargs: Any) -> None:
    """Convenience function to log security events."""
    _security_logger.log_security_event(event_type, level, message, **kwargs)
