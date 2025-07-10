"""認証・認可ミドルウェア."""

from collections.abc import Callable

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from refnet_shared.auth.jwt_handler import jwt_handler
from refnet_shared.exceptions import SecurityError
from refnet_shared.utils.security_audit import (
    SecurityEventType,
    SecurityLevel,
    get_security_logger,
    get_security_metrics,
)

logger = structlog.get_logger(__name__)
security = HTTPBearer()
security_logger = get_security_logger("refnet-api")
security_metrics = get_security_metrics()


class AuthenticationError(HTTPException):
    """認証エラー."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    """認可エラー."""

    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """現在のユーザー取得."""
    ip_address = "unknown"
    user_agent = None

    try:
        token = credentials.credentials
        payload = jwt_handler.verify_token(token)
        user_data = {
            "user_id": payload["sub"],
            "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", []),
        }

        # Log successful authentication
        security_logger.log_auth_success(
            user_id=user_data["user_id"],
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return user_data

    except SecurityError as e:
        logger.warning("Authentication failed", error=str(e))

        # Log authentication failure
        security_logger.log_auth_failure(
            username="unknown",
            ip_address=ip_address,
            reason=str(e),
            user_agent=user_agent,
        )

        raise AuthenticationError(str(e)) from e


def require_roles(required_roles: list[str]) -> Callable:
    """必要なロールの確認."""

    def role_checker(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        user_roles = current_user.get("roles", [])
        ip_address = "unknown"

        if not any(role in user_roles for role in required_roles):
            logger.warning(
                "Access denied",
                user_id=current_user["user_id"],
                required_roles=required_roles,
                user_roles=user_roles,
            )

            # Log authorization failure
            security_logger.log_security_event(
                SecurityEventType.AUTHZ_FAILURE,
                SecurityLevel.WARNING,
                f"Access denied: user lacks required roles {required_roles}",
                user_id=current_user["user_id"],
                ip_address=ip_address,
                additional_data={"required_roles": required_roles, "user_roles": user_roles},
            )

            raise AuthorizationError(f"Required roles: {', '.join(required_roles)}")

        # Log successful authorization
        security_logger.log_security_event(
            SecurityEventType.AUTHZ_SUCCESS,
            SecurityLevel.INFO,
            "Access granted: user has required roles",
            user_id=current_user["user_id"],
            ip_address=ip_address,
            additional_data={"required_roles": required_roles},
        )

        return current_user

    return role_checker


def require_permissions(required_permissions: list[str]) -> Callable:
    """必要な権限の確認."""

    def permission_checker(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        user_permissions = current_user.get("permissions", [])
        ip_address = "unknown"

        if not all(perm in user_permissions for perm in required_permissions):
            logger.warning(
                "Access denied",
                user_id=current_user["user_id"],
                required_permissions=required_permissions,
                user_permissions=user_permissions,
            )

            # Log authorization failure
            security_logger.log_security_event(
                SecurityEventType.AUTHZ_FAILURE,
                SecurityLevel.WARNING,
                f"Access denied: user lacks required permissions {required_permissions}",
                user_id=current_user["user_id"],
                ip_address=ip_address,
                additional_data={
                    "required_permissions": required_permissions,
                    "user_permissions": user_permissions,
                },
            )

            raise AuthorizationError(f"Required permissions: {', '.join(required_permissions)}")

        # Log successful authorization
        security_logger.log_security_event(
            SecurityEventType.AUTHZ_SUCCESS,
            SecurityLevel.INFO,
            "Access granted: user has required permissions",
            user_id=current_user["user_id"],
            ip_address=ip_address,
            additional_data={"required_permissions": required_permissions},
        )

        return current_user

    return permission_checker


# 管理者権限チェック
require_admin = require_roles(["admin"])

# 読み取り権限チェック
require_read_access = require_permissions(["papers:read"])

# 書き込み権限チェック
require_write_access = require_permissions(["papers:write"])
