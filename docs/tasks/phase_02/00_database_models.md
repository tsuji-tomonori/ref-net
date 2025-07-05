# Task: データベースモデル定義

## タスクの目的

SQLAlchemyを使用してPostgreSQLデータベースのモデルを定義し、全コンポーネントが使用する共通データ構造を確立する。このタスクは Phase 3 全サービスの基盤となるデータアクセス層を提供する。

## 前提条件

- Phase 1 が完了している
- 共通ライブラリ（shared）が利用可能
- PostgreSQL 16+ がインストール済み
- 環境設定管理システムが動作

## 実施内容

### 1. SQLAlchemyモデルの作成

`package/shared/src/refnet_shared/models/database.py`:

```python
"""データベースモデル定義."""

from datetime import datetime
from typing import List, Optional, Any
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float,
    ForeignKey, Table, Index, UniqueConstraint, CheckConstraint,
    create_engine, MetaData
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid


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

Base = declarative_base(metadata=metadata)


# 多対多関係のためのアソシエーションテーブル
paper_authors = Table(
    'paper_authors',
    Base.metadata,
    Column('paper_id', String, ForeignKey('papers.paper_id'), primary_key=True),
    Column('author_id', String, ForeignKey('authors.author_id'), primary_key=True),
    Column('position', Integer, nullable=False),  # 著者の順番
    Column('created_at', DateTime, default=datetime.utcnow),
    Index('idx_paper_authors_paper_id', 'paper_id'),
    Index('idx_paper_authors_author_id', 'author_id'),
    Index('idx_paper_authors_position', 'paper_id', 'position'),
)


class Paper(Base):
    """論文モデル."""
    __tablename__ = 'papers'

    # 基本情報
    paper_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    year: Mapped[Optional[int]] = mapped_column(Integer)

    # 統計情報
    citation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reference_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    influence_score: Mapped[Optional[float]] = mapped_column(Float)  # 影響度スコア

    # 処理状態
    crawl_status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False)
    pdf_status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False)
    summary_status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False)

    # PDF情報
    pdf_url: Mapped[Optional[str]] = mapped_column(String(2048))
    pdf_hash: Mapped[Optional[str]] = mapped_column(String(64))  # SHA256
    pdf_size: Mapped[Optional[int]] = mapped_column(Integer)  # バイト数

    # AI生成コンテンツ
    summary: Mapped[Optional[str]] = mapped_column(Text)
    summary_model: Mapped[Optional[str]] = mapped_column(String(100))  # 使用したモデル
    summary_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # 出版情報
    venue_id: Mapped[Optional[str]] = mapped_column(String(255), ForeignKey('venues.venue_id'))
    journal_id: Mapped[Optional[str]] = mapped_column(String(255), ForeignKey('journals.journal_id'))

    # 言語・分野情報
    language: Mapped[Optional[str]] = mapped_column(String(10))  # ISO言語コード
    is_open_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 最後のクロール日時
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # リレーションシップ
    authors: Mapped[List["Author"]] = relationship(
        "Author",
        secondary=paper_authors,
        back_populates="papers",
        order_by="paper_authors.c.position"
    )
    venue: Mapped[Optional["Venue"]] = relationship("Venue", back_populates="papers")
    journal: Mapped[Optional["Journal"]] = relationship("Journal", back_populates="papers")

    # 引用関係
    cited_papers: Mapped[List["PaperRelation"]] = relationship(
        "PaperRelation",
        foreign_keys="PaperRelation.source_paper_id",
        back_populates="source_paper"
    )
    citing_papers: Mapped[List["PaperRelation"]] = relationship(
        "PaperRelation",
        foreign_keys="PaperRelation.target_paper_id",
        back_populates="target_paper"
    )

    # 外部ID
    external_ids: Mapped[List["PaperExternalId"]] = relationship("PaperExternalId", back_populates="paper", cascade="all, delete-orphan")

    # 研究分野
    fields_of_study: Mapped[List["PaperFieldOfStudy"]] = relationship("PaperFieldOfStudy", back_populates="paper", cascade="all, delete-orphan")

    # AI生成キーワード
    keywords: Mapped[List["PaperKeyword"]] = relationship("PaperKeyword", back_populates="paper", cascade="all, delete-orphan")

    # インデックス・制約
    __table_args__ = (
        Index('idx_papers_title_fts', 'title'),  # 全文検索用
        Index('idx_papers_year', 'year'),
        Index('idx_papers_citation_count', 'citation_count'),
        Index('idx_papers_crawl_status', 'crawl_status'),
        Index('idx_papers_pdf_status', 'pdf_status'),
        Index('idx_papers_summary_status', 'summary_status'),
        Index('idx_papers_created_at', 'created_at'),
        Index('idx_papers_updated_at', 'updated_at'),
        Index('idx_papers_last_crawled_at', 'last_crawled_at'),
        Index('idx_papers_venue_year', 'venue_id', 'year'),  # 複合インデックス
        Index('idx_papers_journal_year', 'journal_id', 'year'),  # 複合インデックス
        CheckConstraint('year >= 1900 AND year <= 2100', name='check_year_range'),
        CheckConstraint('citation_count >= 0', name='check_citation_count_positive'),
        CheckConstraint('reference_count >= 0', name='check_reference_count_positive'),
        CheckConstraint('pdf_size >= 0', name='check_pdf_size_positive'),
        CheckConstraint("crawl_status IN ('pending', 'running', 'completed', 'failed')", name='check_crawl_status'),
        CheckConstraint("pdf_status IN ('pending', 'running', 'completed', 'failed', 'unavailable')", name='check_pdf_status'),
        CheckConstraint("summary_status IN ('pending', 'running', 'completed', 'failed')", name='check_summary_status'),
    )


class Author(Base):
    """著者モデル."""
    __tablename__ = 'authors'

    author_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)

    # 統計情報
    paper_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    citation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    h_index: Mapped[Optional[int]] = mapped_column(Integer)

    # 所属情報
    affiliations: Mapped[Optional[str]] = mapped_column(Text)  # JSON形式で複数所属を保存

    # メタデータ
    homepage_url: Mapped[Optional[str]] = mapped_column(String(2048))
    orcid: Mapped[Optional[str]] = mapped_column(String(19))  # ORCID ID

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # リレーションシップ
    papers: Mapped[List["Paper"]] = relationship(
        "Paper",
        secondary=paper_authors,
        back_populates="authors"
    )

    # インデックス・制約
    __table_args__ = (
        Index('idx_authors_name', 'name'),
        Index('idx_authors_name_fts', 'name'),  # 全文検索用
        Index('idx_authors_paper_count', 'paper_count'),
        Index('idx_authors_citation_count', 'citation_count'),
        Index('idx_authors_h_index', 'h_index'),
        Index('idx_authors_orcid', 'orcid'),
        CheckConstraint('paper_count >= 0', name='check_paper_count_positive'),
        CheckConstraint('citation_count >= 0', name='check_citation_count_positive'),
        CheckConstraint('h_index >= 0', name='check_h_index_positive'),
    )


class PaperRelation(Base):
    """論文間の関係（引用・被引用）."""
    __tablename__ = 'paper_relations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_paper_id: Mapped[str] = mapped_column(String(255), ForeignKey('papers.paper_id'), nullable=False)
    target_paper_id: Mapped[str] = mapped_column(String(255), ForeignKey('papers.paper_id'), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'citation' or 'reference'
    hop_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 起点からの距離

    # 関係の信頼度・重要度
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)  # 関係の信頼度
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)  # 関係の関連度

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # リレーションシップ
    source_paper: Mapped["Paper"] = relationship(
        "Paper",
        foreign_keys=[source_paper_id],
        back_populates="cited_papers"
    )
    target_paper: Mapped["Paper"] = relationship(
        "Paper",
        foreign_keys=[target_paper_id],
        back_populates="citing_papers"
    )

    # インデックス・制約
    __table_args__ = (
        UniqueConstraint('source_paper_id', 'target_paper_id', 'relation_type', name='uq_paper_relation'),
        Index('idx_paper_relations_source', 'source_paper_id'),
        Index('idx_paper_relations_target', 'target_paper_id'),
        Index('idx_paper_relations_type', 'relation_type'),
        Index('idx_paper_relations_hop_count', 'hop_count'),
        Index('idx_paper_relations_source_hop', 'source_paper_id', 'hop_count'),  # 複合インデックス
        Index('idx_paper_relations_target_hop', 'target_paper_id', 'hop_count'),  # 複合インデックス
        CheckConstraint('hop_count >= 1', name='check_hop_count_positive'),
        CheckConstraint("relation_type IN ('citation', 'reference')", name='check_relation_type'),
        CheckConstraint('source_paper_id != target_paper_id', name='check_no_self_reference'),
    )


class Venue(Base):
    """会議・学会モデル."""
    __tablename__ = 'venues'

    venue_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(100))  # 略称
    type: Mapped[Optional[str]] = mapped_column(String(50))  # 'conference', 'workshop', etc.

    # 詳細情報
    description: Mapped[Optional[str]] = mapped_column(Text)
    homepage_url: Mapped[Optional[str]] = mapped_column(String(2048))

    # 品質指標
    rank: Mapped[Optional[str]] = mapped_column(String(10))  # A*, A, B, C等
    h_index: Mapped[Optional[int]] = mapped_column(Integer)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # リレーションシップ
    papers: Mapped[List["Paper"]] = relationship("Paper", back_populates="venue")

    # インデックス・制約
    __table_args__ = (
        Index('idx_venues_name', 'name'),
        Index('idx_venues_short_name', 'short_name'),
        Index('idx_venues_type', 'type'),
        Index('idx_venues_rank', 'rank'),
    )


class Journal(Base):
    """ジャーナルモデル."""
    __tablename__ = 'journals'

    journal_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)

    # 詳細情報
    issn: Mapped[Optional[str]] = mapped_column(String(20))
    publisher: Mapped[Optional[str]] = mapped_column(String(200))
    homepage_url: Mapped[Optional[str]] = mapped_column(String(2048))

    # 品質指標
    impact_factor: Mapped[Optional[float]] = mapped_column(Float)
    h_index: Mapped[Optional[int]] = mapped_column(Integer)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # リレーションシップ
    papers: Mapped[List["Paper"]] = relationship("Paper", back_populates="journal")

    # インデックス・制約
    __table_args__ = (
        Index('idx_journals_name', 'name'),
        Index('idx_journals_issn', 'issn'),
        Index('idx_journals_publisher', 'publisher'),
        Index('idx_journals_impact_factor', 'impact_factor'),
    )


class PaperExternalId(Base):
    """論文の外部識別子."""
    __tablename__ = 'paper_external_ids'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(255), ForeignKey('papers.paper_id'), nullable=False)
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'DOI', 'ArXiv', 'PubMed', etc.
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # リレーションシップ
    paper: Mapped["Paper"] = relationship("Paper", back_populates="external_ids")

    # インデックス・制約
    __table_args__ = (
        UniqueConstraint('paper_id', 'id_type', 'external_id', name='uq_paper_external_id'),
        Index('idx_paper_external_ids_paper_id', 'paper_id'),
        Index('idx_paper_external_ids_type', 'id_type'),
        Index('idx_paper_external_ids_external_id', 'external_id'),
        Index('idx_paper_external_ids_type_external', 'id_type', 'external_id'),  # 複合インデックス
        CheckConstraint("id_type IN ('DOI', 'ArXiv', 'PubMed', 'PMCID', 'MAG', 'DBLP', 'ACL')", name='check_id_type'),
    )


class PaperFieldOfStudy(Base):
    """論文の研究分野."""
    __tablename__ = 'paper_fields_of_study'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(255), ForeignKey('papers.paper_id'), nullable=False)
    field_name: Mapped[str] = mapped_column(String(200), nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)  # 分野分類の信頼度

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # リレーションシップ
    paper: Mapped["Paper"] = relationship("Paper", back_populates="fields_of_study")

    # インデックス・制約
    __table_args__ = (
        UniqueConstraint('paper_id', 'field_name', name='uq_paper_field_of_study'),
        Index('idx_paper_fields_of_study_paper_id', 'paper_id'),
        Index('idx_paper_fields_of_study_field_name', 'field_name'),
        Index('idx_paper_fields_of_study_confidence', 'confidence_score'),
    )


class PaperKeyword(Base):
    """AI生成キーワード."""
    __tablename__ = 'paper_keywords'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(255), ForeignKey('papers.paper_id'), nullable=False)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)

    # 生成元情報
    extraction_method: Mapped[Optional[str]] = mapped_column(String(100))  # 'llm', 'tfidf', 'manual'
    model_name: Mapped[Optional[str]] = mapped_column(String(100))  # 使用したモデル名

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # リレーションシップ
    paper: Mapped["Paper"] = relationship("Paper", back_populates="keywords")

    # インデックス・制約
    __table_args__ = (
        UniqueConstraint('paper_id', 'keyword', name='uq_paper_keyword'),
        Index('idx_paper_keywords_paper_id', 'paper_id'),
        Index('idx_paper_keywords_keyword', 'keyword'),
        Index('idx_paper_keywords_relevance_score', 'relevance_score'),
        Index('idx_paper_keywords_extraction_method', 'extraction_method'),
    )


class ProcessingQueue(Base):
    """処理キューモデル."""
    __tablename__ = 'processing_queue'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String(255), ForeignKey('papers.paper_id'), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'crawl', 'summarize', 'generate'
    status: Mapped[str] = mapped_column(String(50), default='pending', nullable=False)  # 'pending', 'running', 'completed', 'failed'
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # エラー・再試行情報
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # 実行時間情報
    execution_time_seconds: Mapped[Optional[float]] = mapped_column(Float)

    # 処理パラメータ（JSON形式）
    parameters: Mapped[Optional[dict]] = mapped_column(JSONB)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # インデックス・制約
    __table_args__ = (
        Index('idx_processing_queue_paper_id', 'paper_id'),
        Index('idx_processing_queue_task_type', 'task_type'),
        Index('idx_processing_queue_status', 'status'),
        Index('idx_processing_queue_priority', 'priority'),
        Index('idx_processing_queue_created_at', 'created_at'),
        Index('idx_processing_queue_status_priority', 'status', 'priority'),  # 複合インデックス
        Index('idx_processing_queue_task_status', 'task_type', 'status'),  # 複合インデックス
        CheckConstraint('priority >= 0', name='check_priority_positive'),
        CheckConstraint('retry_count >= 0', name='check_retry_count_positive'),
        CheckConstraint('max_retries >= 0', name='check_max_retries_positive'),
        CheckConstraint("task_type IN ('crawl', 'summarize', 'generate')", name='check_task_type'),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name='check_status'),
    )
```

### 2. データベース接続ヘルパー

`package/shared/src/refnet_shared/models/database_manager.py`:

```python
"""データベース接続管理."""

from contextlib import contextmanager
from typing import Generator, Optional, Dict, Any
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool
from refnet_shared.config import settings
from refnet_shared.models.database import Base
from refnet_shared.exceptions import DatabaseError
from refnet_shared.utils import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """データベース接続管理クラス."""

    def __init__(self, database_url: Optional[str] = None):
        """初期化."""
        self.database_url = database_url or settings.database.url

        # SQLAlchemy エンジン設定
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.debug,  # デバッグ時にSQLログを出力
        )

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def create_tables(self) -> None:
        """テーブル作成."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error("Failed to create database tables", error=str(e))
            raise DatabaseError(f"Failed to create tables: {str(e)}") from e

    def drop_tables(self) -> None:
        """テーブル削除."""
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error("Failed to drop database tables", error=str(e))
            raise DatabaseError(f"Failed to drop tables: {str(e)}") from e

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """セッション取得."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Database session error", error=str(e))
            raise DatabaseError(f"Database operation failed: {str(e)}") from e
        finally:
            session.close()

    def health_check(self) -> Dict[str, Any]:
        """データベースヘルスチェック."""
        try:
            with self.get_session() as session:
                result = session.execute(text("SELECT 1")).scalar()
                if result == 1:
                    return {
                        "status": "healthy",
                        "database_url": self.database_url.split('@')[1] if '@' in self.database_url else "unknown",
                        "engine_pool_size": self.engine.pool.size(),
                        "engine_pool_checked_in": self.engine.pool.checkedin(),
                        "engine_pool_checked_out": self.engine.pool.checkedout(),
                    }
                else:
                    return {"status": "unhealthy", "error": "Unexpected result from health check"}
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return {"status": "unhealthy", "error": str(e)}

    def get_table_stats(self) -> Dict[str, int]:
        """テーブル統計情報取得."""
        stats = {}
        try:
            with self.get_session() as session:
                # 各テーブルの行数を取得
                for table_name in Base.metadata.tables.keys():
                    try:
                        count = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                        stats[table_name] = count
                    except Exception as e:
                        logger.warning(f"Failed to get count for table {table_name}", error=str(e))
                        stats[table_name] = -1
        except Exception as e:
            logger.error("Failed to get table statistics", error=str(e))
            raise DatabaseError(f"Failed to get table stats: {str(e)}") from e

        return stats

    def vacuum_analyze(self) -> None:
        """データベースのVACUUM ANALYZE実行（PostgreSQL用）."""
        try:
            # autocommit=Trueでセッションを作成（VACUUM用）
            with self.engine.connect() as connection:
                connection.execute(text("VACUUM ANALYZE"))
            logger.info("Database VACUUM ANALYZE completed")
        except Exception as e:
            logger.error("VACUUM ANALYZE failed", error=str(e))
            raise DatabaseError(f"VACUUM ANALYZE failed: {str(e)}") from e

    def close(self) -> None:
        """データベース接続を閉じる."""
        try:
            self.engine.dispose()
            logger.info("Database connections closed")
        except Exception as e:
            logger.error("Failed to close database connections", error=str(e))


# グローバルインスタンス
db_manager = DatabaseManager()
```

### 3. Pydanticスキーマ定義

`package/shared/src/refnet_shared/models/schemas.py`:

```python
"""Pydanticスキーマ定義."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# Paper スキーマ
class PaperBase(BaseModel):
    """論文基底スキーマ."""
    title: str = Field(..., min_length=1, max_length=2000)
    abstract: Optional[str] = Field(None, max_length=10000)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    citation_count: int = Field(default=0, ge=0)
    reference_count: int = Field(default=0, ge=0)
    language: Optional[str] = Field(None, max_length=10)
    is_open_access: bool = Field(default=False)


class PaperCreate(PaperBase):
    """論文作成スキーマ."""
    paper_id: str = Field(..., min_length=1, max_length=255)


class PaperUpdate(BaseModel):
    """論文更新スキーマ."""
    title: Optional[str] = Field(None, min_length=1, max_length=2000)
    abstract: Optional[str] = Field(None, max_length=10000)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    citation_count: Optional[int] = Field(None, ge=0)
    reference_count: Optional[int] = Field(None, ge=0)
    summary: Optional[str] = Field(None, max_length=50000)
    pdf_url: Optional[str] = Field(None, max_length=2048)
    pdf_hash: Optional[str] = Field(None, max_length=64)
    crawl_status: Optional[str] = Field(None, pattern=r'^(pending|running|completed|failed)$')
    pdf_status: Optional[str] = Field(None, pattern=r'^(pending|running|completed|failed|unavailable)$')
    summary_status: Optional[str] = Field(None, pattern=r'^(pending|running|completed|failed)$')


class PaperResponse(PaperBase):
    """論文レスポンススキーマ."""
    paper_id: str
    crawl_status: str
    pdf_status: str
    summary_status: str
    summary: Optional[str] = None
    pdf_url: Optional[str] = None
    venue_id: Optional[str] = None
    journal_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Author スキーマ
class AuthorBase(BaseModel):
    """著者基底スキーマ."""
    name: str = Field(..., min_length=1, max_length=500)
    affiliations: Optional[str] = Field(None, max_length=2000)
    homepage_url: Optional[str] = Field(None, max_length=2048)
    orcid: Optional[str] = Field(None, max_length=19, pattern=r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$')


class AuthorCreate(AuthorBase):
    """著者作成スキーマ."""
    author_id: str = Field(..., min_length=1, max_length=255)


class AuthorResponse(AuthorBase):
    """著者レスポンススキーマ."""
    author_id: str
    paper_count: int
    citation_count: int
    h_index: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# Relation スキーマ
class PaperRelationCreate(BaseModel):
    """論文関係作成スキーマ."""
    source_paper_id: str = Field(..., min_length=1, max_length=255)
    target_paper_id: str = Field(..., min_length=1, max_length=255)
    relation_type: str = Field(..., pattern=r'^(citation|reference)$')
    hop_count: int = Field(default=1, ge=1)
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class PaperRelationResponse(BaseModel):
    """論文関係レスポンススキーマ."""
    id: int
    source_paper_id: str
    target_paper_id: str
    relation_type: str
    hop_count: int
    confidence_score: Optional[float] = None
    relevance_score: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Processing Queue スキーマ
class ProcessingQueueCreate(BaseModel):
    """処理キュー作成スキーマ."""
    paper_id: str = Field(..., min_length=1, max_length=255)
    task_type: str = Field(..., pattern=r'^(crawl|summarize|generate)$')
    priority: int = Field(default=0, ge=0)
    parameters: Optional[Dict[str, Any]] = None


class ProcessingQueueResponse(BaseModel):
    """処理キューレスポンススキーマ."""
    id: int
    paper_id: str
    task_type: str
    status: str
    priority: int
    retry_count: int
    max_retries: int
    error_message: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    parameters: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Keyword スキーマ
class PaperKeywordCreate(BaseModel):
    """キーワード作成スキーマ."""
    paper_id: str = Field(..., min_length=1, max_length=255)
    keyword: str = Field(..., min_length=1, max_length=200)
    relevance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    extraction_method: Optional[str] = Field(None, max_length=100)
    model_name: Optional[str] = Field(None, max_length=100)


class PaperKeywordResponse(BaseModel):
    """キーワードレスポンススキーマ."""
    id: int
    paper_id: str
    keyword: str
    relevance_score: Optional[float] = None
    extraction_method: Optional[str] = None
    model_name: Optional[str] = None
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
    database_health: Dict[str, Any]


# 検索スキーマ
class PaperSearchParams(BaseModel):
    """論文検索パラメータ."""
    query: Optional[str] = None
    author: Optional[str] = None
    year_start: Optional[int] = Field(None, ge=1900)
    year_end: Optional[int] = Field(None, le=2100)
    venue_id: Optional[str] = None
    journal_id: Optional[str] = None
    field_of_study: Optional[str] = None
    min_citation_count: Optional[int] = Field(None, ge=0)
    has_pdf: Optional[bool] = None
    has_summary: Optional[bool] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class PaperSearchResponse(BaseModel):
    """論文検索レスポンス."""
    papers: List[PaperResponse]
    total_count: int
    has_more: bool
    search_params: PaperSearchParams
```

### 4. テストの作成

`tests/test_models.py`:

```python
"""データベースモデルのテスト."""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from refnet_shared.models.database import Base, Paper, Author, PaperRelation, paper_authors
from refnet_shared.models.database_manager import DatabaseManager
from refnet_shared.models.schemas import PaperCreate, PaperUpdate


@pytest.fixture
def db_manager():
    """テスト用データベース接続."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    manager = DatabaseManager("sqlite:///:memory:")
    manager.engine = engine
    manager.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return manager


def test_paper_creation(db_manager):
    """論文作成テスト."""
    with db_manager.get_session() as session:
        paper = Paper(
            paper_id="test-paper-1",
            title="Test Paper",
            abstract="Test abstract",
            year=2023,
            citation_count=10
        )
        session.add(paper)
        session.commit()

        # 取得テスト
        retrieved_paper = session.query(Paper).filter_by(paper_id="test-paper-1").first()
        assert retrieved_paper is not None
        assert retrieved_paper.title == "Test Paper"
        assert retrieved_paper.citation_count == 10


def test_author_paper_relationship(db_manager):
    """著者と論文の関係テスト."""
    with db_manager.get_session() as session:
        # 論文作成
        paper = Paper(
            paper_id="test-paper-1",
            title="Test Paper",
            year=2023
        )

        # 著者作成
        author = Author(
            author_id="test-author-1",
            name="Test Author"
        )

        # 関係設定
        paper.authors.append(author)

        session.add(paper)
        session.add(author)
        session.commit()

        # 関係確認
        retrieved_paper = session.query(Paper).filter_by(paper_id="test-paper-1").first()
        assert len(retrieved_paper.authors) == 1
        assert retrieved_paper.authors[0].name == "Test Author"


def test_paper_relation_creation(db_manager):
    """論文関係作成テスト."""
    with db_manager.get_session() as session:
        # 論文作成
        paper1 = Paper(paper_id="paper-1", title="Paper 1", year=2023)
        paper2 = Paper(paper_id="paper-2", title="Paper 2", year=2023)

        # 関係作成
        relation = PaperRelation(
            source_paper_id="paper-1",
            target_paper_id="paper-2",
            relation_type="citation",
            hop_count=1
        )

        session.add(paper1)
        session.add(paper2)
        session.add(relation)
        session.commit()

        # 関係確認
        retrieved_relation = session.query(PaperRelation).first()
        assert retrieved_relation.source_paper_id == "paper-1"
        assert retrieved_relation.target_paper_id == "paper-2"
        assert retrieved_relation.relation_type == "citation"


def test_database_manager_health_check(db_manager):
    """データベースマネージャーヘルスチェックテスト."""
    health = db_manager.health_check()
    assert health["status"] == "healthy"


def test_table_stats(db_manager):
    """テーブル統計テスト."""
    with db_manager.get_session() as session:
        # テストデータ追加
        paper = Paper(paper_id="test-paper", title="Test", year=2023)
        session.add(paper)
        session.commit()

    stats = db_manager.get_table_stats()
    assert "papers" in stats
    assert stats["papers"] >= 1


def test_paper_schema_validation():
    """論文スキーマ検証テスト."""
    # 正常なデータ
    valid_data = PaperCreate(
        paper_id="test-paper",
        title="Test Paper",
        abstract="Test abstract",
        year=2023,
        citation_count=10
    )
    assert valid_data.paper_id == "test-paper"

    # 異常なデータ
    with pytest.raises(ValueError):
        PaperCreate(
            paper_id="test-paper",
            title="",  # 空タイトル
            year=2023
        )


def test_paper_update_schema():
    """論文更新スキーマテスト."""
    update_data = PaperUpdate(
        title="Updated Title",
        citation_count=20
    )
    assert update_data.title == "Updated Title"
    assert update_data.citation_count == 20
    assert update_data.abstract is None  # 設定されていない項目
```

## スコープ

- SQLAlchemyモデル定義（全テーブル）
- データベース接続管理クラス
- Pydanticスキーマ定義（全モデル）
- インデックス・制約の最適化
- 基本的なテストケース作成
- パフォーマンス考慮事項の実装

**スコープ外:**
- Alembicマイグレーション（次タスクで実施）
- 複雑なクエリ関数
- データ分析用ビュー
- 本番運用時のチューニング

## 参照するドキュメント

- `/docs/database/schema.md`
- `/docs/database/erd.md`
- `/docs/development/coding-standards.md`

## 完了条件

### 必須条件
- [ ] 全テーブルのSQLAlchemyモデルが定義されている
- [ ] Pydanticスキーマが全モデルに対して定義されている
- [ ] データベース接続管理クラスが実装されている
- [ ] 適切なインデックスが設定されている
- [ ] 制約が適切に設定されている

### パフォーマンス条件
- [ ] 複合インデックスが適切に配置されている
- [ ] 外部キー制約が設定されている
- [ ] CHECK制約でデータ整合性が保証されている

### テスト条件
- [ ] 基本的なテストケースが作成されている
- [ ] モデル間の関係テストが作成されている
- [ ] スキーマ検証テストが作成されている
- [ ] `cd package/shared && moon run shared:check` が正常終了する
- [ ] テストカバレッジが80%以上である

## 次のタスクへの引き継ぎ

### 01_database_migrations.md への前提条件
- 全データベースモデルが定義済み
- テーブル間の関係が確立済み
- データベース接続管理が動作済み

### Phase 3 への前提条件
- 共通データアクセス層が利用可能
- 全サービスがモデルをインポート可能
- データベーススキーマが確定済み

### 引き継ぎファイル
- `package/shared/src/refnet_shared/models/database.py` - データモデル
- `package/shared/src/refnet_shared/models/database_manager.py` - DB管理
- `package/shared/src/refnet_shared/models/schemas.py` - Pydanticスキーマ
