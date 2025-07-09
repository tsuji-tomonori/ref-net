"""認証関連テスト."""

from unittest.mock import patch

import pytest

from refnet_shared.auth.jwt_handler import JWTHandler
from refnet_shared.exceptions import SecurityError


class TestJWTHandler:
    """JWTハンドラーテスト."""

    def test_init(self):
        """初期化テスト."""
        handler = JWTHandler()
        assert handler.secret_key is not None
        assert handler.algorithm == "HS256"
        assert handler.access_token_expire_minutes == 60
        assert handler.refresh_token_expire_days == 7

    def test_create_access_token(self):
        """アクセストークン生成テスト."""
        handler = JWTHandler()
        token = handler.create_access_token("test_user")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_claims(self):
        """アクセストークン生成テスト（追加claims）."""
        handler = JWTHandler()
        additional_claims = {"roles": ["admin"], "permissions": ["read"]}
        token = handler.create_access_token("test_user", additional_claims)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        """リフレッシュトークン生成テスト."""
        handler = JWTHandler()
        token = handler.create_refresh_token("test_user")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_valid(self):
        """有効なトークン検証テスト."""
        handler = JWTHandler()
        token = handler.create_access_token("test_user")
        payload = handler.verify_token(token)
        assert payload["sub"] == "test_user"
        assert payload["type"] == "access"

    def test_verify_token_invalid_type(self):
        """無効なトークンタイプテスト."""
        handler = JWTHandler()
        access_token = handler.create_access_token("test_user")
        with pytest.raises(SecurityError, match="Invalid token type"):
            handler.verify_token(access_token, "refresh")

    def test_extract_subject(self):
        """サブジェクト抽出テスト."""
        handler = JWTHandler()
        token = handler.create_access_token("test_user")
        subject = handler.extract_subject(token)
        assert subject == "test_user"

    def test_hash_password(self):
        """パスワードハッシュ化テスト."""
        handler = JWTHandler()
        password = "test_password"
        hashed = handler.hash_password(password)
        assert isinstance(hashed, str)
        assert hashed != password

    def test_verify_password_valid(self):
        """有効なパスワード検証テスト."""
        handler = JWTHandler()
        password = "test_password"
        hashed = handler.hash_password(password)
        assert handler.verify_password(password, hashed) is True

    def test_verify_password_invalid(self):
        """無効なパスワード検証テスト."""
        handler = JWTHandler()
        password = "test_password"
        hashed = handler.hash_password(password)
        assert handler.verify_password("wrong_password", hashed) is False

    @patch("refnet_shared.auth.jwt_handler.jwt.encode")
    def test_create_access_token_error(self, mock_encode):
        """アクセストークン生成エラーテスト."""
        mock_encode.side_effect = Exception("JWT encode error")
        handler = JWTHandler()
        with pytest.raises(SecurityError, match="Token creation failed"):
            handler.create_access_token("test_user")

    @patch("refnet_shared.auth.jwt_handler.jwt.encode")
    def test_create_refresh_token_error(self, mock_encode):
        """リフレッシュトークン生成エラーテスト."""
        mock_encode.side_effect = Exception("JWT encode error")
        handler = JWTHandler()
        with pytest.raises(SecurityError, match="Token creation failed"):
            handler.create_refresh_token("test_user")

    @patch("refnet_shared.auth.jwt_handler.jwt.decode")
    def test_verify_token_error(self, mock_decode):
        """トークン検証エラーテスト."""
        mock_decode.side_effect = Exception("JWT decode error")
        handler = JWTHandler()
        with pytest.raises(SecurityError, match="Token verification failed"):
            handler.verify_token("invalid_token")
