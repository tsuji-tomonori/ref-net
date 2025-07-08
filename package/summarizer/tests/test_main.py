"""メインエントリーポイントのテスト."""

import sys
from unittest.mock import AsyncMock, patch

import pytest

from refnet_summarizer.main import main, summarize_paper


@pytest.mark.asyncio
async def test_summarize_paper_success():  # type: ignore
    """論文要約成功テスト."""
    with patch('refnet_summarizer.main.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.return_value = True

        result = await summarize_paper("test-paper-123")

        assert result is True
        mock_service.summarize_paper.assert_called_once_with("test-paper-123")
        mock_service.close.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_paper_failure():  # type: ignore
    """論文要約失敗テスト."""
    with patch('refnet_summarizer.main.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.return_value = False

        result = await summarize_paper("test-paper-123")

        assert result is False
        mock_service.close.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_paper_exception():  # type: ignore
    """論文要約例外テスト."""
    with patch('refnet_summarizer.main.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.side_effect = Exception("Test error")

        with pytest.raises(Exception):  # type: ignore  # noqa: B017
            await summarize_paper("test-paper-123")

        mock_service.close.assert_called_once()


def test_main_no_args():  # type: ignore
    """引数なしテスト."""
    with patch.object(sys, 'argv', ['refnet-summarizer']):  # type: ignore
        with patch('builtins.print') as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            mock_print.assert_called()


def test_main_summarize_success():  # type: ignore
    """要約コマンド成功テスト."""
    with patch.object(sys, 'argv', ['refnet-summarizer', 'summarize', 'test-paper-123']):  # type: ignore
        with patch('asyncio.run', return_value=True) as mock_run:
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                mock_run.assert_called_once()
                mock_print.assert_called_with("Successfully summarized paper: test-paper-123")


def test_main_summarize_failure():  # type: ignore
    """要約コマンド失敗テスト."""
    with patch.object(sys, 'argv', ['refnet-summarizer', 'summarize', 'test-paper-123']):  # type: ignore
        with patch('asyncio.run', return_value=False) as mock_run:
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1
                mock_run.assert_called_once()
                mock_print.assert_called_with("Failed to summarize paper: test-paper-123")


def test_main_summarize_no_paper_id():  # type: ignore
    """要約コマンドで論文IDなしテスト."""
    with patch.object(sys, 'argv', ['refnet-summarizer', 'summarize']):  # type: ignore
        with patch('builtins.print') as mock_print:
            # asyncio.runが呼ばれないようにパッチを当てる
            with patch('asyncio.run') as mock_run:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1
                mock_print.assert_called_with("Usage: refnet-summarizer summarize <paper_id>")
                # asyncio.runは呼ばれない
                mock_run.assert_not_called()


def test_main_unknown_command():  # type: ignore
    """不明なコマンドテスト."""
    with patch.object(sys, 'argv', ['refnet-summarizer', 'unknown']):  # type: ignore
        with patch('builtins.print') as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            mock_print.assert_called_with("Unknown command: unknown")
