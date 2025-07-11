"""モデル関連モジュール."""

from .database import (
    Author,
    Base,
    Journal,
    Paper,
    PaperExternalId,
    PaperFieldOfStudy,
    PaperKeyword,
    PaperRelation,
    ProcessingQueue,
    Venue,
    paper_authors,
)
from .database_manager import DatabaseManager, db_manager
from .schemas import (
    AuthorBase,
    AuthorCreate,
    AuthorResponse,
    DatabaseStats,
    PaperBase,
    PaperCreate,
    PaperExternalIdCreate,
    PaperExternalIdResponse,
    PaperKeywordCreate,
    PaperKeywordResponse,
    PaperRelationCreate,
    PaperRelationResponse,
    PaperResponse,
    PaperSearchParams,
    PaperSearchResponse,
    PaperUpdate,
    ProcessingQueueCreate,
    ProcessingQueueResponse,
)

__all__ = [
    # Database models
    "Base",
    "Paper",
    "Author",
    "PaperRelation",
    "Venue",
    "Journal",
    "PaperExternalId",
    "PaperFieldOfStudy",
    "PaperKeyword",
    "ProcessingQueue",
    "paper_authors",
    # Database manager
    "DatabaseManager",
    "db_manager",
    # Pydantic schemas
    "PaperBase",
    "PaperCreate",
    "PaperUpdate",
    "PaperResponse",
    "AuthorBase",
    "AuthorCreate",
    "AuthorResponse",
    "PaperRelationCreate",
    "PaperRelationResponse",
    "ProcessingQueueCreate",
    "ProcessingQueueResponse",
    "PaperKeywordCreate",
    "PaperKeywordResponse",
    "PaperExternalIdCreate",
    "PaperExternalIdResponse",
    "DatabaseStats",
    "PaperSearchParams",
    "PaperSearchResponse",
]
