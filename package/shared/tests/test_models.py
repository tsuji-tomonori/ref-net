"""データベースモデルのテスト."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from refnet_shared.models.database import Author, Base, Paper, PaperRelation
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

        session.add(paper)
        session.add(author)
        session.commit()

        # 関係設定（paper_authorsテーブルに直接挿入）
        from sqlalchemy import text
        session.execute(text(
            "INSERT INTO paper_authors (paper_id, author_id, position, created_at) "
            "VALUES (:paper_id, :author_id, :position, :created_at)"
        ), {
            "paper_id": "test-paper-1",
            "author_id": "test-author-1",
            "position": 1,
            "created_at": datetime.utcnow()
        })
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
