"""キュー関連レスポンスモデル."""

from typing import Any

from .base import BaseResponse


class QueueItemResponse(BaseResponse):
    """キューアイテムレスポンス."""

    id: int
    paper_id: str
    status: str
    task_type: str
    created_at: str
    updated_at: str


class QueueStatusResponse(BaseResponse):
    """キューステータスレスポンス."""

    queue_items: list[dict[str, Any]]
    total: int


class TaskStatusResponse(BaseResponse):
    """タスクステータスレスポンス."""

    task_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    progress: float | None = None
