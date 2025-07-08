"""メインモジュールのテスト."""

import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

from refnet_crawler.main import crawl_paper, main


class TestCrawlPaper:
    """論文クローリング機能のテスト."""

    @pytest.mark.asyncio
    async def test_crawl_paper_success(self) -> None:
        """論文クローリング成功テスト."""
        with patch('refnet_crawler.main.CrawlerService') as mock_service_class:
            mock_service = Mock()
            mock_service.crawl_paper = AsyncMock(return_value=True)
            mock_service.close = AsyncMock()
            mock_service_class.return_value = mock_service

            result = await crawl_paper("test-paper-1", 1, 2)

            assert result is True
            mock_service.crawl_paper.assert_called_once_with("test-paper-1", 1, 2)
            mock_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_paper_failure(self) -> None:
        """論文クローリング失敗テスト."""
        with patch('refnet_crawler.main.CrawlerService') as mock_service_class:
            mock_service = Mock()
            mock_service.crawl_paper = AsyncMock(return_value=False)
            mock_service.close = AsyncMock()
            mock_service_class.return_value = mock_service

            result = await crawl_paper("test-paper-1", 0, 3)

            assert result is False
            mock_service.crawl_paper.assert_called_once_with("test-paper-1", 0, 3)
            mock_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_paper_exception(self) -> None:
        """論文クローリング例外テスト."""
        with patch('refnet_crawler.main.CrawlerService') as mock_service_class:
            mock_service = Mock()
            mock_service.crawl_paper = AsyncMock(side_effect=Exception("Test error"))
            mock_service.close = AsyncMock()
            mock_service_class.return_value = mock_service

            with pytest.raises(Exception, match="Test error"):
                await crawl_paper("test-paper-1")

            mock_service.close.assert_called_once()


class TestMain:
    """メイン関数のテスト."""

    def test_main_success(self) -> None:
        """メイン関数成功テスト."""
        test_args = ["script_name", "test-paper-1", "1", "2"]

        with patch.object(sys, 'argv', test_args):
            with patch('refnet_crawler.main.asyncio.run') as mock_asyncio_run:
                mock_asyncio_run.return_value = True
                with patch('builtins.print') as mock_print:
                    main()

                    mock_print.assert_called_with("Successfully crawled paper: test-paper-1")

    def test_main_failure(self) -> None:
        """メイン関数失敗テスト."""
        test_args = ["script_name", "test-paper-1"]

        with patch.object(sys, 'argv', test_args):
            with patch('refnet_crawler.main.asyncio.run') as mock_asyncio_run:
                mock_asyncio_run.return_value = False
                with patch('builtins.print') as mock_print:
                    with pytest.raises(SystemExit) as exc_info:
                        main()

                    assert exc_info.value.code == 1
                    mock_print.assert_called_with("Failed to crawl paper: test-paper-1")

    def test_main_exception(self) -> None:
        """メイン関数例外テスト."""
        test_args = ["script_name", "test-paper-1"]

        with patch.object(sys, 'argv', test_args):
            with patch('refnet_crawler.main.asyncio.run') as mock_asyncio_run:
                mock_asyncio_run.side_effect = Exception("Test error")
                with patch('builtins.print') as mock_print:
                    with pytest.raises(SystemExit) as exc_info:
                        main()

                    assert exc_info.value.code == 1
                    mock_print.assert_called_with("Error: Test error")

    def test_main_insufficient_args(self) -> None:
        """メイン関数引数不足テスト."""
        test_args = ["script_name"]

        with patch.object(sys, 'argv', test_args):
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1
                mock_print.assert_called_with(
                    "Usage: python -m refnet_crawler.main <paper_id> [hop_count] [max_hops]"
                )

    def test_main_with_default_args(self) -> None:
        """メイン関数デフォルト引数テスト."""
        test_args = ["script_name", "test-paper-1"]

        with patch.object(sys, 'argv', test_args):
            with patch('refnet_crawler.main.asyncio.run') as mock_asyncio_run:
                mock_asyncio_run.return_value = True
                with patch('builtins.print'):
                    main()

                    # デフォルト値での呼び出し確認
                    mock_asyncio_run.assert_called_once()
                    # アサーション内容をより簡潔に
                    assert mock_asyncio_run.called

    def test_main_with_all_args(self) -> None:
        """メイン関数全引数テスト."""
        test_args = ["script_name", "test-paper-1", "2", "5"]

        with patch.object(sys, 'argv', test_args):
            with patch('refnet_crawler.main.asyncio.run') as mock_asyncio_run:
                mock_asyncio_run.return_value = True
                with patch('builtins.print'):
                    main()

                    mock_asyncio_run.assert_called_once()
