"""著者エンドポイントのテスト."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from refnet_shared.models.database import Author, Base, Paper
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from refnet_api.dependencies import get_db
from refnet_api.main import app


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """テスト用データベースセッション."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db: Session) -> Generator[TestClient, None, None]:
    """テスト用FastAPIクライアント."""
    app.dependency_overrides[get_db] = lambda: test_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_author(test_db: Session) -> Author:
    """サンプル著者データ."""
    author = Author(
        author_id="test-author-1",
        name="Test Author",
        affiliations="Test University",
        homepage_url="https://example.com",
        paper_count=2,
        citation_count=10,
        h_index=3,
    )
    test_db.add(author)

    # 著者に関連する論文も追加
    paper1 = Paper(
        paper_id="paper-1",
        title="Test Paper 1",
        abstract="Abstract 1",
        pdf_url="https://example.com/paper1.pdf",
    )
    paper2 = Paper(
        paper_id="paper-2",
        title="Test Paper 2",
        abstract="Abstract 2",
        pdf_url="https://example.com/paper2.pdf",
    )
    test_db.add(paper1)
    test_db.add(paper2)
    test_db.commit()

    # 著者と論文を関連付け（position付き）
    from refnet_shared.models.database import paper_authors
    test_db.execute(
        paper_authors.insert().values(
            paper_id="paper-1", author_id="test-author-1", position=0
        )
    )
    test_db.execute(
        paper_authors.insert().values(
            paper_id="paper-2", author_id="test-author-1", position=0
        )
    )
    test_db.commit()

    return author


def test_get_authors(client: TestClient, sample_author: Author) -> None:
    """著者一覧取得のテスト."""
    response = client.get("/api/v1/authors/")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["per_page"] == 100
    assert len(data["authors"]) == 1
    assert data["authors"][0]["author_id"] == sample_author.author_id
    assert data["authors"][0]["name"] == sample_author.name


def test_get_authors_with_pagination(client: TestClient, test_db: Session) -> None:
    """ページネーション付き著者一覧取得のテスト."""
    # 複数の著者を作成
    for i in range(5):
        author = Author(
            author_id=f"author-{i}",
            name=f"Author {i}",
            paper_count=i,
            citation_count=i * 2,
        )
        test_db.add(author)
    test_db.commit()

    # ページネーションテスト
    response = client.get("/api/v1/authors/?skip=2&limit=2")
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 5
    assert data["page"] == 2
    assert data["per_page"] == 2
    assert len(data["authors"]) == 2


def test_get_author_detail(client: TestClient, sample_author: Author) -> None:
    """著者詳細取得のテスト."""
    response = client.get(f"/api/v1/authors/{sample_author.author_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["author_id"] == sample_author.author_id
    assert data["name"] == sample_author.name
    assert data["affiliations"] == sample_author.affiliations
    assert data["homepage_url"] == sample_author.homepage_url
    assert data["paper_count"] == sample_author.paper_count
    assert data["citation_count"] == sample_author.citation_count
    assert data["h_index"] == sample_author.h_index


def test_get_author_not_found(client: TestClient) -> None:
    """存在しない著者の取得テスト."""
    response = client.get("/api/v1/authors/non-existent-author")
    assert response.status_code == 404
    assert response.json()["detail"] == "Author not found"


def test_get_author_papers(client: TestClient, sample_author: Author) -> None:
    """著者の論文一覧取得のテスト."""
    response = client.get(f"/api/v1/authors/{sample_author.author_id}/papers")
    assert response.status_code == 200

    data = response.json()
    assert data["author_id"] == sample_author.author_id
    assert data["total"] == 2
    assert len(data["papers"]) == 2

    # 論文データの確認
    paper_ids = {p["id"] for p in data["papers"]}
    paper_titles = {p["title"] for p in data["papers"]}
    assert "paper-1" in paper_ids
    assert "paper-2" in paper_ids
    assert "Test Paper 1" in paper_titles
    assert "Test Paper 2" in paper_titles


def test_get_author_papers_not_found(client: TestClient) -> None:
    """存在しない著者の論文一覧取得テスト."""
    response = client.get("/api/v1/authors/non-existent-author/papers")
    assert response.status_code == 404
    assert response.json()["detail"] == "Author not found"


def test_get_author_papers_empty(client: TestClient, test_db: Session) -> None:
    """論文を持たない著者の論文一覧取得テスト."""
    # 論文を持たない著者を作成
    author = Author(
        author_id="no-papers-author",
        name="Author Without Papers",
        paper_count=0,
        citation_count=0,
    )
    test_db.add(author)
    test_db.commit()

    response = client.get(f"/api/v1/authors/{author.author_id}/papers")
    assert response.status_code == 200

    data = response.json()
    assert data["author_id"] == author.author_id
    assert data["total"] == 0
    assert len(data["papers"]) == 0
