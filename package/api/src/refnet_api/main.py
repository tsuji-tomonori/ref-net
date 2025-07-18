"""RefNet APIメインアプリケーション."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from refnet_shared.config.environment import load_environment_settings
from refnet_shared.utils import setup_logging

from refnet_api.responses import HealthResponse, MessageResponse
from refnet_api.routers import auth, authors, papers, queue

# 設定とロギング設定
settings = load_environment_settings()
setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """アプリケーションライフサイクル管理."""
    logger.info("Starting RefNet API", environment=settings.environment.value)
    yield
    logger.info("Shutting down RefNet API")


# FastAPIアプリケーション
app = FastAPI(
    title="RefNet API",
    description="論文関係性可視化システム API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development() else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(papers.router, prefix="/api/v1/papers", tags=["papers"])
app.include_router(authors.router, prefix="/api/v1/authors", tags=["authors"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["queue"])


@app.get("/")
async def root() -> MessageResponse:
    """ルートエンドポイント."""
    return MessageResponse(message=f"RefNet API v0.1.0 - {settings.environment.value}")


@app.get("/health")
async def health_check() -> HealthResponse:
    """ヘルスチェック."""
    from redis import Redis
    from refnet_shared.models.database_manager import db_manager

    # データベース接続チェック
    db_health = db_manager.health_check()

    # Redis接続チェック
    redis_health = {"status": "healthy"}
    try:
        redis_client = Redis.from_url(settings.redis.url)
        redis_client.ping()
    except Exception as e:
        redis_health = {"status": "unhealthy", "error": str(e)}

    # 全体のヘルスステータス決定
    db_healthy = db_health["status"] == "healthy"
    redis_healthy = redis_health["status"] == "healthy"
    overall_status = "healthy" if db_healthy and redis_healthy else "unhealthy"

    return HealthResponse(
        status=overall_status,
        message=f"API is running - DB: {db_health['status']}, Redis: {redis_health['status']}"
    )


def run() -> None:
    """開発サーバー起動."""
    import uvicorn

    uvicorn.run(
        "refnet_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development(),
        log_level=settings.logging.level.lower(),
    )


if __name__ == "__main__":
    run()
