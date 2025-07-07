"""クローラーサービスの基本テスト."""

import pytest
from refnet_crawler.models.paper_data import SemanticScholarPaper


def test_paper_data_model():
    """論文データモデルのテスト."""
    paper_data = {
        "paperId": "test-paper-1",
        "title": "Test Paper",
        "abstract": "Test abstract",
        "year": 2023,
        "citationCount": 10,
        "referenceCount": 5,
    }

    paper = SemanticScholarPaper(**paper_data)
    assert paper.paperId == "test-paper-1"
    assert paper.title == "Test Paper"
    assert paper.citationCount == 10


def test_paper_to_dict_conversion():
    """論文データのDB用辞書変換テスト."""
    paper_data = {
        "paperId": "test-paper-1",
        "title": "Test Paper",
        "abstract": "Test abstract",
        "year": 2023,
        "citationCount": 10,
        "referenceCount": 5,
    }

    paper = SemanticScholarPaper(**paper_data)
    db_dict = paper.to_paper_create_dict()

    assert db_dict["paper_id"] == "test-paper-1"
    assert db_dict["title"] == "Test Paper"
    assert db_dict["citation_count"] == 10
