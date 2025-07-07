"""ユーティリティモジュール."""

import logging
import sys
from typing import Any

import structlog

from refnet_shared.config import settings


def setup_logging() -> None:
    """ロギング設定の初期化."""
    # 基本設定
    logging.basicConfig(
        level=getattr(logging, settings.logging.level.upper()),
        stream=sys.stdout,
    )

    # Structlogの設定
    if settings.logging.format == "json":
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """ロガー取得."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def validate_required_settings() -> None:
    """必須設定の検証."""
    errors = []

    # データベース設定の検証
    if not settings.database.host:
        errors.append("DATABASE__HOST is required")

    # 本番環境でのセキュリティ設定検証
    if not settings.debug:
        if settings.security.jwt_secret == "development-secret-key":
            errors.append("SECURITY__JWT_SECRET must be set in production")

    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")


def get_app_info() -> dict[str, Any]:
    """アプリケーション情報取得."""
    return {
        "name": settings.app_name,
        "version": settings.version,
        "debug": settings.debug,
        "database_url": settings.database.url.replace(settings.database.password or "", "***"),
        "redis_url": settings.redis.url,
        "logging_level": settings.logging.level,
    }
