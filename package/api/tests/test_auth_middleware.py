"""認証ミドルウェアテスト."""

from typing import Any
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from refnet_api.middleware.auth import (
    get_current_user,
    require_permissions,
    require_roles,
)


class TestAuthMiddleware:
    """認証ミドルウェアテスト."""

    @patch("refnet_api.middleware.auth.jwt_handler")
    def test_get_current_user_success(self, mock_jwt_handler: Any) -> None:
        """現在のユーザー取得成功テスト."""
        mock_jwt_handler.verify_token.return_value = {
            "sub": "test_user",
            "roles": ["admin"],
            "permissions": ["read", "write"]
        }

        credentials = Mock()
        credentials.credentials = "valid_token"

        result = get_current_user(credentials)

        assert result["user_id"] == "test_user"
        assert result["roles"] == ["admin"]
        assert result["permissions"] == ["read", "write"]

    @patch("refnet_api.middleware.auth.jwt_handler")
    def test_get_current_user_invalid_token(self, mock_jwt_handler: Any) -> None:
        """無効なトークンでのユーザー取得テスト."""
        from refnet_api.middleware.auth import SecurityError
        mock_jwt_handler.verify_token.side_effect = SecurityError("Invalid token")

        credentials = Mock()
        credentials.credentials = "invalid_token"

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials)

        assert exc_info.value.status_code == 401

    def test_require_roles_success(self) -> None:
        """ロール確認成功テスト."""
        user = {
            "user_id": "test_user",
            "roles": ["admin", "user"],
            "permissions": ["read"]
        }

        role_checker = require_roles(["admin"])
        result = role_checker(user)

        assert result == user

    def test_require_roles_failure(self) -> None:
        """ロール確認失敗テスト."""
        user = {
            "user_id": "test_user",
            "roles": ["user"],
            "permissions": ["read"]
        }

        role_checker = require_roles(["admin"])

        with pytest.raises(HTTPException) as exc_info:
            role_checker(user)

        assert exc_info.value.status_code == 403

    def test_require_permissions_success(self) -> None:
        """権限確認成功テスト."""
        user = {
            "user_id": "test_user",
            "roles": ["user"],
            "permissions": ["papers:read", "papers:write"]
        }

        permission_checker = require_permissions(["papers:read"])
        result = permission_checker(user)

        assert result == user

    def test_require_permissions_failure(self) -> None:
        """権限確認失敗テスト."""
        user = {
            "user_id": "test_user",
            "roles": ["user"],
            "permissions": ["papers:read"]
        }

        permission_checker = require_permissions(["papers:write"])

        with pytest.raises(HTTPException) as exc_info:
            permission_checker(user)

        assert exc_info.value.status_code == 403
