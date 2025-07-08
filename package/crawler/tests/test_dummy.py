"""論文データモデルのテスト."""

from typing import Any

from refnet_crawler.models.paper_data import (
    SemanticScholarAuthor,
    SemanticScholarJournal,
    SemanticScholarPaper,
    SemanticScholarVenue,
)


class TestSemanticScholarAuthor:
    """SemanticScholarAuthorのテスト."""

    def test_create_with_all_fields(self) -> None:
        """全フィールド指定での作成テスト."""
        author = SemanticScholarAuthor(
            authorId="author-1",
            name="Test Author"
        )

        assert author.authorId == "author-1"
        assert author.name == "Test Author"

    def test_create_with_none_values(self) -> None:
        """None値での作成テスト."""
        author = SemanticScholarAuthor(
            authorId=None,
            name=None
        )

        assert author.authorId is None
        assert author.name is None

    def test_create_minimal(self) -> None:
        """最小構成での作成テスト."""
        author = SemanticScholarAuthor()

        assert author.authorId is None
        assert author.name is None


class TestSemanticScholarVenue:
    """SemanticScholarVenueのテスト."""

    def test_create_with_all_fields(self) -> None:
        """全フィールド指定での作成テスト."""
        venue = SemanticScholarVenue(
            id="venue-1",
            name="Test Venue",
            type="journal",
            alternate_names=["Alternative Name"],
            issn="1234-5678",
            url="https://test-venue.com"
        )

        assert venue.id == "venue-1"
        assert venue.name == "Test Venue"
        assert venue.type == "journal"
        assert venue.alternate_names == ["Alternative Name"]
        assert venue.issn == "1234-5678"
        assert venue.url == "https://test-venue.com"

    def test_create_with_none_values(self) -> None:
        """None値での作成テスト."""
        venue = SemanticScholarVenue()

        assert venue.id is None
        assert venue.name is None
        assert venue.type is None
        assert venue.alternate_names is None
        assert venue.issn is None
        assert venue.url is None


class TestSemanticScholarJournal:
    """SemanticScholarJournalのテスト."""

    def test_create_with_all_fields(self) -> None:
        """全フィールド指定での作成テスト."""
        journal = SemanticScholarJournal(
            name="Test Journal",
            pages="1-10",
            volume="42"
        )

        assert journal.name == "Test Journal"
        assert journal.pages == "1-10"
        assert journal.volume == "42"

    def test_create_with_none_values(self) -> None:
        """None値での作成テスト."""
        journal = SemanticScholarJournal()

        assert journal.name is None
        assert journal.pages is None
        assert journal.volume is None


class TestSemanticScholarPaper:
    """SemanticScholarPaperのテスト."""

    def test_paper_data_model(self) -> None:
        """論文データモデルのテスト."""
        paper_data = {
            "paperId": "test-paper-1",
            "title": "Test Paper",
            "abstract": "Test abstract",
            "year": 2023,
            "citationCount": 10,
            "referenceCount": 5,
        }

        paper = SemanticScholarPaper(
            paperId=str(paper_data["paperId"]),
            title=str(paper_data["title"]),
            abstract=str(paper_data["abstract"]),
            year=int(paper_data["year"]),  # type: ignore
            citationCount=int(paper_data["citationCount"]),  # type: ignore
            referenceCount=int(paper_data["referenceCount"]),  # type: ignore
        )
        assert paper.paperId == "test-paper-1"
        assert paper.title == "Test Paper"
        assert paper.citationCount == 10

    def test_paper_to_dict_conversion(self) -> None:
        """論文データのDB用辞書変換テスト."""
        paper_data = {
            "paperId": "test-paper-1",
            "title": "Test Paper",
            "abstract": "Test abstract",
            "year": 2023,
            "citationCount": 10,
            "referenceCount": 5,
        }

        paper = SemanticScholarPaper(
            paperId=str(paper_data["paperId"]),
            title=str(paper_data["title"]),
            abstract=str(paper_data["abstract"]),
            year=int(paper_data["year"]),  # type: ignore
            citationCount=int(paper_data["citationCount"]),  # type: ignore
            referenceCount=int(paper_data["referenceCount"]),  # type: ignore
        )
        db_dict = paper.to_paper_create_dict()

        assert db_dict["paper_id"] == "test-paper-1"
        assert db_dict["title"] == "Test Paper"
        assert db_dict["citation_count"] == 10

    def test_create_with_all_fields(self) -> None:
        """全フィールド指定での作成テスト."""
        paper = SemanticScholarPaper(
            paperId="test-paper-1",
            title="Test Paper",
            abstract="Test abstract",
            year=2023,
            citationCount=100,
            referenceCount=50,
            authors=[
                SemanticScholarAuthor(authorId="author-1", name="Author 1"),
                SemanticScholarAuthor(authorId="author-2", name="Author 2")
            ],
            venue=SemanticScholarVenue(id="venue-1", name="Test Venue"),
            journal=SemanticScholarJournal(name="Test Journal", volume="1"),
            externalIds={"DOI": "10.1000/test", "ArXiv": "2023.12345"},
            fieldsOfStudy=["Computer Science", "Machine Learning"],
            url="https://test-paper.com"
        )

        assert paper.paperId == "test-paper-1"
        assert paper.title == "Test Paper"
        assert paper.abstract == "Test abstract"
        assert paper.year == 2023
        assert paper.citationCount == 100
        assert paper.referenceCount == 50
        assert len(paper.authors or []) == 2
        assert paper.venue is not None
        assert paper.journal is not None
        assert paper.externalIds == {"DOI": "10.1000/test", "ArXiv": "2023.12345"}
        assert paper.fieldsOfStudy == ["Computer Science", "Machine Learning"]
        assert paper.url == "https://test-paper.com"

    def test_create_with_none_values(self) -> None:
        """None値での作成テスト."""
        paper = SemanticScholarPaper(paperId="test-paper-1")

        assert paper.paperId == "test-paper-1"
        assert paper.title is None
        assert paper.abstract is None
        assert paper.year is None
        assert paper.citationCount is None
        assert paper.referenceCount is None
        assert paper.authors is None
        assert paper.venue is None
        assert paper.journal is None
        assert paper.externalIds is None
        assert paper.fieldsOfStudy is None
        assert paper.url is None

    def test_to_paper_create_dict_with_none_title(self) -> None:
        """title=Noneでの辞書変換テスト."""
        paper = SemanticScholarPaper(
            paperId="test-paper-1",
            title=None,
            citationCount=None,
            referenceCount=None
        )

        db_dict = paper.to_paper_create_dict()

        assert db_dict["paper_id"] == "test-paper-1"
        assert db_dict["title"] == ""  # None -> 空文字列に変換
        assert db_dict["citation_count"] == 0  # None -> 0に変換
        assert db_dict["reference_count"] == 0  # None -> 0に変換

    def test_model_validate_from_dict(self) -> None:
        """辞書からのモデル作成テスト."""
        data: dict[str, Any] = {
            "paperId": "test-paper-1",
            "title": "Test Paper",
            "abstract": "Test abstract",
            "year": 2023,
            "citationCount": 10,
            "referenceCount": 5,
            "authors": [
                {"authorId": "author-1", "name": "Author 1"}
            ],
            "venue": {"id": "venue-1", "name": "Test Venue"},
            "journal": {"name": "Test Journal"},
            "externalIds": {"DOI": "10.1000/test"},
            "fieldsOfStudy": ["Computer Science"],
            "url": "https://test-paper.com"
        }

        paper = SemanticScholarPaper.model_validate(data)

        assert paper.paperId == "test-paper-1"
        assert paper.title == "Test Paper"
        assert len(paper.authors or []) == 1
        assert paper.venue is not None
        assert paper.journal is not None
