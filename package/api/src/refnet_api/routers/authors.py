"""著者関連エンドポイント."""



import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from refnet_shared.models.database import Author
from sqlalchemy.orm import Session

from refnet_api.dependencies import get_db
from refnet_api.responses import (
    AuthorListResponse,
    AuthorPapersResponse,
)
from refnet_api.responses import (
    AuthorResponse as APIAuthorResponse,
)
from refnet_api.responses.author import PaperSummary

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=AuthorListResponse)
async def get_authors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> AuthorListResponse:
    """著者一覧取得."""
    authors = db.query(Author).offset(skip).limit(limit).all()
    total = db.query(Author).count()
    return AuthorListResponse(
        authors=[APIAuthorResponse.model_validate(author) for author in authors],
        total=total,
        page=skip // limit + 1,
        per_page=limit,
    )


@router.get("/{author_id}", response_model=APIAuthorResponse)
async def get_author(author_id: str, db: Session = Depends(get_db)) -> APIAuthorResponse:
    """著者詳細取得."""
    author = db.query(Author).filter(Author.author_id == author_id).first()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    return APIAuthorResponse.model_validate(author)


@router.get("/{author_id}/papers")
async def get_author_papers(author_id: str, db: Session = Depends(get_db)) -> AuthorPapersResponse:
    """著者の論文一覧取得."""
    author = db.query(Author).filter(Author.author_id == author_id).first()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")

    papers = [PaperSummary(id=p.paper_id, title=p.title) for p in author.papers]
    return AuthorPapersResponse(
        author_id=author_id,
        papers=papers,
        total=len(papers),
    )
