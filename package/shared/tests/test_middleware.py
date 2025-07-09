"""ミドルウェアテスト."""

from unittest.mock import Mock, patch

from refnet_shared.middleware.rate_limiter import RateLimiter, create_rate_limit_middleware


class TestRateLimiter:
    """レート制限クラステスト."""

    def test_init(self):
        """初期化テスト."""
        limiter = RateLimiter()
        assert limiter.redis_client is not None

    @patch("refnet_shared.middleware.rate_limiter.redis.Redis")
    def test_is_allowed_under_limit(self, mock_redis):
        """制限内リクエストテスト."""
        mock_client = Mock()
        mock_redis.return_value = mock_client

        # パイプラインのモック
        mock_pipeline = Mock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [None, 5, None, True]

        limiter = RateLimiter()
        allowed, info = limiter.is_allowed("test_key", 10, 60)

        assert allowed is True
        assert info["current_requests"] == 6  # 5 + 1 (current)
        assert info["limit"] == 10
        assert info["reset_time"] is not None

    @patch("refnet_shared.middleware.rate_limiter.redis.Redis")
    def test_is_allowed_over_limit(self, mock_redis):
        """制限超過リクエストテスト."""
        mock_client = Mock()
        mock_redis.return_value = mock_client

        # パイプラインのモック
        mock_pipeline = Mock()
        mock_client.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [None, 10, None, True]

        limiter = RateLimiter()
        allowed, info = limiter.is_allowed("test_key", 10, 60)

        assert allowed is False
        assert info["current_requests"] == 10  # Already at limit
        assert info["limit"] == 10
        assert info["reset_time"] is not None


class TestRateLimitMiddleware:
    """レート制限ミドルウェアテスト."""

    def test_create_rate_limit_middleware(self):
        """レート制限ミドルウェア作成テスト."""
        middleware = create_rate_limit_middleware(100)
        assert callable(middleware)
