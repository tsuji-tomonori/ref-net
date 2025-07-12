"""データベースモデル定義."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# メタデータとベースクラス
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    """SQLAlchemyベースクラス."""

    metadata = metadata


# Cross-database JSON type
def get_json_type() -> type:
    """データベースに応じたJSON型を返す.

    PostgreSQLの場合はJSONB、その他（SQLite等）の場合はJSONを使用。
    環境変数DATABASE_URLから判定する。
    """
    import os

    from sqlalchemy.dialects.postgresql import JSONB

    database_url = os.environ.get("DATABASE_URL", "")

    # PostgreSQLの場合はJSONBを使用
    if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        return JSONB

    # その他のデータベース（SQLite等）の場合はJSONを使用
    return JSON


# 多対多関係のためのアソシエーションテーブル
paper_authors = Table(
    "paper_authors",
    Base.metadata,
    Column("paper_id", String, ForeignKey("papers.paper_id"), primary_key=True),
    Column("author_id", String, ForeignKey("authors.author_id"), primary_key=True),
    Column("position", Integer, nullable=False),  # 著者の順番
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc)),
    Index("idx_paper_authors_paper_id", "paper_id"),
    Index("idx_paper_authors_author_id", "author_id"),
    Index("idx_paper_authors_position", "paper_id", "position"),
)


class Paper(Base):
    """論文モデル."""

    __tablename__ = "papers"

    # 基本情報
    paper_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)

    # 統計情報
    citation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reference_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    influence_score: Mapped[float | None] = mapped_column(Float)  # 影響度スコア

    # 処理状態 - 単純なboolフラグに変更
    is_crawled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_summarized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 追加フィールド
    crawl_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # クロールの深さ
    markdown_path: Mapped[str | None] = mapped_column(String(2048))  # 生成されたMarkdownのパス
    error_message: Mapped[str | None] = mapped_column(Text)  # エラーメッセージ
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # リトライ回数

    # 論文のURL
    url: Mapped[str | None] = mapped_column(String(2048))  # 論文のURL

    # 全文テキスト
    full_text: Mapped[str | None] = mapped_column(Text)  # PDFから抽出した全文

    # PDF情報
    pdf_url: Mapped[str | None] = mapped_column(String(2048))
    pdf_hash: Mapped[str | None] = mapped_column(String(64))  # SHA256
    pdf_size: Mapped[int | None] = mapped_column(Integer)  # バイト数

    # AI生成コンテンツ
    summary: Mapped[str | None] = mapped_column(Text)
    summary_model: Mapped[str | None] = mapped_column(String(100))  # 使用したモデル
    summary_created_at: Mapped[datetime | None] = mapped_column(DateTime)

    # 出版情報
    venue_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("venues.venue_id"))
    journal_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("journals.journal_id"))

    # 言語・分野情報
    language: Mapped[str | None] = mapped_column(String(10))  # ISO言語コード
    is_open_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # 最後のクロール日時
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime)

    # リレーションシップ
    authors: Mapped[list["Author"]] = relationship("Author", secondary=paper_authors, back_populates="papers", order_by="paper_authors.c.position")
    venue: Mapped[Optional["Venue"]] = relationship("Venue", back_populates="papers")
    journal: Mapped[Optional["Journal"]] = relationship("Journal", back_populates="papers")

    # 引用関係
    cited_papers: Mapped[list["PaperRelation"]] = relationship(
        "PaperRelation", foreign_keys="PaperRelation.source_paper_id", back_populates="source_paper"
    )
    citing_papers: Mapped[list["PaperRelation"]] = relationship(
        "PaperRelation", foreign_keys="PaperRelation.target_paper_id", back_populates="target_paper"
    )

    # 外部ID
    external_ids: Mapped[list["PaperExternalId"]] = relationship("PaperExternalId", back_populates="paper", cascade="all, delete-orphan")

    # 研究分野
    fields_of_study: Mapped[list["PaperFieldOfStudy"]] = relationship("PaperFieldOfStudy", back_populates="paper", cascade="all, delete-orphan")

    # AI生成キーワード
    keywords: Mapped[list["PaperKeyword"]] = relationship("PaperKeyword", back_populates="paper", cascade="all, delete-orphan")

    # インデックス・制約
    __table_args__ = (
        Index("idx_papers_title_fts", "title"),  # 全文検索用
        Index("idx_papers_year", "year"),
        Index("idx_papers_citation_count", "citation_count"),
        Index("idx_papers_is_crawled", "is_crawled"),
        Index("idx_papers_is_summarized", "is_summarized"),
        Index("idx_papers_is_generated", "is_generated"),
        Index("idx_papers_crawl_depth", "crawl_depth"),
        Index("idx_papers_markdown_path", "markdown_path"),
        Index("idx_papers_retry_count", "retry_count"),
        Index("idx_papers_created_at", "created_at"),
        Index("idx_papers_updated_at", "updated_at"),
        Index("idx_papers_last_crawled_at", "last_crawled_at"),
        Index("idx_papers_venue_year", "venue_id", "year"),  # 複合インデックス
        Index("idx_papers_journal_year", "journal_id", "year"),  # 複合インデックス
        CheckConstraint("year >= 1900 AND year <= 2100", name="check_year_range"),
        CheckConstraint("citation_count >= 0", name="check_citation_count_positive"),
        CheckConstraint("reference_count >= 0", name="check_reference_count_positive"),
        CheckConstraint("pdf_size >= 0", name="check_pdf_size_positive"),
        CheckConstraint("crawl_depth >= 0", name="check_crawl_depth_positive"),
        CheckConstraint("retry_count >= 0", name="check_retry_count_positive"),
    )


class Author(Base):
    """著者モデル."""

    __tablename__ = "authors"

    author_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)

    # 統計情報
    paper_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    citation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    h_index: Mapped[int | None] = mapped_column(Integer)

    # 所属情報
    affiliations: Mapped[str | None] = mapped_column(Text)  # JSON形式で複数所属を保存

    # メタデータ
    homepage_url: Mapped[str | None] = mapped_column(String(2048))
    orcid: Mapped[str | None] = mapped_column(String(19))  # ORCID ID

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # リレーションシップ
    papers: Mapped[list["Paper"]] = relationship("Paper", secondary=paper_authors, back_populates="authors")

    # インデックス・制約
    __table_args__ = (
        Index("idx_authors_name", "name"),
        Index("idx_authors_name_fts", "name"),  # 全文検索用
        Index("idx_authors_paper_count", "paper_count"),
        Index("idx_authors_citation_count", "citation_count"),
        Index("idx_authors_h_index", "h_index"),
        Index("idx_authors_orcid", "orcid"),
        CheckConstraint("paper_count >= 0", name="check_paper_count_positive"),
        CheckConstraint("citation_count >= 0", name="check_citation_count_positive"),
        CheckConstraint("h_index >= 0", name="check_h_index_positive"),
    )


class PaperRelation(Base):
    """論文間の関係（引用・被引用）."""

    __tablename__ = "paper_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_paper_id: Mapped[str] = mapped_column(String(255), ForeignKey("papers.paper_id"), nullable=False)
    target_paper_id: Mapped[str] = mapped_column(String(255), ForeignKey("papers.paper_id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'citation' or 'reference'
    hop_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 起点からの距離

    # 関係の信頼度・重要度
    confidence_score: Mapped[float | None] = mapped_column(Float)  # 関係の信頼度
    relevance_score: Mapped[float | None] = mapped_column(Float)  # 関係の関連度

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # リレーションシップ
    source_paper: Mapped["Paper"] = relationship("Paper", foreign_keys=[source_paper_id], back_populates="cited_papers")
    target_paper: Mapped["Paper"] = relationship("Paper", foreign_keys=[target_paper_id], back_populates="citing_papers")

    # インデックス・制約
    __table_args__ = (
        UniqueConstraint("source_paper_id", "target_paper_id", "relation_type", name="uq_paper_relation"),
        Index("idx_paper_relations_source", "source_paper_id"),
        Index("idx_paper_relations_target", "target_paper_id"),
        Index("idx_paper_relations_type", "relation_type"),
        Index("idx_paper_relations_hop_count", "hop_count"),
        Index("idx_paper_relations_source_hop", "source_paper_id", "hop_count"),  # 複合インデックス
        Index("idx_paper_relations_target_hop", "target_paper_id", "hop_count"),  # 複合インデックス
        CheckConstraint("hop_count >= 1", name="check_hop_count_positive"),
        CheckConstraint("relation_type IN ('citation', 'reference')", name="check_relation_type"),
        CheckConstraint("source_paper_id != target_paper_id", name="check_no_self_reference"),
    )


class Venue(Base):
    """会議・学会モデル."""

    __tablename__ = "venues"

    venue_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100))  # 略称
    type: Mapped[str | None] = mapped_column(String(50))  # 'conference', 'workshop', etc.

    # 詳細情報
    description: Mapped[str | None] = mapped_column(Text)
    homepage_url: Mapped[str | None] = mapped_column(String(2048))

    # 品質指標
    rank: Mapped[str | None] = mapped_column(String(10))  # A*, A, B, C等
    h_index: Mapped[int | None] = mapped_column(Integer)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # リレーションシップ
    papers: Mapped[list["Paper"]] = relationship("Paper", back_populates="venue")

    # インデックス・制約
    __table_args__ = (
        Index("idx_venues_name", "name"),
        Index("idx_venues_short_name", "short_name"),
        Index("idx_venues_type", "type"),
        Index("idx_venues_rank", "rank"),
    )


class Journal(Base):
    """ジャーナルモデル."""

    __tablename__ = "journals"

    journal_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)

    # 詳細情報
    issn: Mapped[str | None] = mapped_column(String(20))
    publisher: Mapped[str | None] = mapped_column(String(200))
    homepage_url: Mapped[str | None] = mapped_column(String(2048))

    # 品質指標
    impact_factor: Mapped[float | None] = mapped_column(Float)
    h_index: Mapped[int | None] = mapped_column(Integer)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # リレーションシップ
    papers: Mapped[list["Paper"]] = relationship("Paper", back_populates="journal")

    # インデックス・制約
    __table_args__ = (
        Index("idx_journals_name", "name"),
        Index("idx_journals_issn", "issn"),
        Index("idx_journals_publisher", "publisher"),
        Index("idx_journals_impact_factor", "impact_factor"),
    )


class PaperExternalId(Base):
    """論文の外部識別子."""

    __tablename__ = "paper_external_ids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(255), ForeignKey("papers.paper_id"), nullable=False)
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'DOI', 'ArXiv', 'PubMed', etc.
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # リレーションシップ
    paper: Mapped["Paper"] = relationship("Paper", back_populates="external_ids")

    # インデックス・制約
    __table_args__ = (
        UniqueConstraint("paper_id", "id_type", "external_id", name="uq_paper_external_id"),
        Index("idx_paper_external_ids_paper_id", "paper_id"),
        Index("idx_paper_external_ids_type", "id_type"),
        Index("idx_paper_external_ids_external_id", "external_id"),
        Index("idx_paper_external_ids_type_external", "id_type", "external_id"),  # 複合インデックス
        CheckConstraint("id_type IN ('DOI', 'ArXiv', 'PubMed', 'PMCID', 'MAG', 'DBLP', 'ACL')", name="check_id_type"),
    )


class PaperFieldOfStudy(Base):
    """論文の研究分野."""

    __tablename__ = "paper_fields_of_study"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(255), ForeignKey("papers.paper_id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(200), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)  # 分野分類の信頼度

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # リレーションシップ
    paper: Mapped["Paper"] = relationship("Paper", back_populates="fields_of_study")

    # インデックス・制約
    __table_args__ = (
        UniqueConstraint("paper_id", "field_name", name="uq_paper_field_of_study"),
        Index("idx_paper_fields_of_study_paper_id", "paper_id"),
        Index("idx_paper_fields_of_study_field_name", "field_name"),
        Index("idx_paper_fields_of_study_confidence", "confidence_score"),
    )


class PaperKeyword(Base):
    """AI生成キーワード."""

    __tablename__ = "paper_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(255), ForeignKey("papers.paper_id"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    relevance_score: Mapped[float | None] = mapped_column(Float)

    # 生成元情報
    extraction_method: Mapped[str | None] = mapped_column(String(100))  # 'llm', 'tfidf', 'manual'
    model_name: Mapped[str | None] = mapped_column(String(100))  # 使用したモデル名

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # リレーションシップ
    paper: Mapped["Paper"] = relationship("Paper", back_populates="keywords")

    # インデックス・制約
    __table_args__ = (
        UniqueConstraint("paper_id", "keyword", name="uq_paper_keyword"),
        Index("idx_paper_keywords_paper_id", "paper_id"),
        Index("idx_paper_keywords_keyword", "keyword"),
        Index("idx_paper_keywords_relevance_score", "relevance_score"),
        Index("idx_paper_keywords_extraction_method", "extraction_method"),
    )


class ProcessingQueue(Base):
    """処理キューモデル."""

    __tablename__ = "processing_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(255), ForeignKey("papers.paper_id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'crawl', 'summarize', 'generate'
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # 'pending', 'running', 'completed', 'failed'
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # エラー・再試行情報
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # 実行時間情報
    execution_time_seconds: Mapped[float | None] = mapped_column(Float)

    # 処理パラメータ（JSON形式）
    parameters: Mapped[dict | None] = mapped_column(get_json_type())

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # インデックス・制約
    __table_args__ = (
        Index("idx_processing_queue_paper_id", "paper_id"),
        Index("idx_processing_queue_task_type", "task_type"),
        Index("idx_processing_queue_status", "status"),
        Index("idx_processing_queue_priority", "priority"),
        Index("idx_processing_queue_created_at", "created_at"),
        Index("idx_processing_queue_status_priority", "status", "priority"),  # 複合インデックス
        Index("idx_processing_queue_task_status", "task_type", "status"),  # 複合インデックス
        CheckConstraint("priority >= 0", name="check_priority_positive"),
        CheckConstraint("retry_count >= 0", name="check_retry_count_positive"),
        CheckConstraint("max_retries >= 0", name="check_max_retries_positive"),
        CheckConstraint("task_type IN ('crawl', 'summarize', 'generate')", name="check_task_type"),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name="check_status"),
    )
