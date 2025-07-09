"""認証・認可ミドルウェア."""

from collections.abc import Callable

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from refnet_shared.auth.jwt_handler import jwt_handler
from refnet_shared.exceptions import SecurityError

logger = structlog.get_logger(__name__)
security = HTTPBearer()


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


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """現在のユーザー取得."""
    try:
        token = credentials.credentials
        payload = jwt_handler.verify_token(token)
        return {
            "user_id": payload["sub"],
            "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", [])
        }
    except SecurityError as e:
        logger.warning("Authentication failed", error=str(e))
        raise AuthenticationError(str(e)) from e


def require_roles(required_roles: list[str]) -> Callable:
    """必要なロールの確認."""
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = current_user.get("roles", [])
        if not any(role in user_roles for role in required_roles):
            logger.warning("Access denied", user_id=current_user["user_id"],
                         required_roles=required_roles, user_roles=user_roles)
            raise AuthorizationError(f"Required roles: {', '.join(required_roles)}")
        return current_user
    return role_checker


def require_permissions(required_permissions: list[str]) -> Callable:
    """必要な権限の確認."""
    def permission_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_permissions = current_user.get("permissions", [])
        if not all(perm in user_permissions for perm in required_permissions):
            logger.warning("Access denied", user_id=current_user["user_id"],
                         required_permissions=required_permissions,
                         user_permissions=user_permissions)
            raise AuthorizationError(f"Required permissions: {', '.join(required_permissions)}")
        return current_user
    return permission_checker


# 管理者権限チェック
require_admin = require_roles(["admin"])

# 読み取り権限チェック
require_read_access = require_permissions(["papers:read"])

# 書き込み権限チェック
require_write_access = require_permissions(["papers:write"])
