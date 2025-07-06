"""Pydanticスキーマ定義."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# Paper スキーマ
class PaperBase(BaseModel):
    """論文基底スキーマ."""
    title: str = Field(..., min_length=1, max_length=2000)
    abstract: str | None = Field(None, max_length=10000)
    year: int | None = Field(None, ge=1900, le=2100)
    citation_count: int = Field(default=0, ge=0)
    reference_count: int = Field(default=0, ge=0)
    language: str | None = Field(None, max_length=10)
    is_open_access: bool = Field(default=False)


class PaperCreate(PaperBase):
    """論文作成スキーマ."""
    paper_id: str = Field(..., min_length=1, max_length=255)


class PaperUpdate(BaseModel):
    """論文更新スキーマ."""
    title: str | None = Field(None, min_length=1, max_length=2000)
    abstract: str | None = Field(None, max_length=10000)
    year: int | None = Field(None, ge=1900, le=2100)
    citation_count: int | None = Field(None, ge=0)
    reference_count: int | None = Field(None, ge=0)
    summary: str | None = Field(None, max_length=50000)
    pdf_url: str | None = Field(None, max_length=2048)
    pdf_hash: str | None = Field(None, max_length=64)
    crawl_status: str | None = Field(None, pattern=r'^(pending|running|completed|failed)$')
    pdf_status: str | None = Field(None, pattern=r'^(pending|running|completed|failed|unavailable)$')
    summary_status: str | None = Field(None, pattern=r'^(pending|running|completed|failed)$')


class PaperResponse(PaperBase):
    """論文レスポンススキーマ."""
    paper_id: str
    crawl_status: str
    pdf_status: str
    summary_status: str
    summary: str | None = None
    pdf_url: str | None = None
    venue_id: str | None = None
    journal_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Author スキーマ
class AuthorBase(BaseModel):
    """著者基底スキーマ."""
    name: str = Field(..., min_length=1, max_length=500)
    affiliations: str | None = Field(None, max_length=2000)
    homepage_url: str | None = Field(None, max_length=2048)
    orcid: str | None = Field(None, max_length=19, pattern=r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$')


class AuthorCreate(AuthorBase):
    """著者作成スキーマ."""
    author_id: str = Field(..., min_length=1, max_length=255)


class AuthorResponse(AuthorBase):
    """著者レスポンススキーマ."""
    author_id: str
    paper_count: int
    citation_count: int
    h_index: int | None = None

    model_config = ConfigDict(from_attributes=True)


# Relation スキーマ
class PaperRelationCreate(BaseModel):
    """論文関係作成スキーマ."""
    source_paper_id: str = Field(..., min_length=1, max_length=255)
    target_paper_id: str = Field(..., min_length=1, max_length=255)
    relation_type: str = Field(..., pattern=r'^(citation|reference)$')
    hop_count: int = Field(default=1, ge=1)
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)


class PaperRelationResponse(BaseModel):
    """論文関係レスポンススキーマ."""
    id: int
    source_paper_id: str
    target_paper_id: str
    relation_type: str
    hop_count: int
    confidence_score: float | None = None
    relevance_score: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Processing Queue スキーマ
class ProcessingQueueCreate(BaseModel):
    """処理キュー作成スキーマ."""
    paper_id: str = Field(..., min_length=1, max_length=255)
    task_type: str = Field(..., pattern=r'^(crawl|summarize|generate)$')
    priority: int = Field(default=0, ge=0)
    parameters: dict[str, Any] | None = None


class ProcessingQueueResponse(BaseModel):
    """処理キューレスポンススキーマ."""
    id: int
    paper_id: str
    task_type: str
    status: str
    priority: int
    retry_count: int
    max_retries: int
    error_message: str | None = None
    execution_time_seconds: float | None = None
    parameters: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# Keyword スキーマ
class PaperKeywordCreate(BaseModel):
    """キーワード作成スキーマ."""
    paper_id: str = Field(..., min_length=1, max_length=255)
    keyword: str = Field(..., min_length=1, max_length=200)
    relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    extraction_method: str | None = Field(None, max_length=100)
    model_name: str | None = Field(None, max_length=100)


class PaperKeywordResponse(BaseModel):
    """キーワードレスポンススキーマ."""
    id: int
    paper_id: str
    keyword: str
    relevance_score: float | None = None
    extraction_method: str | None = None
    model_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# External ID スキーマ
class PaperExternalIdCreate(BaseModel):
    """外部ID作成スキーマ."""
    paper_id: str = Field(..., min_length=1, max_length=255)
    id_type: str = Field(..., pattern=r'^(DOI|ArXiv|PubMed|PMCID|MAG|DBLP|ACL)$')
    external_id: str = Field(..., min_length=1, max_length=500)


class PaperExternalIdResponse(BaseModel):
    """外部IDレスポンススキーマ."""
    id: int
    paper_id: str
    id_type: str
    external_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 統計情報スキーマ
class DatabaseStats(BaseModel):
    """データベース統計スキーマ."""
    total_papers: int
    total_authors: int
    total_relations: int
    total_venues: int
    total_journals: int
    pending_queue_items: int
    database_health: dict[str, Any]


# 検索スキーマ
class PaperSearchParams(BaseModel):
    """論文検索パラメータ."""
    query: str | None = None
    author: str | None = None
    year_start: int | None = Field(None, ge=1900)
    year_end: int | None = Field(None, le=2100)
    venue_id: str | None = None
    journal_id: str | None = None
    field_of_study: str | None = None
    min_citation_count: int | None = Field(None, ge=0)
    has_pdf: bool | None = None
    has_summary: bool | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class PaperSearchResponse(BaseModel):
    """論文検索レスポンス."""
    papers: list[PaperResponse]
    total_count: int
    has_more: bool
    search_params: PaperSearchParams
