"""要約サービスのテスト."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from refnet_summarizer.services.summarizer_service import SummarizerService
from refnet_shared.models.database import Paper, ProcessingQueue


@pytest.fixture
def mock_paper():
    """モック論文データ."""
    paper = MagicMock(spec=Paper)
    paper.paper_id = "test-paper-123"
    paper.pdf_url = "https://example.com/paper.pdf"
    paper.pdf_hash = None
    paper.pdf_size = None
    paper.pdf_status = None
    paper.summary = None
    paper.summary_model = None
    paper.summary_created_at = None
    paper.summary_status = None
    return paper


@pytest.fixture
def mock_pdf_content():
    """モックPDFコンテンツ."""
    return b"%PDF-1.4 mock pdf content"


@pytest.fixture
def mock_text_content():
    """モック抽出テキスト."""
    return "This is a test paper about machine learning and neural networks. " * 50


@pytest.fixture
def mock_summary():
    """モック要約."""
    return "This paper presents a novel approach to machine learning using neural networks."


@pytest.fixture
def mock_keywords():
    """モックキーワード."""
    return ["machine learning", "neural networks", "deep learning"]


@pytest.mark.asyncio
async def test_summarize_paper_success(
    mock_paper,
    mock_pdf_content,
    mock_text_content,
    mock_summary,
    mock_keywords
):
    """論文要約成功テスト."""
    service = SummarizerService()

    # モックセッション設定
    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_paper

        # PDFプロセッサーのモック
        with patch.object(service.pdf_processor, 'download_pdf', return_value=mock_pdf_content):
            with patch.object(service.pdf_processor, 'calculate_hash', return_value="mock-hash"):
                with patch.object(service.pdf_processor, 'extract_text', return_value=mock_text_content):
                    # AIクライアントのモック
                    with patch.object(service.ai_client, 'generate_summary', return_value=mock_summary):
                        with patch.object(service.ai_client, 'extract_keywords', return_value=mock_keywords):
                            result = await service.summarize_paper("test-paper-123")

        # 結果検証
        assert result is True
        assert mock_paper.pdf_hash == "mock-hash"
        assert mock_paper.pdf_size == len(mock_pdf_content)
        assert mock_paper.pdf_status == "completed"
        assert mock_paper.summary == mock_summary
        assert mock_paper.summary_status == "completed"
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_paper_no_pdf_url(mock_paper):
    """PDF URLなしエラーテスト."""
    mock_paper.pdf_url = None
    service = SummarizerService()

    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_paper

        result = await service.summarize_paper("test-paper-123")

        assert result is False


@pytest.mark.asyncio
async def test_summarize_paper_pdf_download_failed(mock_paper):
    """PDFダウンロード失敗テスト."""
    service = SummarizerService()

    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_paper

        with patch.object(service.pdf_processor, 'download_pdf', return_value=None):
            result = await service.summarize_paper("test-paper-123")

        assert result is False


@pytest.mark.asyncio
async def test_summarize_paper_text_extraction_failed(mock_paper, mock_pdf_content):
    """テキスト抽出失敗テスト."""
    service = SummarizerService()

    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_paper

        with patch.object(service.pdf_processor, 'download_pdf', return_value=mock_pdf_content):
            with patch.object(service.pdf_processor, 'extract_text', return_value=""):
                result = await service.summarize_paper("test-paper-123")

        assert result is False


@pytest.mark.asyncio
async def test_summarize_paper_ai_generation_failed(
    mock_paper,
    mock_pdf_content,
    mock_text_content
):
    """AI要約生成失敗テスト."""
    service = SummarizerService()

    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_paper

        with patch.object(service.pdf_processor, 'download_pdf', return_value=mock_pdf_content):
            with patch.object(service.pdf_processor, 'extract_text', return_value=mock_text_content):
                with patch.object(service.ai_client, 'generate_summary', return_value=""):
                    result = await service.summarize_paper("test-paper-123")

        assert result is False


@pytest.mark.asyncio
async def test_update_processing_status():
    """処理状態更新テスト."""
    service = SummarizerService()
    mock_session = MagicMock()
    mock_queue_item = MagicMock(spec=ProcessingQueue)
    mock_queue_item.status = "pending"
    mock_queue_item.retry_count = 0

    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_queue_item

    await service._update_processing_status(
        mock_session,
        "test-paper-123",
        "summary",
        "completed"
    )

    assert mock_queue_item.status == "completed"


@pytest.mark.asyncio
async def test_update_processing_status_with_error():
    """エラー付き処理状態更新テスト."""
    service = SummarizerService()
    mock_session = MagicMock()
    mock_queue_item = MagicMock(spec=ProcessingQueue)
    mock_queue_item.status = "pending"
    mock_queue_item.retry_count = 0

    mock_session.query.return_value.filter_by.return_value.first.return_value = mock_queue_item

    await service._update_processing_status(
        mock_session,
        "test-paper-123",
        "summary",
        "failed",
        "Test error message"
    )

    assert mock_queue_item.status == "failed"
    assert mock_queue_item.error_message == "Test error message"
    assert mock_queue_item.retry_count == 1
