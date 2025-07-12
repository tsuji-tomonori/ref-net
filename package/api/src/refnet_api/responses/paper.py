"""論文関連レスポンスモデル."""

from refnet_shared.models.schemas import (
    PaperRelationResponse,
)
from refnet_shared.models.schemas import (
    PaperResponse as SharedPaperResponse,
)

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
    is_crawled: bool
    is_summarized: bool
    is_generated: bool


class PaperRelationsResponse(BaseResponse):
    """論文関係性レスポンス."""

    paper_id: str
    references: list[PaperRelationResponse]
    citations: list[PaperRelationResponse]
    related_papers: list[PaperRelationResponse]
