"""認証エンドポイントテスト."""

from fastapi.testclient import TestClient

from refnet_api.main import app

client = TestClient(app)


class TestAuthEndpoints:
    """認証エンドポイントテスト."""

    def test_login_success(self):
        """ログイン成功テスト."""
        response = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin_password"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self):
        """ログイン失敗テスト."""
        response = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrong_password"
        })
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_login_user_not_found(self):
        """ユーザー存在しないテスト."""
        response = client.post("/api/auth/login", json={
            "username": "nonexistent",
            "password": "password"
        })
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_me_endpoint_without_token(self):
        """認証なしでmeエンドポイントアクセス."""
        response = client.get("/api/auth/me")
        assert response.status_code == 403

    def test_me_endpoint_with_token(self):
        """認証ありでmeエンドポイントアクセス."""
        # まずログイン
        login_response = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin_password"
        })
        token = login_response.json()["access_token"]

        # meエンドポイントアクセス
        response = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "admin"
        assert "admin" in data["roles"]

    def test_refresh_token_success(self):
        """リフレッシュトークン成功テスト."""
        # まずログイン
        login_response = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin_password"
        })
        refresh_token = login_response.json()["refresh_token"]

        # リフレッシュ
        response = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_token_invalid(self):
        """リフレッシュトークン失敗テスト."""
        response = client.post("/api/auth/refresh", json={
            "refresh_token": "invalid_token"
        })
        assert response.status_code == 401

    def test_logout_success(self):
        """ログアウト成功テスト."""
        # まずログイン
        login_response = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin_password"
        })
        token = login_response.json()["access_token"]

        # ログアウト
        response = client.post("/api/auth/logout", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]

    def test_logout_without_token(self):
        """認証なしでログアウト."""
        response = client.post("/api/auth/logout")
        assert response.status_code == 403
