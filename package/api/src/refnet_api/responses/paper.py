"""論文関連レスポンスモデル."""

from typing import Any

from refnet_shared.models.schemas import PaperResponse as SharedPaperResponse

from .base import BaseResponse


class PaperResponse(SharedPaperResponse):
    """論文レスポンス."""
    pass


class PaperListResponse(BaseResponse):
    """論文一覧レスポンス."""

    papers: list[PaperResponse]
    total: int
    page: int
    per_page: int


class PaperCreateResponse(BaseResponse):
    """論文作成レスポンス."""

    paper_id: str
    message: str


class PaperStatusResponse(BaseResponse):
    """論文ステータスレスポンス."""

    paper_id: str
    crawl_status: str
    pdf_status: str
    summary_status: str


class PaperRelationsResponse(BaseResponse):
    """論文関係性レスポンス."""

    paper_id: str
    references: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    related_papers: list[dict[str, Any]]
