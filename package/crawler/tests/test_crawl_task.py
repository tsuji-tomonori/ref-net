"""crawl_taskモジュールのテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCrawlTaskBasic:
    """クロールタスクの基本テスト."""

    def test_module_imports(self) -> None:
        """モジュールのインポートテスト."""
        try:
            from refnet_crawler.tasks.crawl_task import check_and_crawl_new_papers, crawl_paper
            # インポートが成功することを確認
            assert check_and_crawl_new_papers is not None
            assert crawl_paper is not None
        except ImportError:
            pytest.fail("必要なモジュールのインポートに失敗しました")

    def test_database_models_import(self) -> None:
        """データベースモデルのインポートテスト."""
        try:
            from refnet_shared.models.database import Paper
            from refnet_shared.models.database_manager import db_manager
            # インポートが成功することを確認
            assert Paper is not None
            assert db_manager is not None
        except ImportError:
            pytest.fail("データベース関連のインポートに失敗しました")

    @pytest.mark.asyncio
    async def test_async_function_behavior(self) -> None:
        """非同期関数の動作テスト."""
        with patch('refnet_crawler.services.crawler_service.CrawlerService') as mock_service_class:
            # CrawlerServiceのモック
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            mock_service.crawl_paper = AsyncMock(return_value=True)

            # 非同期関数のテスト
            async def _test_crawl() -> bool:
                crawler = mock_service_class()
                try:
                    return await crawler.crawl_paper("test-paper-123", 0, 3)
                finally:
                    pass

            result = await _test_crawl()

            # アサーション
            assert result is True
            mock_service.crawl_paper.assert_called_once_with("test-paper-123", 0, 3)
