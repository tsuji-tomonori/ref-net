"""クローラーサービスの基本テスト."""

from refnet_crawler.models.paper_data import SemanticScholarPaper


def test_paper_data_model() -> None:
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
        paperId=paper_data["paperId"],
        title=paper_data["title"],
        abstract=paper_data["abstract"],
        year=paper_data["year"],
        citationCount=paper_data["citationCount"],
        referenceCount=paper_data["referenceCount"],
    )
    assert paper.paperId == "test-paper-1"
    assert paper.title == "Test Paper"
    assert paper.citationCount == 10


def test_paper_to_dict_conversion() -> None:
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
        paperId=paper_data["paperId"],
        title=paper_data["title"],
        abstract=paper_data["abstract"],
        year=paper_data["year"],
        citationCount=paper_data["citationCount"],
        referenceCount=paper_data["referenceCount"],
    )
    db_dict = paper.to_paper_create_dict()

    assert db_dict["paper_id"] == "test-paper-1"
    assert db_dict["title"] == "Test Paper"
    assert db_dict["citation_count"] == 10
