"""キュー管理エンドポイント."""


import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from refnet_shared.models.database import ProcessingQueue
from sqlalchemy.orm import Session

from refnet_api.dependencies import get_db
from refnet_api.responses import QueueStatusResponse, TaskStatusResponse
from refnet_api.services.celery_service import CeleryService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/")
async def get_queue_status(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: str = Query(None),
    db: Session = Depends(get_db),
) -> QueueStatusResponse:
    """処理キュー状態取得."""
    query = db.query(ProcessingQueue)

    if status_filter:
        query = query.filter(ProcessingQueue.status == status_filter)

    queue_items = query.offset(skip).limit(limit).all()
    total = query.count()

    # シンプルなdict形式で返す
    items_data = [{
        'id': item.id,
        'paper_id': item.paper_id,
        'status': item.status,
        'task_type': item.task_type,
        'created_at': str(item.created_at),
        'updated_at': str(item.updated_at),
    } for item in queue_items]

    return QueueStatusResponse(queue_items=items_data, total=total)


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """タスク状態取得."""
    celery_service = CeleryService()
    status_info = celery_service.get_task_status(task_id)
    return TaskStatusResponse(
        task_id=task_id,
        status=status_info.get('status', 'unknown'),
        result=status_info.get('result'),
        error=status_info.get('error'),
        progress=status_info.get('progress'),
    )


@router.get("/papers/{paper_id}/queue")
async def get_paper_queue_status(
    paper_id: str, db: Session = Depends(get_db)
) -> QueueStatusResponse:
    """論文の処理キュー状態取得."""
    queue_items = db.query(ProcessingQueue).filter(ProcessingQueue.paper_id == paper_id).all()

    if not queue_items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No queue items found for this paper"
        )

    items_data = [{
        'id': item.id,
        'paper_id': item.paper_id,
        'status': item.status,
        'task_type': item.task_type,
        'created_at': str(item.created_at),
        'updated_at': str(item.updated_at),
    } for item in queue_items]

    return QueueStatusResponse(queue_items=items_data, total=len(items_data))
