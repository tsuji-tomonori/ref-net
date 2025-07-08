"""Semantic Scholar APIレスポンス用データモデル."""

from typing import Any

from pydantic import BaseModel


class SemanticScholarAuthor(BaseModel):
    """Semantic Scholar著者モデル."""

    authorId: str | None = None
    name: str | None = None


class SemanticScholarVenue(BaseModel):
    """Semantic Scholar会場モデル."""

    id: str | None = None
    name: str | None = None
    type: str | None = None
    alternate_names: list[str] | None = None
    issn: str | None = None
    url: str | None = None


class SemanticScholarJournal(BaseModel):
    """Semantic Scholarジャーナルモデル."""

    name: str | None = None
    pages: str | None = None
    volume: str | None = None


class SemanticScholarPaper(BaseModel):
    """Semantic Scholar論文モデル."""

    paperId: str
    title: str | None = None
    abstract: str | None = None
    year: int | None = None
    citationCount: int | None = None
    referenceCount: int | None = None
    authors: list[SemanticScholarAuthor] | None = None
    venue: SemanticScholarVenue | None = None
    journal: SemanticScholarJournal | None = None
    externalIds: dict[str, str] | None = None
    fieldsOfStudy: list[str] | None = None
    url: str | None = None

    def to_paper_create_dict(self) -> dict[str, Any]:
        """データベース作成用辞書に変換."""
        return {
            "paper_id": self.paperId,
            "title": self.title or "",
            "abstract": self.abstract,
            "year": self.year,
            "citation_count": self.citationCount or 0,
            "reference_count": self.referenceCount or 0,
        }
