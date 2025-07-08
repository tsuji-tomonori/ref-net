"""著者関連レスポンスモデル."""

from typing import Any

from refnet_shared.models.schemas import AuthorResponse as SharedAuthorResponse

from .base import BaseResponse


class AuthorResponse(SharedAuthorResponse):
    """著者レスポンス."""
    pass


class AuthorListResponse(BaseResponse):
    """著者一覧レスポンス."""

    authors: list[AuthorResponse]
    total: int
    page: int
    per_page: int


class AuthorPapersResponse(BaseResponse):
    """著者の論文一覧レスポンス."""

    author_id: str
    papers: list[dict[str, Any]]
    total: int
