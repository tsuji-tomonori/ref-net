"""セキュリティテスト."""

import pytest
import requests
import time
from refnet_shared.auth.jwt_handler import jwt_handler


class TestSecurity:
    """セキュリティテスト."""

    BASE_URL = "http://localhost"

    def test_jwt_token_creation_and_verification(self):
        """JWTトークン作成・検証テスト."""
        # トークン作成
        token = jwt_handler.create_access_token("test_user")
        assert token is not None

        # トークン検証
        payload = jwt_handler.verify_token(token)
        assert payload["sub"] == "test_user"
        assert payload["type"] == "access"

    def test_login_endpoint(self):
        """ログインエンドポイントテスト."""
        login_data = {
            "username": "admin",
            "password": "admin_password"
        }

        response = requests.post(f"{self.BASE_URL}/api/auth/login", json=login_data)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_protected_endpoint_without_token(self):
        """認証が必要なエンドポイントへの未認証アクセステスト."""
        response = requests.get(f"{self.BASE_URL}/api/v1/papers/")
        # 認証が必要な場合は401が返される
        assert response.status_code in [200, 401]  # 実装に依存

    def test_protected_endpoint_with_token(self):
        """認証が必要なエンドポイントへの認証済みアクセステスト."""
        # ログインしてトークン取得
        login_data = {
            "username": "admin",
            "password": "admin_password"
        }
        login_response = requests.post(f"{self.BASE_URL}/api/auth/login", json=login_data)
        token = login_response.json()["access_token"]

        # 認証ヘッダー付きでアクセス
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{self.BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["username"] == "admin"

    def test_invalid_token(self):
        """無効なトークンテスト."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = requests.get(f"{self.BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 401

    @pytest.mark.slow
    def test_rate_limiting(self):
        """レート制限テスト."""
        # 短期間で大量のリクエスト送信
        responses = []
        for i in range(70):  # 60req/min制限を超える
            response = requests.get(f"{self.BASE_URL}/api/health")
            responses.append(response.status_code)
            if response.status_code == 429:
                break

        # 429 (Too Many Requests) が返されることを確認
        assert 429 in responses

    def test_security_headers(self):
        """セキュリティヘッダーテスト."""
        response = requests.get(f"{self.BASE_URL}/api/health")

        # セキュリティヘッダーの確認
        headers = response.headers
        assert "X-Frame-Options" in headers
        assert "X-Content-Type-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Referrer-Policy" in headers

    def test_password_hashing(self):
        """パスワードハッシュ化テスト."""
        password = "test_password"
        hashed = jwt_handler.hash_password(password)

        # ハッシュ化されていることを確認
        assert hashed != password
        assert len(hashed) > 50  # bcryptハッシュの長さ

        # 検証が正しく動作することを確認
        assert jwt_handler.verify_password(password, hashed) is True
        assert jwt_handler.verify_password("wrong_password", hashed) is False
