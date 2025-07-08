"""メインエントリーポイントのテスト."""

import asyncio
import sys
from unittest.mock import AsyncMock, patch

import pytest

from refnet_summarizer.main import main, summarize_paper


@pytest.mark.asyncio
async def test_summarize_paper_success():
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
async def test_summarize_paper_failure():
    """論文要約失敗テスト."""
    with patch('refnet_summarizer.main.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.return_value = False

        result = await summarize_paper("test-paper-123")

        assert result is False
        mock_service.close.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_paper_exception():
    """論文要約例外テスト."""
    with patch('refnet_summarizer.main.SummarizerService') as mock_service_class:
        mock_service = AsyncMock()
        mock_service_class.return_value = mock_service
        mock_service.summarize_paper.side_effect = Exception("Test error")

        with pytest.raises(Exception):
            await summarize_paper("test-paper-123")

        mock_service.close.assert_called_once()


def test_main_no_args():
    """引数なしテスト."""
    with patch.object(sys, 'argv', ['refnet-summarizer']):
        with patch('builtins.print') as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            mock_print.assert_called()


def test_main_summarize_success():
    """要約コマンド成功テスト."""
    with patch.object(sys, 'argv', ['refnet-summarizer', 'summarize', 'test-paper-123']):
        with patch('asyncio.run', return_value=True) as mock_run:
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                mock_run.assert_called_once()
                mock_print.assert_called_with("Successfully summarized paper: test-paper-123")


def test_main_summarize_failure():
    """要約コマンド失敗テスト."""
    with patch.object(sys, 'argv', ['refnet-summarizer', 'summarize', 'test-paper-123']):
        with patch('asyncio.run', return_value=False) as mock_run:
            with patch('builtins.print') as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1
                mock_run.assert_called_once()
                mock_print.assert_called_with("Failed to summarize paper: test-paper-123")


def test_main_summarize_no_paper_id():
    """要約コマンドで論文IDなしテスト."""
    with patch.object(sys, 'argv', ['refnet-summarizer', 'summarize']):
        with patch('builtins.print') as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            mock_print.assert_called_with("Usage: refnet-summarizer summarize <paper_id>")


def test_main_unknown_command():
    """不明なコマンドテスト."""
    with patch.object(sys, 'argv', ['refnet-summarizer', 'unknown']):
        with patch('builtins.print') as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1
            mock_print.assert_called_with("Unknown command: unknown")
