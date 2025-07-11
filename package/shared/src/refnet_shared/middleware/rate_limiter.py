"""レート制限ミドルウェア."""

import time
from collections.abc import Callable

import redis
import structlog
from fastapi import HTTPException, Request, status
from fastapi.responses import Response

from refnet_shared.config.environment import load_environment_settings
from refnet_shared.security.audit_logger import security_audit_logger

logger = structlog.get_logger(__name__)
settings = load_environment_settings()


class AdvancedRateLimiter:
    """高度なレート制限クラス."""

    def __init__(self) -> None:
        """初期化."""
        self.redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.database,
            decode_responses=True
        )

        # エンドポイント別レート制限設定
        self.endpoint_limits: dict[str, dict[str, int]] = {
            "/api/papers/": {"normal": 30, "burst": 60, "window": 60},
            "/api/papers/search": {"normal": 10, "burst": 20, "window": 60},
            "/api/papers/analyze": {"normal": 5, "burst": 10, "window": 60},
            "/api/batch/": {"normal": 2, "burst": 5, "window": 60},
            "/api/admin/": {"normal": 10, "burst": 20, "window": 60},
            "default": {"normal": 60, "burst": 100, "window": 60}
        }

    def get_endpoint_config(self, path: str) -> dict[str, int]:
        """エンドポイント設定を取得."""
        for endpoint, config in self.endpoint_limits.items():
            if endpoint != "default" and path.startswith(endpoint):
                return config
        return self.endpoint_limits["default"]

    def is_allowed(self, key: str, limit: int, window_seconds: int, burst_limit: int | None = None) -> tuple[bool, dict]:
        """レート制限チェック（通常・バースト対応）."""
        current_time = int(time.time())
        window_start = current_time - window_seconds

        pipe = self.redis_client.pipeline()

        # 古いエントリを削除
        pipe.zremrangebyscore(key, 0, window_start)

        # 現在のリクエスト数を取得
        pipe.zcard(key)

        # 現在のリクエストを追加
        pipe.zadd(key, {str(current_time): current_time})

        # TTLを設定
        pipe.expire(key, window_seconds)

        results = pipe.execute()
        current_requests = results[1]

        # バースト制限チェック（優先）
        if burst_limit and current_requests >= burst_limit:
            logger.warning("Burst rate limit exceeded", key=key, current_requests=current_requests, burst_limit=burst_limit)
            return False, {
                "allowed": False,
                "current_requests": current_requests,
                "limit": limit,
                "burst_limit": burst_limit,
                "window_seconds": window_seconds,
                "reset_time": current_time + window_seconds,
                "limit_type": "burst"
            }

        # 通常制限チェック
        if current_requests >= limit:
            logger.warning("Rate limit exceeded", key=key, current_requests=current_requests, limit=limit)
            return False, {
                "allowed": False,
                "current_requests": current_requests,
                "limit": limit,
                "burst_limit": burst_limit,
                "window_seconds": window_seconds,
                "reset_time": current_time + window_seconds,
                "limit_type": "normal"
            }

        return True, {
            "allowed": True,
            "current_requests": current_requests + 1,
            "limit": limit,
            "burst_limit": burst_limit,
            "window_seconds": window_seconds,
            "reset_time": current_time + window_seconds,
            "limit_type": "allowed"
        }

    def check_user_specific_limit(self, user_id: str, endpoint: str) -> tuple[bool, dict]:
        """ユーザー固有のレート制限チェック."""
        config = self.get_endpoint_config(endpoint)
        key = f"user_rate_limit:{user_id}:{endpoint}"

        return self.is_allowed(
            key=key,
            limit=config["normal"],
            window_seconds=config["window"],
            burst_limit=config["burst"]
        )

    def check_ip_limit(self, ip: str, endpoint: str) -> tuple[bool, dict]:
        """IP別レート制限チェック."""
        config = self.get_endpoint_config(endpoint)
        key = f"ip_rate_limit:{ip}:{endpoint}"

        return self.is_allowed(
            key=key,
            limit=config["normal"],
            window_seconds=config["window"],
            burst_limit=config["burst"]
        )


# グローバルインスタンス
advanced_rate_limiter = AdvancedRateLimiter()

# 後方互換性のためのエイリアス
RateLimiter = AdvancedRateLimiter
rate_limiter = advanced_rate_limiter


def create_advanced_rate_limit_middleware() -> Callable:
    """高度なレート制限ミドルウェア作成."""

    async def advanced_rate_limit_middleware(request: Request, call_next: Callable) -> Response:
        # クライアントIPを取得
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # API パスのみレート制限を適用
        if not request.url.path.startswith("/api/"):
            response = await call_next(request)
            return response  # type: ignore

        # ユーザー認証情報を取得（JWT等から）
        user_id: str | None = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # JWT トークンからユーザーIDを取得する処理
            # 実装は認証システムに依存するため、ここではスキップ
            # TODO: JWTデコード実装後に以下のようなコードを追加
            # try:
            #     token = auth_header.split(" ")[1]
            #     payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
            #     user_id = payload.get("user_id")
            # except Exception:
            #     pass
            pass

        # レート制限チェック（ユーザー認証があればユーザー別、なければIP別）
        if user_id is not None:
            allowed, info = advanced_rate_limiter.check_user_specific_limit(user_id, request.url.path)
            limit_key = f"user:{user_id}"
        else:
            allowed, info = advanced_rate_limiter.check_ip_limit(client_ip, request.url.path)
            limit_key = f"ip:{client_ip}"

        if not allowed:
            limit_type = info.get("limit_type", "normal")
            limit_value = info.get("burst_limit", info.get("limit", 0))

            logger.warning(
                "Rate limit exceeded",
                limit_key=limit_key,
                endpoint=request.url.path,
                limit_type=limit_type,
                current_requests=info.get("current_requests", 0),
                limit=limit_value
            )

            # セキュリティ監査ログに記録
            security_audit_logger.log_rate_limit_exceeded(
                user_id=user_id,
                ip_address=client_ip,
                endpoint=request.url.path,
                limit_type=limit_type,
                current_requests=info.get("current_requests", 0),
                limit=limit_value
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({limit_type})",
                headers={
                    "X-RateLimit-Limit": str(limit_value),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset_time"]),
                    "X-RateLimit-Limit-Type": limit_type,
                    "Retry-After": str(info["window_seconds"])
                },
            )

        response = await call_next(request)

        # レート制限ヘッダー追加
        current_limit = info.get("burst_limit", info.get("limit", 0))
        response.headers["X-RateLimit-Limit"] = str(current_limit)
        response.headers["X-RateLimit-Remaining"] = str(current_limit - info["current_requests"])
        response.headers["X-RateLimit-Reset"] = str(info["reset_time"])
        response.headers["X-RateLimit-Limit-Type"] = info.get("limit_type", "normal")

        return response  # type: ignore

    return advanced_rate_limit_middleware


# 後方互換性のための旧関数
def create_rate_limit_middleware(requests_per_minute: int = 60) -> Callable:
    """レート制限ミドルウェア作成（後方互換性）."""
    return create_advanced_rate_limit_middleware()
