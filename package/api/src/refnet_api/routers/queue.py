"""キュー管理エンドポイント."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from refnet_shared.models.database import ProcessingQueue
from sqlalchemy.orm import Session

from refnet_api.dependencies import get_db
from refnet_api.services.celery_service import CeleryService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/")
async def get_queue_status(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: str = Query(None),
    db: Session = Depends(get_db),
) -> list[Any]:
    """処理キュー状態取得."""
    query = db.query(ProcessingQueue)

    if status_filter:
        query = query.filter(ProcessingQueue.status == status_filter)

    queue_items = query.offset(skip).limit(limit).all()
    return queue_items


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> dict[str, Any]:
    """タスク状態取得."""
    celery_service = CeleryService()
    status_info = celery_service.get_task_status(task_id)
    return status_info


@router.get("/papers/{paper_id}/queue")
async def get_paper_queue_status(paper_id: str, db: Session = Depends(get_db)) -> list[Any]:
    """論文の処理キュー状態取得."""
    queue_items = db.query(ProcessingQueue).filter(ProcessingQueue.paper_id == paper_id).all()

    if not queue_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No queue items found for this paper"
        )

    return queue_items
