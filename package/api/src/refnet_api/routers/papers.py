"""論文関連エンドポイント."""



import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from refnet_shared.models.schemas import PaperCreate, PaperUpdate
from sqlalchemy.orm import Session

from refnet_api.dependencies import get_db
from refnet_api.responses import (
    MessageResponse,
    PaperCreateResponse,
    PaperListResponse,
    PaperRelationsResponse,
    PaperStatusResponse,
)
from refnet_api.responses import (
    PaperResponse as APIPaperResponse,
)
from refnet_api.services.paper_service import PaperService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=PaperListResponse)
async def get_papers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> PaperListResponse:
    """論文一覧取得."""
    service = PaperService(db)
    papers = service.get_papers(skip=skip, limit=limit)
    # 実際の実装では適切なカウントを取得
    total = len(papers)  # 簡易実装
    return PaperListResponse(
        papers=[APIPaperResponse.model_validate(paper) for paper in papers],
        total=total,
        page=skip // limit + 1,
        per_page=limit,
    )


@router.get("/{paper_id}", response_model=APIPaperResponse)
async def get_paper(paper_id: str, db: Session = Depends(get_db)) -> APIPaperResponse:
    """論文詳細取得."""
    service = PaperService(db)
    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")
    return APIPaperResponse.model_validate(paper)


@router.post("/", response_model=PaperCreateResponse)
async def create_paper(paper: PaperCreate, db: Session = Depends(get_db)) -> PaperCreateResponse:
    """論文作成."""
    service = PaperService(db)

    # 既存チェック
    existing_paper = service.get_paper(paper.paper_id)
    if existing_paper:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Paper already exists")

    created_paper = service.create_paper(paper)
    return PaperCreateResponse(
        paper_id=created_paper.paper_id,
        message="Paper created successfully",
    )


@router.put("/{paper_id}", response_model=APIPaperResponse)
async def update_paper(
    paper_id: str, paper_update: PaperUpdate, db: Session = Depends(get_db)
) -> APIPaperResponse:
    """論文更新."""
    service = PaperService(db)

    # 存在チェック
    existing_paper = service.get_paper(paper_id)
    if not existing_paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

    updated_paper = service.update_paper(paper_id, paper_update)
    return APIPaperResponse.model_validate(updated_paper)


@router.post("/{paper_id}/process")
async def process_paper(paper_id: str, db: Session = Depends(get_db)) -> MessageResponse:
    """論文処理開始."""
    service = PaperService(db)

    # 存在チェック
    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

    # 処理キューに追加
    task_id = service.queue_paper_processing(paper_id)

    return MessageResponse(message=f"Paper processing started for {paper_id} (task: {task_id})")


@router.get("/{paper_id}/status")
async def get_paper_status(paper_id: str, db: Session = Depends(get_db)) -> PaperStatusResponse:
    """論文処理状態取得."""
    service = PaperService(db)

    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

    return PaperStatusResponse(
        paper_id=paper_id,
        crawl_status=paper.crawl_status,
        pdf_status=paper.pdf_status,
        summary_status=paper.summary_status,
    )


@router.get("/{paper_id}/relations")
async def get_paper_relations(
    paper_id: str, relation_type: str | None = Query(None), db: Session = Depends(get_db)
) -> PaperRelationsResponse:
    """論文関係取得."""
    service = PaperService(db)

    paper = service.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found")

    relations = service.get_paper_relations(paper_id, relation_type)
    return PaperRelationsResponse(
        paper_id=paper_id,
        references=[],  # 実際の実装で適切なデータを設定
        citations=[],
        related_papers=relations,
    )
