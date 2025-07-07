"""著者関連エンドポイント."""


import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from refnet_shared.models.database import Author
from refnet_shared.models.schemas import AuthorResponse
from sqlalchemy.orm import Session

from refnet_api.dependencies import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/", response_model=list[AuthorResponse])
async def get_authors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """著者一覧取得."""
    authors = db.query(Author).offset(skip).limit(limit).all()
    return authors


@router.get("/{author_id}", response_model=AuthorResponse)
async def get_author(author_id: str, db: Session = Depends(get_db)):
    """著者詳細取得."""
    author = db.query(Author).filter(Author.author_id == author_id).first()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    return author


@router.get("/{author_id}/papers")
async def get_author_papers(author_id: str, db: Session = Depends(get_db)):
    """著者の論文一覧取得."""
    author = db.query(Author).filter(Author.author_id == author_id).first()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")

    return {"papers": [paper for paper in author.papers]}
