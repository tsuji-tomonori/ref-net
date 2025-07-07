"""FastAPI依存関係."""

from collections.abc import Generator

import structlog
from fastapi import HTTPException, status
from refnet_shared.exceptions import DatabaseError
from refnet_shared.models.database_manager import db_manager
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)


def get_db() -> Generator[Session, None, None]:
    """データベースセッション取得."""
    try:
        with db_manager.get_session() as session:
            yield session
    except DatabaseError as e:
        logger.error("Database error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database connection failed"
        ) from e


def get_current_user() -> dict[str, str]:
    """現在のユーザー取得（認証実装時に使用）."""
    # TODO: 認証実装
    return {"user_id": "system"}
