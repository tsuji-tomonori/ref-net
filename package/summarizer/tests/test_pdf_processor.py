"""PDF処理のテスト."""

import pytest
from unittest.mock import AsyncMock, patch, mock_open
from refnet_summarizer.processors.pdf_processor import PDFProcessor


@pytest.fixture
def processor():
    """テスト用プロセッサー."""
    return PDFProcessor()


@pytest.fixture
def mock_pdf_content():
    """モックPDFコンテンツ."""
    return b"%PDF-1.4 mock pdf content"


@pytest.mark.asyncio
async def test_download_pdf_success(processor, mock_pdf_content):
    """PDF ダウンロード成功テスト."""
    with patch.object(processor.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.content = mock_pdf_content
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await processor.download_pdf("https://example.com/paper.pdf")

        assert result == mock_pdf_content


@pytest.mark.asyncio
async def test_download_pdf_invalid_content_type(processor):
    """PDF ダウンロード（無効なContent-Type）テスト."""
    with patch.object(processor.client, 'get') as mock_get:
        mock_response = AsyncMock()
        mock_response.content = b"not a pdf"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = await processor.download_pdf("https://example.com/notpdf.html")

        assert result is None


def test_calculate_hash(processor, mock_pdf_content):
    """ハッシュ計算テスト."""
    hash1 = processor.calculate_hash(mock_pdf_content)
    hash2 = processor.calculate_hash(mock_pdf_content)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256は64文字


def test_clean_text(processor):
    """テキストクリーニングテスト."""
    dirty_text = "Line 1\r\n\r\nLine 2\n\n\n\nLine 3    with   spaces"
    clean_text = processor._clean_text(dirty_text)

    assert "Line 1 Line 2 Line 3 with spaces" in clean_text
    assert "\r" not in clean_text
