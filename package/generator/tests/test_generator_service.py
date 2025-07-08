"""GeneratorServiceのテスト."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from refnet_generator.services.generator_service import GeneratorService
from refnet_shared.models.database import Author, Paper, PaperRelation


@pytest.fixture
def mock_settings() -> Mock:
    """設定のモック."""
    settings = Mock()
    settings.output_dir = "/tmp/test_output"
    return settings


@pytest.fixture
def mock_db_manager() -> Mock:
    """データベースマネージャーのモック."""
    return Mock()


@pytest.fixture
def sample_paper() -> Paper:
    """サンプル論文データ."""
    paper = Paper(
        paper_id="paper123",
        title="Test Paper Title",
        abstract="This is a test abstract",
        year=2024,
        citation_count=10,
        reference_count=5,
        summary="This is a test summary",
        summary_model="gpt-4",
        crawl_status="completed",
        pdf_status="downloaded",
        summary_status="completed",
        pdf_url="https://example.com/paper.pdf",
    )
    return paper


@pytest.fixture
def sample_authors() -> list[Author]:
    """サンプル著者データ."""
    return [
        Author(author_id="author1", name="Test Author 1"),
        Author(author_id="author2", name="Test Author 2"),
    ]


@pytest.fixture
def sample_relations() -> list[PaperRelation]:
    """サンプル関係データ."""
    return [
        PaperRelation(
            source_paper_id="paper456",
            target_paper_id="paper123",
            relation_type="citation",
        ),
        PaperRelation(
            source_paper_id="paper123",
            target_paper_id="paper789",
            relation_type="reference",
        ),
    ]


class TestGeneratorService:
    """GeneratorServiceのテストクラス."""

    @pytest.mark.asyncio
    @patch("refnet_generator.services.generator_service.load_environment_settings")
    @patch("refnet_generator.services.generator_service.db_manager")
    async def test_generate_markdown_success(
        self,
        mock_db_manager: Mock,
        mock_load_settings: Mock,
        mock_settings: Mock,
        sample_paper: Paper,
        sample_authors: list[Author],
        sample_relations: list[PaperRelation],
        tmp_path: Path,
    ) -> None:
        """Markdown生成の正常系テスト."""
        # 設定のモック
        mock_settings.output_dir = str(tmp_path)
        mock_load_settings.return_value = mock_settings

        # セッションのモック
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session

        # クエリのモック
        mock_session.query.return_value.filter_by.return_value.first.return_value = sample_paper
        mock_session.query.return_value.join.return_value.filter.return_value.all.return_value = (
            sample_authors
        )
        mock_session.query.return_value.filter_by.return_value.limit.return_value.all.return_value = sample_relations
        mock_session.query.return_value.filter.return_value.all.return_value = sample_relations
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            sample_paper
        ]
        mock_session.query.return_value.count.return_value = 1
        mock_session.query.return_value.filter.return_value.count.return_value = 1

        # サービスのインスタンス化と実行
        service = GeneratorService()
        result = await service.generate_markdown("paper123")

        # アサーション
        assert result is True
        # Files are created in service.output_dir, not tmp_path
        output_path = Path(service.output_dir)
        assert (output_path / "paper123.md").exists()
        assert (output_path / "paper123_network.md").exists()
        assert (output_path / "index.md").exists()

    @pytest.mark.asyncio
    @patch("refnet_generator.services.generator_service.load_environment_settings")
    @patch("refnet_generator.services.generator_service.db_manager")
    async def test_generate_markdown_paper_not_found(
        self,
        mock_db_manager: Mock,
        mock_load_settings: Mock,
        mock_settings: Mock,
        tmp_path: Path,
    ) -> None:
        """論文が見つからない場合のテスト."""
        # 設定のモック
        mock_settings.output_dir = str(tmp_path)
        mock_load_settings.return_value = mock_settings

        # セッションのモック
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session

        # 論文が見つからない
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # サービスのインスタンス化と実行
        service = GeneratorService()
        result = await service.generate_markdown("nonexistent")

        # アサーション
        assert result is False
        assert not (tmp_path / "nonexistent.md").exists()

    @pytest.mark.asyncio
    @patch("refnet_generator.services.generator_service.load_environment_settings")
    @patch("refnet_generator.services.generator_service.db_manager")
    async def test_generate_markdown_exception(
        self,
        mock_db_manager: Mock,
        mock_load_settings: Mock,
        mock_settings: Mock,
        tmp_path: Path,
    ) -> None:
        """例外発生時のテスト."""
        # 設定のモック
        mock_settings.output_dir = str(tmp_path)
        mock_load_settings.return_value = mock_settings

        # セッションのモックで例外を発生させる
        mock_db_manager.get_session.side_effect = Exception("Database error")

        # サービスのインスタンス化と実行
        service = GeneratorService()
        result = await service.generate_markdown("paper123")

        # アサーション
        assert result is False
