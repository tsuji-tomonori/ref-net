# Task: データベースモデル定義

## タスクの目的

SQLAlchemyを使用してPostgreSQLデータベースのモデルを定義し、全コンポーネントが使用する共通データ構造を確立する。

## 実施内容

### 1. SQLAlchemyモデルの作成

`package/shared/src/refnet_shared/models/database.py`:

```python
"""データベースモデル定義."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float,
    ForeignKey, Table, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid


Base = declarative_base()


# 多対多関係のためのアソシエーションテーブル
paper_authors = Table(
    'paper_authors',
    Base.metadata,
    Column('paper_id', String, ForeignKey('papers.paper_id'), primary_key=True),
    Column('author_id', String, ForeignKey('authors.author_id'), primary_key=True),
    Column('position', Integer, nullable=False),  # 著者の順番
    Index('idx_paper_authors_paper_id', 'paper_id'),
    Index('idx_paper_authors_author_id', 'author_id'),
)


class Paper(Base):
    """論文モデル."""
    __tablename__ = 'papers'

    paper_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    year: Mapped[Optional[int]] = mapped_column(Integer)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    reference_count: Mapped[int] = mapped_column(Integer, default=0)

    # 処理状態
    crawl_status: Mapped[str] = mapped_column(String, default='pending')
    pdf_status: Mapped[str] = mapped_column(String, default='pending')
    summary_status: Mapped[str] = mapped_column(String, default='pending')

    # PDF情報
    pdf_url: Mapped[Optional[str]] = mapped_column(String)
    pdf_hash: Mapped[Optional[str]] = mapped_column(String)

    # AI生成コンテンツ
    summary: Mapped[Optional[str]] = mapped_column(Text)

    # 出版情報
    venue_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey('venues.venue_id'))
    journal_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey('journals.journal_id'))

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    external_ids: Mapped[List["PaperExternalId"]] = relationship("PaperExternalId", back_populates="paper")

    # 研究分野
    fields_of_study: Mapped[List["PaperFieldOfStudy"]] = relationship("PaperFieldOfStudy", back_populates="paper")

    # AI生成キーワード
    keywords: Mapped[List["PaperKeyword"]] = relationship("PaperKeyword", back_populates="paper")

    # インデックス
    __table_args__ = (
        Index('idx_papers_title', 'title'),
        Index('idx_papers_year', 'year'),
        Index('idx_papers_citation_count', 'citation_count'),
        Index('idx_papers_crawl_status', 'crawl_status'),
        Index('idx_papers_pdf_status', 'pdf_status'),
        Index('idx_papers_summary_status', 'summary_status'),
        CheckConstraint('year >= 1900 AND year <= 2100', name='check_year_range'),
        CheckConstraint('citation_count >= 0', name='check_citation_count_positive'),
    )


class Author(Base):
    """著者モデル."""
    __tablename__ = 'authors'

    author_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

    # 統計情報
    paper_count: Mapped[int] = mapped_column(Integer, default=0)
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    h_index: Mapped[Optional[int]] = mapped_column(Integer)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーションシップ
    papers: Mapped[List["Paper"]] = relationship(
        "Paper",
        secondary=paper_authors,
        back_populates="authors"
    )

    # インデックス
    __table_args__ = (
        Index('idx_authors_name', 'name'),
        Index('idx_authors_paper_count', 'paper_count'),
        Index('idx_authors_citation_count', 'citation_count'),
    )


class PaperRelation(Base):
    """論文間の関係（引用・被引用）."""
    __tablename__ = 'paper_relations'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_paper_id: Mapped[str] = mapped_column(String, ForeignKey('papers.paper_id'), nullable=False)
    target_paper_id: Mapped[str] = mapped_column(String, ForeignKey('papers.paper_id'), nullable=False)
    relation_type: Mapped[str] = mapped_column(String, nullable=False)  # 'citation' or 'reference'
    hop_count: Mapped[int] = mapped_column(Integer, default=1)  # 起点からの距離

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

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

    # インデックス
    __table_args__ = (
        UniqueConstraint('source_paper_id', 'target_paper_id', 'relation_type', name='uq_paper_relation'),
        Index('idx_paper_relations_source', 'source_paper_id'),
        Index('idx_paper_relations_target', 'target_paper_id'),
        Index('idx_paper_relations_type', 'relation_type'),
        Index('idx_paper_relations_hop_count', 'hop_count'),
        CheckConstraint('hop_count >= 1', name='check_hop_count_positive'),
    )


class Venue(Base):
    """会議・学会モデル."""
    __tablename__ = 'venues'

    venue_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String)  # 'conference', 'workshop', etc.

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # リレーションシップ
    papers: Mapped[List["Paper"]] = relationship("Paper", back_populates="venue")

    # インデックス
    __table_args__ = (
        Index('idx_venues_name', 'name'),
        Index('idx_venues_type', 'type'),
    )


class Journal(Base):
    """ジャーナルモデル."""
    __tablename__ = 'journals'

    journal_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # リレーションシップ
    papers: Mapped[List["Paper"]] = relationship("Paper", back_populates="journal")

    # インデックス
    __table_args__ = (
        Index('idx_journals_name', 'name'),
    )


class PaperExternalId(Base):
    """論文の外部識別子."""
    __tablename__ = 'paper_external_ids'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey('papers.paper_id'), nullable=False)
    id_type: Mapped[str] = mapped_column(String, nullable=False)  # 'DOI', 'ArXiv', 'PubMed', etc.
    external_id: Mapped[str] = mapped_column(String, nullable=False)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # リレーションシップ
    paper: Mapped["Paper"] = relationship("Paper", back_populates="external_ids")

    # インデックス
    __table_args__ = (
        UniqueConstraint('paper_id', 'id_type', 'external_id', name='uq_paper_external_id'),
        Index('idx_paper_external_ids_paper_id', 'paper_id'),
        Index('idx_paper_external_ids_type', 'id_type'),
        Index('idx_paper_external_ids_external_id', 'external_id'),
    )


class PaperFieldOfStudy(Base):
    """論文の研究分野."""
    __tablename__ = 'paper_fields_of_study'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey('papers.paper_id'), nullable=False)
    field_name: Mapped[str] = mapped_column(String, nullable=False)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # リレーションシップ
    paper: Mapped["Paper"] = relationship("Paper", back_populates="fields_of_study")

    # インデックス
    __table_args__ = (
        UniqueConstraint('paper_id', 'field_name', name='uq_paper_field_of_study'),
        Index('idx_paper_fields_of_study_paper_id', 'paper_id'),
        Index('idx_paper_fields_of_study_field_name', 'field_name'),
    )


class PaperKeyword(Base):
    """AI生成キーワード."""
    __tablename__ = 'paper_keywords'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey('papers.paper_id'), nullable=False)
    keyword: Mapped[str] = mapped_column(String, nullable=False)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # リレーションシップ
    paper: Mapped["Paper"] = relationship("Paper", back_populates="keywords")

    # インデックス
    __table_args__ = (
        UniqueConstraint('paper_id', 'keyword', name='uq_paper_keyword'),
        Index('idx_paper_keywords_paper_id', 'paper_id'),
        Index('idx_paper_keywords_keyword', 'keyword'),
        Index('idx_paper_keywords_relevance_score', 'relevance_score'),
    )


class ProcessingQueue(Base):
    """処理キューモデル."""
    __tablename__ = 'processing_queue'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey('papers.paper_id'), nullable=False)
    task_type: Mapped[str] = mapped_column(String, nullable=False)  # 'crawl', 'summarize', 'generate'
    status: Mapped[str] = mapped_column(String, default='pending')  # 'pending', 'running', 'completed', 'failed'
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # エラー情報
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # インデックス
    __table_args__ = (
        Index('idx_processing_queue_paper_id', 'paper_id'),
        Index('idx_processing_queue_task_type', 'task_type'),
        Index('idx_processing_queue_status', 'status'),
        Index('idx_processing_queue_priority', 'priority'),
        Index('idx_processing_queue_created_at', 'created_at'),
        CheckConstraint('priority >= 0', name='check_priority_positive'),
        CheckConstraint('retry_count >= 0', name='check_retry_count_positive'),
    )
```

### 2. データベース接続ヘルパー

`package/shared/src/refnet_shared/models/database_manager.py`:

```python
"""データベース接続管理."""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker
from refnet_shared.config import settings
from refnet_shared.models.database import Base


class DatabaseManager:
    """データベース接続管理クラス."""

    def __init__(self, database_url: str | None = None):
        """初期化."""
        self.database_url = database_url or settings.database.url
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self) -> None:
        """テーブル作成."""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self) -> None:
        """テーブル削除."""
        Base.metadata.drop_all(bind=self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """セッション取得."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# グローバルインスタンス
db_manager = DatabaseManager()
```

### 3. Pydanticスキーマ定義

`package/shared/src/refnet_shared/models/schemas.py`:

```python
"""Pydanticスキーマ定義."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PaperBase(BaseModel):
    """論文基底スキーマ."""
    title: str
    abstract: Optional[str] = None
    year: Optional[int] = None
    citation_count: int = 0
    reference_count: int = 0


class PaperCreate(PaperBase):
    """論文作成スキーマ."""
    paper_id: str


class PaperUpdate(BaseModel):
    """論文更新スキーマ."""
    title: Optional[str] = None
    abstract: Optional[str] = None
    year: Optional[int] = None
    citation_count: Optional[int] = None
    reference_count: Optional[int] = None
    summary: Optional[str] = None
    pdf_url: Optional[str] = None


class PaperResponse(PaperBase):
    """論文レスポンススキーマ."""
    paper_id: str
    crawl_status: str
    pdf_status: str
    summary_status: str
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuthorBase(BaseModel):
    """著者基底スキーマ."""
    name: str


class AuthorCreate(AuthorBase):
    """著者作成スキーマ."""
    author_id: str


class AuthorResponse(AuthorBase):
    """著者レスポンススキーマ."""
    author_id: str
    paper_count: int
    citation_count: int
    h_index: Optional[int] = None

    model_config = {"from_attributes": True}


class PaperRelationCreate(BaseModel):
    """論文関係作成スキーマ."""
    source_paper_id: str
    target_paper_id: str
    relation_type: str
    hop_count: int = 1


class PaperRelationResponse(BaseModel):
    """論文関係レスポンススキーマ."""
    id: int
    source_paper_id: str
    target_paper_id: str
    relation_type: str
    hop_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ProcessingQueueCreate(BaseModel):
    """処理キュー作成スキーマ."""
    paper_id: str
    task_type: str
    priority: int = 0


class ProcessingQueueResponse(BaseModel):
    """処理キューレスポンススキーマ."""
    id: int
    paper_id: str
    task_type: str
    status: str
    priority: int
    retry_count: int
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}
```

### 4. テストの作成

`package/shared/tests/test_models.py`:

```python
"""データベースモデルのテスト."""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from refnet_shared.models.database import Base, Paper, Author, PaperRelation
from refnet_shared.models.database_manager import DatabaseManager


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
```

## スコープ

- SQLAlchemyモデル定義
- データベース接続管理
- Pydanticスキーマ定義
- 基本的なテストケース作成

**スコープ外:**
- Alembicマイグレーション
- 複雑なクエリ関数
- パフォーマンスチューニング

## 参照するドキュメント

- `/docs/database/schema.md`
- `/docs/database/erd.md`
- `/docs/development/coding-standards.md`

## 完了条件

### 機能要件
- [ ] 全テーブルのSQLAlchemyモデルが定義されている
- [ ] Pydanticスキーマが定義されている
- [ ] データベース接続管理クラスが実装されている
- [ ] 基本的なテストケースが作成されている

### パフォーマンス要件
- [ ] 論文検索クエリの応答時間が500ms以下である（10,000件データベース）
- [ ] 同時接続数100でのデータベース接続プール安定動作
- [ ] インデックスが設定されたクエリの実行時間が100ms以下である
- [ ] トランザクションのコミット時間が50ms以下である
- [ ] 1秒間に100件の論文データ挿入が可能である

### 品質要件
- [ ] `cd package/shared && moon check` が正常終了する
- [ ] テストカバレッジが80%以上である
- [ ] メモリ使用量がベースライン+200MB以下である（10,000件データロード時）

## レビュー観点

### 技術的正確性
- [ ] SQLAlchemyモデルの定義がPostgreSQLの制約に適合している
- [ ] リレーションシップが双方向で正しく設定されている
- [ ] インデックスが検索頻度の高いカラムに適切に設定されている
- [ ] Pydanticスキーマがモデルと整合性を保っている
- [ ] マイグレーション対応のためのテーブル・カラム設計が適切である

### 実装可能性
- [ ] データベース接続プールの設定が適切である
- [ ] トランザクション管理が正しく実装されている
- [ ] モデル間の循環参照が適切に処理されている
- [ ] 大量データ処理に対応できるクエリ設計である

### 統合考慮事項
- [ ] Semantic Scholar APIのデータ構造に対応している
- [ ] 論文関係の再帰的な構造を効率的に表現できている
- [ ] 複数のサービスから同時アクセスされることを考慮した設計である
- [ ] 処理キューモデルが非同期処理に適している

### 品質基準
- [ ] 全モデルに適切な制約（CheckConstraint、UniqueConstraint）が設定されている
- [ ] 型安全性が確保されている（Mapped型アノテーション）
- [ ] エラーハンドリングが適切に実装されている
- [ ] テストデータの作成・削除が確実に行われている

### セキュリティ考慮事項
- [ ] SQLインジェクション対策が適切である
- [ ] 機密情報（APIキー等）がデータベースに保存されていない
- [ ] アクセス制御の基盤が考慮されている

### パフォーマンス考慮事項
- [ ] 検索処理に必要なインデックスが設定されている
- [ ] N+1問題を回避するリレーション設計である
- [ ] 論文ネットワークの探索が効率的に行える設計である
- [ ] バッチ処理に適したデータ構造である

### 保守性
- [ ] スキーマ変更時の影響範囲が最小限である
- [ ] 新しいテーブル・カラムの追加が容易である
- [ ] データマイグレーション戦略が考慮されている
