"""論文関連エンドポイント."""


from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from refnet_shared.models.schemas import PaperCreate, PaperResponse, PaperUpdate
from sqlalchemy.orm import Session

from refnet_api.dependencies import get_db
from refnet_api.services.paper_service import PaperService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=list[PaperResponse])
async def get_papers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[Any]:
    """論文一覧取得."""
    service = PaperService(db)
    papers = service.get_papers(skip=skip, limit=limit)
    return papers


@router.get("/{paper_id}", response_model=PaperResponse)
async def get_paper(paper_id: str, db: Session = Depends(get_db)) -> Any:
    """論文詳細取得."""
    service = PaperService(db)
    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")
    return paper


@router.post("/", response_model=PaperResponse)
async def create_paper(paper: PaperCreate, db: Session = Depends(get_db)) -> Any:
    """論文作成."""
    service = PaperService(db)

    # 既存チェック
    existing_paper = service.get_paper(paper.paper_id)
    if existing_paper:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Paper already exists")

    created_paper = service.create_paper(paper)
    return created_paper


@router.put("/{paper_id}", response_model=PaperResponse)
async def update_paper(
    paper_id: str, paper_update: PaperUpdate, db: Session = Depends(get_db)
) -> Any:
    """論文更新."""
    service = PaperService(db)

    # 存在チェック
    existing_paper = service.get_paper(paper_id)
    if not existing_paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

    updated_paper = service.update_paper(paper_id, paper_update)
    return updated_paper


@router.post("/{paper_id}/process")
async def process_paper(paper_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """論文処理開始."""
    service = PaperService(db)

    # 存在チェック
    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

    # 処理キューに追加
    task_id = service.queue_paper_processing(paper_id)

    return {"message": "Paper processing started", "paper_id": paper_id, "task_id": task_id}


@router.get("/{paper_id}/status")
async def get_paper_status(paper_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    """論文処理状態取得."""
    service = PaperService(db)

    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

    return {
        "paper_id": paper_id,
        "crawl_status": paper.crawl_status,
        "pdf_status": paper.pdf_status,
        "summary_status": paper.summary_status,
    }


@router.get("/{paper_id}/relations")
async def get_paper_relations(
    paper_id: str, relation_type: str | None = Query(None), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """論文関係取得."""
    service = PaperService(db)

    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

    relations = service.get_paper_relations(paper_id, relation_type)
    return {"relations": relations}
