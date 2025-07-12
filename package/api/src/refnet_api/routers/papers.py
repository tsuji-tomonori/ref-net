"""論文関連エンドポイント."""



import re

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from refnet_shared.celery_app import app as celery_app
from refnet_shared.models.paper import Paper
from refnet_shared.models.schemas import PaperCreate, PaperRelationResponse, PaperUpdate
from sqlalchemy.orm import Session

from refnet_api.dependencies import get_db
from refnet_api.middleware.auth import get_current_user
from refnet_api.responses import (
    MessageResponse,
    PaperCreateResponse,
    PaperListResponse,
    PaperRelationsResponse,
)
from refnet_api.responses import (
    PaperResponse as APIPaperResponse,
)
from refnet_api.services.paper_service import PaperService

logger = structlog.get_logger(__name__)
router = APIRouter()


class PaperCrawlRequest(BaseModel):
    paper_url: str


def extract_paper_id(paper_url: str) -> str:
    """Semantic Scholar URLから論文IDを抽出"""
    # Semantic Scholar URL形式: https://www.semanticscholar.org/paper/{paper_id}
    pattern = r'semanticscholar\.org/paper/([a-f0-9]+)'
    match = re.search(pattern, paper_url)
    if not match:
        raise ValueError(f"Invalid Semantic Scholar URL: {paper_url}")
    return match.group(1)


@router.get("/", response_model=PaperListResponse)
async def get_papers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # 認証必須化
) -> PaperListResponse:
    """論文一覧取得（認証必須）."""
    logger.info("Papers list requested", user_id=current_user["user_id"], skip=skip, limit=limit)
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


@router.post("/", response_model=PaperCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_paper(
    paper: PaperCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # 追加
) -> PaperCreateResponse:
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
    paper_id: str,
    paper_update: PaperUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # 追加
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
async def get_paper_status(paper_id: str, db: Session = Depends(get_db)) -> dict:
    """論文の処理状況を取得"""
    paper = db.query(Paper).filter(Paper.paper_id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return {
        "paper_id": paper.paper_id,
        "is_crawled": paper.is_crawled,
        "is_summarized": paper.is_summarized,
        "is_generated": paper.is_generated,
        "created_at": paper.created_at,
        "updated_at": paper.updated_at
    }


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

    # 関係タイプによって分類
    references = []
    citations = []
    related_papers = []

    for relation in relations:
        relation_response = PaperRelationResponse.model_validate(relation)
        if relation.relation_type == "reference" and relation.source_paper_id == paper_id:
            references.append(relation_response)
        elif relation.relation_type == "citation" and relation.target_paper_id == paper_id:
            citations.append(relation_response)
        else:
            related_papers.append(relation_response)

    return PaperRelationsResponse(
        paper_id=paper_id,
        references=references,
        citations=citations,
        related_papers=related_papers,
    )


@router.post("/crawl")
async def trigger_paper_crawl(
    request: PaperCrawlRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """論文のクロールをトリガー"""
    try:
        # Semantic Scholar Paper IDを抽出
        paper_id = extract_paper_id(request.paper_url)

        # データベースに論文エントリを作成
        existing_paper = db.query(Paper).filter(Paper.paper_id == paper_id).first()
        if existing_paper:
            return {
                "status": "already_exists",
                "paper_id": paper_id,
                "message": "Paper already exists in database"
            }

        paper = Paper(
            paper_id=paper_id,
            url=request.paper_url,
            is_crawled=False,
            is_summarized=False,
            is_generated=False
        )
        db.add(paper)
        db.commit()

        # Crawlerタスクをキュー
        task = celery_app.send_task(
            'refnet_crawler.tasks.crawl_task.crawl_paper',
            args=[paper.paper_id],
            queue='crawler'
        )

        logger.info(
            "Paper crawl triggered",
            paper_id=paper.paper_id,
            task_id=task.id,
            user_id=current_user["user_id"]
        )

        return {
            "status": "queued",
            "paper_id": paper.paper_id,
            "task_id": task.id
        }
    except Exception as e:
        logger.error("Failed to trigger paper crawl", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e
