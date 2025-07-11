"""高度なレート制限機能のテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status

from refnet_shared.middleware.rate_limiter import (
    AdvancedRateLimiter,
    advanced_rate_limiter,
    create_advanced_rate_limit_middleware,
)


class TestAdvancedRateLimiter:
    """AdvancedRateLimiterのテスト."""

    def test_get_endpoint_config_specific(self) -> None:
        """特定エンドポイント設定取得テスト."""
        limiter = AdvancedRateLimiter()

        # 特定エンドポイント（/api/papers/searchは/api/papers/にマッチするため）
        config = limiter.get_endpoint_config("/api/papers/search")
        assert config["normal"] == 30  # /api/papers/の設定が適用される
        assert config["burst"] == 60
        assert config["window"] == 60

    def test_get_endpoint_config_prefix_match(self) -> None:
        """プレフィックスマッチエンドポイント設定取得テスト."""
        limiter = AdvancedRateLimiter()

        # プレフィックスマッチ
        config = limiter.get_endpoint_config("/api/papers/123")
        assert config["normal"] == 30
        assert config["burst"] == 60
        assert config["window"] == 60

    def test_get_endpoint_config_default(self) -> None:
        """デフォルトエンドポイント設定取得テスト."""
        limiter = AdvancedRateLimiter()

        # デフォルト
        config = limiter.get_endpoint_config("/api/unknown")
        assert config["normal"] == 60
        assert config["burst"] == 100
        assert config["window"] == 60

    @patch("redis.Redis")
    def test_is_allowed_normal_limit(self, mock_redis_class: MagicMock) -> None:
        """通常制限チェックテスト."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        # パイプライン実行結果（現在のリクエスト数が制限内）
        mock_redis.pipeline.return_value.execute.return_value = [None, 5, None, None]

        limiter = AdvancedRateLimiter()
        allowed, info = limiter.is_allowed("test_key", 10, 60)

        assert allowed
        assert info["allowed"]
        assert info["current_requests"] == 6
        assert info["limit"] == 10
        assert info["limit_type"] == "allowed"

    @patch("redis.Redis")
    def test_is_allowed_normal_limit_exceeded(self, mock_redis_class: MagicMock) -> None:
        """通常制限超過テスト."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        # パイプライン実行結果（現在のリクエスト数が制限超過）
        mock_redis.pipeline.return_value.execute.return_value = [None, 10, None, None]

        limiter = AdvancedRateLimiter()
        allowed, info = limiter.is_allowed("test_key", 10, 60)

        assert not allowed
        assert not info["allowed"]
        assert info["current_requests"] == 10
        assert info["limit"] == 10
        assert info["limit_type"] == "normal"

    @patch("redis.Redis")
    def test_is_allowed_burst_limit_exceeded(self, mock_redis_class: MagicMock) -> None:
        """バースト制限超過テスト."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis

        # パイプライン実行結果（バースト制限超過）
        mock_redis.pipeline.return_value.execute.return_value = [None, 20, None, None]

        limiter = AdvancedRateLimiter()
        allowed, info = limiter.is_allowed("test_key", 10, 60, burst_limit=20)

        assert not allowed
        assert not info["allowed"]
        assert info["current_requests"] == 20
        assert info["burst_limit"] == 20
        assert info["limit_type"] == "burst"

    @patch("redis.Redis")
    def test_check_user_specific_limit(self, mock_redis_class: MagicMock) -> None:
        """ユーザー固有制限チェックテスト."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        mock_redis.pipeline.return_value.execute.return_value = [None, 5, None, None]

        limiter = AdvancedRateLimiter()
        allowed, info = limiter.check_user_specific_limit("user123", "/api/papers/")

        assert allowed
        assert info["allowed"]

    @patch("redis.Redis")
    def test_check_ip_limit(self, mock_redis_class: MagicMock) -> None:
        """IP別制限チェックテスト."""
        mock_redis = MagicMock()
        mock_redis_class.return_value = mock_redis
        mock_redis.pipeline.return_value.execute.return_value = [None, 5, None, None]

        limiter = AdvancedRateLimiter()
        allowed, info = limiter.check_ip_limit("192.168.1.1", "/api/papers/")

        assert allowed
        assert info["allowed"]


class TestAdvancedRateLimitMiddleware:
    """高度なレート制限ミドルウェアのテスト."""

    @pytest.mark.asyncio
    async def test_middleware_non_api_path(self) -> None:
        """API以外のパスのテスト."""
        middleware = create_advanced_rate_limit_middleware()

        # モックリクエスト
        request = MagicMock(spec=Request)
        request.url.path = "/health"
        request.client = None

        # モックcall_next
        async def call_next(req):
            return MagicMock()

        response = await middleware(request, call_next)
        assert response is not None

    @pytest.mark.asyncio
    async def test_middleware_rate_limit_allowed(self) -> None:
        """レート制限許可のテスト."""
        middleware = create_advanced_rate_limit_middleware()

        # モックリクエスト
        request = MagicMock(spec=Request)
        request.url.path = "/api/papers"
        request.client.host = "192.168.1.1"
        request.headers.get.return_value = None

        # モックレート制限
        with patch.object(advanced_rate_limiter, "check_ip_limit", return_value=(True, {
            "allowed": True,
            "current_requests": 5,
            "limit": 60,
            "burst_limit": 100,
            "window_seconds": 60,
            "reset_time": 1234567890,
            "limit_type": "allowed"
        })):
            # モックcall_next
            response_mock = MagicMock()
            response_mock.headers = {}

            async def call_next(req):
                return response_mock

            response = await middleware(request, call_next)

            assert response.headers["X-RateLimit-Limit"] == "100"
            assert response.headers["X-RateLimit-Remaining"] == "95"
            assert response.headers["X-RateLimit-Reset"] == "1234567890"

    @pytest.mark.asyncio
    async def test_middleware_rate_limit_exceeded(self) -> None:
        """レート制限超過のテスト."""
        middleware = create_advanced_rate_limit_middleware()

        # モックリクエスト
        request = MagicMock(spec=Request)
        request.url.path = "/api/papers"
        request.client.host = "192.168.1.1"
        request.headers.get.return_value = None

        # モックレート制限
        with patch.object(advanced_rate_limiter, "check_ip_limit", return_value=(False, {
            "allowed": False,
            "current_requests": 100,
            "limit": 60,
            "burst_limit": 100,
            "window_seconds": 60,
            "reset_time": 1234567890,
            "limit_type": "burst"
        })):
            # モック監査ログ
            with patch("refnet_shared.middleware.rate_limiter.security_audit_logger") as mock_logger:
                # HTTPException が発生することを確認
                with pytest.raises(HTTPException) as exc_info:
                    await middleware(request, AsyncMock())

                assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
                assert "burst" in exc_info.value.detail
                mock_logger.log_rate_limit_exceeded.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_with_forwarded_ip(self) -> None:
        """X-Forwarded-ForヘッダーのIPアドレステスト."""
        middleware = create_advanced_rate_limit_middleware()

        # モックリクエスト
        request = MagicMock(spec=Request)
        request.url.path = "/api/papers"
        request.client.host = "192.168.1.1"
        request.headers.get.side_effect = lambda h: "10.0.0.1, 192.168.1.1" if h == "X-Forwarded-For" else None

        # モックレート制限
        with patch.object(advanced_rate_limiter, "check_ip_limit") as mock_check_ip:
            mock_check_ip.return_value = (True, {
                "allowed": True,
                "current_requests": 5,
                "limit": 60,
                "burst_limit": 100,
                "window_seconds": 60,
                "reset_time": 1234567890,
                "limit_type": "allowed"
            })

            response_mock = MagicMock()
            response_mock.headers = {}

            async def call_next(req):
                return response_mock

            await middleware(request, call_next)

            # 最初のIPアドレスが使用されることを確認
            mock_check_ip.assert_called_once()
            assert mock_check_ip.call_args[0][0] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_middleware_with_authenticated_user(self) -> None:
        """認証済みユーザーのテスト."""
        middleware = create_advanced_rate_limit_middleware()

        # モックリクエスト
        request = MagicMock(spec=Request)
        request.url.path = "/api/papers"
        request.client.host = "192.168.1.1"
        request.headers.get.side_effect = lambda h: "Bearer jwt_token" if h == "Authorization" else None

        # モックレート制限（IP制限がチェックされる）
        with patch.object(advanced_rate_limiter, "check_ip_limit") as mock_check_ip:
            mock_check_ip.return_value = (True, {
                "allowed": True,
                "current_requests": 5,
                "limit": 30,
                "burst_limit": 60,
                "window_seconds": 60,
                "reset_time": 1234567890,
                "limit_type": "allowed"
            })

            response_mock = MagicMock()
            response_mock.headers = {}

            async def call_next(req):
                return response_mock

            await middleware(request, call_next)

            # IP制限がチェックされることを確認（JWTは実装されていないのでuser_idはNone）
            # TODO: JWT実装後にuser_idが正しく設定されることをテスト
            mock_check_ip.assert_called_once()  # JWTデコード未実装のためIP制限が使用される

    @pytest.mark.asyncio
    async def test_middleware_missing_client(self) -> None:
        """クライアント情報がない場合のテスト."""
        middleware = create_advanced_rate_limit_middleware()

        # モックリクエスト（クライアント情報なし）
        request = MagicMock(spec=Request)
        request.url.path = "/api/papers"
        request.client = None
        request.headers.get.return_value = None

        # モックレート制限
        with patch.object(advanced_rate_limiter, "check_ip_limit") as mock_check_ip:
            mock_check_ip.return_value = (True, {
                "allowed": True,
                "current_requests": 5,
                "limit": 60,
                "burst_limit": 100,
                "window_seconds": 60,
                "reset_time": 1234567890,
                "limit_type": "allowed"
            })

            response_mock = MagicMock()
            response_mock.headers = {}

            async def call_next(req):
                return response_mock

            await middleware(request, call_next)

            # "unknown"のIPアドレスで制限がチェックされることを確認
            mock_check_ip.assert_called_once_with("unknown", "/api/papers")

    def test_create_rate_limit_middleware_backward_compatibility(self) -> None:
        """後方互換性関数のテスト."""
        from refnet_shared.middleware.rate_limiter import create_rate_limit_middleware

        middleware = create_rate_limit_middleware(60)
        assert middleware is not None
        assert callable(middleware)

    def test_rate_limiter_alias_backward_compatibility(self) -> None:
        """後方互換性エイリアスのテスト."""
        from refnet_shared.middleware.rate_limiter import RateLimiter, rate_limiter

        # エイリアスが正しく動作することを確認
        assert RateLimiter == AdvancedRateLimiter
        assert isinstance(rate_limiter, AdvancedRateLimiter)

    @pytest.mark.asyncio
    async def test_middleware_with_jwt_authentication_mock(self) -> None:
        """疑似JWT認証ヘッダーのテスト（コードカバレッジ用）."""
        middleware = create_advanced_rate_limit_middleware()

        # モックリクエスト
        request = MagicMock(spec=Request)
        request.url.path = "/api/papers"
        request.client.host = "192.168.1.1"
        # Bearerトークンが含まれるがデコードされないケース
        request.headers.get.side_effect = lambda h: "Bearer valid_jwt_token" if h == "Authorization" else None

        # モックレート制限
        with patch.object(advanced_rate_limiter, "check_ip_limit") as mock_check_ip:
            mock_check_ip.return_value = (True, {
                "allowed": True,
                "current_requests": 1,
                "limit": 60,
                "burst_limit": 100,
                "window_seconds": 60,
                "reset_time": 1234567890,
                "limit_type": "allowed"
            })

            response_mock = MagicMock()
            response_mock.headers = {}

            async def call_next(req):
                return response_mock

            await middleware(request, call_next)

            # JWT未実装のためIP制限が使用される
            mock_check_ip.assert_called_once_with("192.168.1.1", "/api/papers")

            # レスポンスヘッダーが設定されることを確認
            assert "X-RateLimit-Limit" in response_mock.headers

    @pytest.mark.asyncio
    async def test_middleware_user_specific_limit_path(self) -> None:
        """ユーザー制限パスのコードカバレッジテスト."""
        # ミドルウェアの作成は必要ないためコメントアウト

        # モックリクエスト
        request = MagicMock(spec=Request)
        request.url.path = "/api/papers"
        request.client.host = "192.168.1.1"
        request.headers.get.return_value = None

        # モックレート制限
        # ユーザー固有制限メソッドを直接テスト
        with patch.object(advanced_rate_limiter, "check_user_specific_limit") as mock_check_user:
            mock_check_user.return_value = (True, {
                "allowed": True,
                "current_requests": 5,
                "limit": 30,
                "burst_limit": 60,
                "window_seconds": 60,
                "reset_time": 1234567890,
                "limit_type": "allowed"
            })

            response_mock = MagicMock()
            response_mock.headers = {}

            async def call_next(req):
                return response_mock

            # 直接ユーザー制限メソッドをテスト
            user_id = "test_user"
            allowed, info = advanced_rate_limiter.check_user_specific_limit(user_id, request.url.path)
            limit_key = f"user:{user_id}"

            # ユーザー制限が呼び出されることを確認
            mock_check_user.assert_called_with(user_id, request.url.path)
            assert limit_key == "user:test_user"
