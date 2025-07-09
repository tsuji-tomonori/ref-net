"""レート制限ミドルウェア."""

import time
from collections.abc import Callable

import redis
import structlog
from fastapi import HTTPException, Request, status
from fastapi.responses import Response

from refnet_shared.config.environment import load_environment_settings

logger = structlog.get_logger(__name__)
settings = load_environment_settings()


class RateLimiter:
    """レート制限クラス."""

    def __init__(self) -> None:
        """初期化."""
        self.redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.database,
            decode_responses=True
        )

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, dict]:
        """レート制限チェック."""
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

        # レート制限チェック
        if current_requests >= limit:
            logger.warning("Rate limit exceeded", key=key, current_requests=current_requests, limit=limit)
            return False, {
                "allowed": False,
                "current_requests": current_requests,
                "limit": limit,
                "window_seconds": window_seconds,
                "reset_time": current_time + window_seconds
            }

        return True, {
            "allowed": True,
            "current_requests": current_requests + 1,
            "limit": limit,
            "window_seconds": window_seconds,
            "reset_time": current_time + window_seconds
        }


# グローバルインスタンス
rate_limiter = RateLimiter()


def create_rate_limit_middleware(requests_per_minute: int = 60) -> Callable:
    """レート制限ミドルウェア作成."""

    async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
        # クライアントIPを取得
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # API パスのみレート制限を適用
        if not request.url.path.startswith("/api/"):
            response = await call_next(request)
            return response  # type: ignore

        # レート制限チェック
        key = f"rate_limit:{client_ip}"
        allowed, info = rate_limiter.is_allowed(key, requests_per_minute, 60)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset_time"])
                }
            )

        response = await call_next(request)

        # レート制限ヘッダー追加
        response.headers["X-RateLimit-Limit"] = str(requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(requests_per_minute - info["current_requests"])
        response.headers["X-RateLimit-Reset"] = str(info["reset_time"])

        return response  # type: ignore

    return rate_limit_middleware
