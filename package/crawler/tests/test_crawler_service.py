"""クローラーサービスのテスト."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from refnet_shared.exceptions import ExternalAPIError

from refnet_crawler.models.paper_data import SemanticScholarPaper
from refnet_crawler.services.crawler_service import CrawlerService


@pytest.fixture
def mock_paper_data() -> dict[str, Any]:
    """モック論文データ."""
    return {
        "paperId": "test-paper-1",
        "title": "Test Paper",
        "abstract": "Test abstract",
        "year": 2023,
        "citationCount": 10,
        "referenceCount": 5,
        "authors": [
            {"authorId": "author-1", "name": "Test Author"}
        ],
        "externalIds": {"DOI": "10.1000/test"},
        "fieldsOfStudy": ["Computer Science"]
    }


@pytest.fixture
def mock_semantic_scholar_paper(mock_paper_data: dict[str, Any]) -> SemanticScholarPaper:
    """モックSemanticScholarPaperオブジェクト."""
    return SemanticScholarPaper.model_validate(mock_paper_data)


@pytest.fixture
def mock_db_session() -> Mock:
    """モックDBセッション."""
    session = Mock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    session.commit.return_value = None
    session.execute.return_value.fetchone.return_value = None
    return session


class TestCrawlerService:
    """クローラーサービスのテスト."""

    def test_init(self) -> None:
        """初期化テスト."""
        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient') as mock_client:
            service = CrawlerService()

            assert service.client is not None
            mock_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_paper_success(
        self,
        mock_semantic_scholar_paper: SemanticScholarPaper,
        mock_db_session: Mock
    ) -> None:
        """論文クローリング成功テスト."""
        with patch(
            'refnet_crawler.services.crawler_service.SemanticScholarClient'
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.get_paper = AsyncMock(return_value=mock_semantic_scholar_paper)
            mock_client_class.return_value = mock_client

            with patch('refnet_crawler.services.crawler_service.db_manager') as mock_db_manager:
                mock_db_manager.get_session.return_value.__enter__.return_value = mock_db_session

                service = CrawlerService()
                result = await service.crawl_paper("test-paper-1", 0, 3)

                assert result is True
                mock_client.get_paper.assert_called_once_with("test-paper-1")

    @pytest.mark.asyncio
    async def test_crawl_paper_not_found(self, mock_db_session: Mock) -> None:
        """論文未発見テスト."""
        with patch(
            'refnet_crawler.services.crawler_service.SemanticScholarClient'
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.get_paper = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            service = CrawlerService()
            result = await service.crawl_paper("nonexistent-paper", 0, 3)

            assert result is False

    @pytest.mark.asyncio
    async def test_crawl_paper_exception(self, mock_db_session: Mock) -> None:
        """論文クローリング例外テスト."""
        with patch(
            'refnet_crawler.services.crawler_service.SemanticScholarClient'
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.get_paper = AsyncMock(side_effect=ExternalAPIError("API Error"))
            mock_client_class.return_value = mock_client

            with patch('refnet_crawler.services.crawler_service.db_manager') as mock_db_manager:
                mock_db_manager.get_session.return_value.__enter__.return_value = mock_db_session

                service = CrawlerService()
                result = await service.crawl_paper("test-paper-1", 0, 3)

                assert result is False

    @pytest.mark.asyncio
    async def test_save_paper_data_new_paper(
        self,
        mock_semantic_scholar_paper: SemanticScholarPaper,
        mock_db_session: Mock
    ) -> None:
        """新規論文データ保存テスト."""
        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient'):
            with patch('refnet_crawler.services.crawler_service.Paper') as mock_paper_class:
                mock_paper = Mock()
                mock_paper_class.return_value = mock_paper

                service = CrawlerService()
                # _save_authorsをモック化してauthors処理をスキップ
                with patch.object(service, '_save_authors'):
                    await service._save_paper_data(mock_db_session, mock_semantic_scholar_paper)

                mock_db_session.add.assert_called_with(mock_paper)
                mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_paper_data_existing_paper(
        self,
        mock_semantic_scholar_paper: SemanticScholarPaper,
        mock_db_session: Mock
    ) -> None:
        """既存論文データ更新テスト."""
        existing_paper = Mock()
        existing_paper.title = "Old Title"
        existing_paper.abstract = "Old Abstract"
        existing_paper.year = 2020
        existing_paper.citation_count = 5
        existing_paper.reference_count = 3

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = (
            existing_paper
        )

        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient'):
            service = CrawlerService()
            await service._save_paper_data(mock_db_session, mock_semantic_scholar_paper)

            assert existing_paper.title == "Test Paper"
            assert existing_paper.abstract == "Test abstract"
            assert existing_paper.year == 2023
            assert existing_paper.citation_count == 10
            assert existing_paper.reference_count == 5
            assert existing_paper.is_crawled is True

    @pytest.mark.asyncio
    async def test_save_authors(self, mock_db_session: Mock) -> None:
        """著者情報保存テスト."""
        authors_data = [
            Mock(authorId="author-1", name="Author 1"),
            Mock(authorId="author-2", name="Author 2"),
            Mock(authorId=None, name="No ID Author")  # authorIdがNoneの場合
        ]

        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient'):
            with patch('refnet_crawler.services.crawler_service.Author') as mock_author_class:
                mock_author = Mock()
                mock_author_class.return_value = mock_author

                service = CrawlerService()
                await service._save_authors(mock_db_session, "test-paper-1", authors_data)

                # authorIdがNoneの著者は処理されない
                assert mock_author_class.call_count == 2

    @pytest.mark.asyncio
    async def test_crawl_citations(self, mock_db_session: Mock) -> None:
        """引用論文収集テスト."""
        citations = [
            Mock(paperId="citing-paper-1", citationCount=50, year=2023),
            Mock(paperId="citing-paper-2", citationCount=5, year=2020)
        ]

        with patch(
            'refnet_crawler.services.crawler_service.SemanticScholarClient'
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.get_paper_citations = AsyncMock(return_value=citations)
            mock_client_class.return_value = mock_client

            service = CrawlerService()

            with patch.object(service, '_save_paper_relation') as mock_save_relation:
                with patch.object(service, '_should_crawl_recursively') as mock_should_crawl:
                    with patch.object(service, '_queue_paper_for_crawling') as mock_queue:
                        mock_should_crawl.return_value = True

                        await service._crawl_citations(mock_db_session, "test-paper-1", 1, 3)

                        assert mock_save_relation.call_count == 2
                        assert mock_queue.call_count == 2

    @pytest.mark.asyncio
    async def test_crawl_references(self, mock_db_session: Mock) -> None:
        """参考文献収集テスト."""
        references = [
            Mock(paperId="ref-paper-1", citationCount=100, year=2022),
            Mock(paperId="ref-paper-2", citationCount=20, year=2021)
        ]

        with patch(
            'refnet_crawler.services.crawler_service.SemanticScholarClient'
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.get_paper_references = AsyncMock(return_value=references)
            mock_client_class.return_value = mock_client

            service = CrawlerService()

            with patch.object(service, '_save_paper_relation') as mock_save_relation:
                with patch.object(service, '_should_crawl_recursively') as mock_should_crawl:
                    with patch.object(service, '_queue_paper_for_crawling') as mock_queue:
                        mock_should_crawl.return_value = True

                        await service._crawl_references(mock_db_session, "test-paper-1", 1, 3)

                        assert mock_save_relation.call_count == 2
                        assert mock_queue.call_count == 2

    @pytest.mark.asyncio
    async def test_save_paper_relation_new(self, mock_db_session: Mock) -> None:
        """新規論文関係保存テスト."""
        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient'):
            with patch(
                'refnet_crawler.services.crawler_service.PaperRelation'
            ) as mock_relation_class:
                mock_relation = Mock()
                mock_relation_class.return_value = mock_relation

                service = CrawlerService()
                await service._save_paper_relation(
                    mock_db_session,
                    "source-paper",
                    "target-paper",
                    "citation",
                    1
                )

                mock_db_session.add.assert_called_with(mock_relation)

    @pytest.mark.asyncio
    async def test_save_paper_relation_existing(self, mock_db_session: Mock) -> None:
        """既存論文関係スキップテスト."""
        existing_relation = Mock()
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = (
            existing_relation
        )

        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient'):
            service = CrawlerService()
            await service._save_paper_relation(
                mock_db_session,
                "source-paper",
                "target-paper",
                "citation",
                1
            )

            mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_should_crawl_recursively(self) -> None:
        """再帰的収集判定テスト."""
        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient'):
            service = CrawlerService()

            # 高優先度論文（引用数多い、新しい）
            high_priority_paper = Mock(citationCount=200, year=2023)
            result = await service._should_crawl_recursively(high_priority_paper, 1, 3)
            assert result is True

            # 低優先度論文（引用数少ない、古い）
            low_priority_paper = Mock(citationCount=1, year=1990)
            result = await service._should_crawl_recursively(low_priority_paper, 1, 3)
            assert result is False

            # 最大ホップ数到達
            result = await service._should_crawl_recursively(high_priority_paper, 3, 3)
            assert result is False

            # None値のハンドリング
            none_paper = Mock(citationCount=None, year=None)
            result = await service._should_crawl_recursively(none_paper, 1, 3)
            assert result is False

    @pytest.mark.asyncio
    async def test_queue_paper_for_crawling_new(self, mock_db_session: Mock) -> None:
        """新規論文キューイングテスト."""
        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient'):
            with patch(
                'refnet_crawler.services.crawler_service.ProcessingQueue'
            ) as mock_queue_class:
                mock_queue = Mock()
                mock_queue_class.return_value = mock_queue

                service = CrawlerService()
                await service._queue_paper_for_crawling(mock_db_session, "test-paper-1", 1)

                mock_db_session.add.assert_called_with(mock_queue)

    @pytest.mark.asyncio
    async def test_queue_paper_for_crawling_existing(self, mock_db_session: Mock) -> None:
        """既存論文キューイングスキップテスト."""
        existing_queue = Mock()
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = (
            existing_queue
        )

        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient'):
            service = CrawlerService()
            await service._queue_paper_for_crawling(mock_db_session, "test-paper-1", 1)

            mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_processing_status_with_queue(self, mock_db_session: Mock) -> None:
        """処理状態更新（キューあり）テスト."""
        queue_item = Mock()
        queue_item.retry_count = 0
        paper = Mock()

        mock_db_session.query.return_value.filter_by.return_value.first.side_effect = [
            queue_item,  # ProcessingQueue
            paper        # Paper
        ]

        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient'):
            service = CrawlerService()
            await service._update_processing_status(
                mock_db_session,
                "test-paper-1",
                "crawl",
                "failed",
                "Error message"
            )

            assert queue_item.status == "failed"
            assert queue_item.error_message == "Error message"
            assert queue_item.retry_count == 1
            assert paper.is_crawled is False

    @pytest.mark.asyncio
    async def test_update_processing_status_no_queue(self, mock_db_session: Mock) -> None:
        """処理状態更新（キューなし）テスト."""
        paper = Mock()

        mock_db_session.query.return_value.filter_by.return_value.first.side_effect = [
            None,  # ProcessingQueue
            paper  # Paper
        ]

        with patch('refnet_crawler.services.crawler_service.SemanticScholarClient'):
            service = CrawlerService()
            await service._update_processing_status(
                mock_db_session,
                "test-paper-1",
                "crawl",
                "completed"
            )

            assert paper.is_crawled is True

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """リソースクリーンアップテスト."""
        with patch(
            'refnet_crawler.services.crawler_service.SemanticScholarClient'
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            service = CrawlerService()
            await service.close()

            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_citations_exception(self, mock_db_session: Mock) -> None:
        """引用論文収集例外テスト."""
        with patch(
            'refnet_crawler.services.crawler_service.SemanticScholarClient'
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.get_paper_citations = AsyncMock(side_effect=Exception("API Error"))
            mock_client_class.return_value = mock_client

            service = CrawlerService()
            # 例外が発生しても処理が継続することを確認
            await service._crawl_citations(mock_db_session, "test-paper-1", 1, 3)

    @pytest.mark.asyncio
    async def test_crawl_references_exception(self, mock_db_session: Mock) -> None:
        """参考文献収集例外テスト."""
        with patch(
            'refnet_crawler.services.crawler_service.SemanticScholarClient'
        ) as mock_client_class:
            mock_client = Mock()
            mock_client.get_paper_references = AsyncMock(side_effect=Exception("API Error"))
            mock_client_class.return_value = mock_client

            service = CrawlerService()
            # 例外が発生しても処理が継続することを確認
            await service._crawl_references(mock_db_session, "test-paper-1", 1, 3)
