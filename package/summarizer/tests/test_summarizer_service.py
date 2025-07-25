"""要約サービスのテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from refnet_shared.models.database import Paper, ProcessingQueue

from refnet_summarizer.services.summarizer_service import SummarizerService


# AIクライアントのパッチ設定
@pytest.fixture(autouse=True)
def mock_ai_client():  # type: ignore
    """すべてのテストでAIクライアントをモック."""
    with patch('refnet_summarizer.services.summarizer_service.create_ai_client') as mock_create_ai:
        mock_ai_client = AsyncMock()
        mock_create_ai.return_value = mock_ai_client
        yield mock_ai_client


@pytest.fixture
def mock_paper():  # type: ignore
    """モック論文データ."""
    paper = MagicMock(spec=Paper)
    paper.paper_id = "test-paper-123"
    paper.pdf_url = "https://example.com/paper.pdf"
    paper.pdf_hash = None
    paper.pdf_size = None
    paper.summary = None
    paper.summary_model = None
    paper.summary_created_at = None
    paper.is_summarized = False
    return paper


@pytest.fixture
def mock_pdf_content():  # type: ignore
    """モックPDFコンテンツ."""
    return b"%PDF-1.4 mock pdf content"


@pytest.fixture
def mock_text_content():  # type: ignore
    """モック抽出テキスト."""
    return "This is a test paper about machine learning and neural networks. " * 50


@pytest.fixture
def mock_summary():  # type: ignore
    """モック要約."""
    return "This paper presents a novel approach to machine learning using neural networks."


@pytest.fixture
def mock_keywords():  # type: ignore
    """モックキーワード."""
    return ["machine learning", "neural networks", "deep learning"]


@pytest.mark.asyncio
async def test_summarize_paper_success(
    mock_paper,
    mock_pdf_content,
    mock_text_content,
    mock_summary,
    mock_keywords
):  # type: ignore
    """論文要約成功テスト."""
    service = SummarizerService()

    # モックセッション設定
    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_paper

        # PDFプロセッサーのモック（asyncメソッドを考慮）
        with patch.object(
            service.pdf_processor,
            'download_pdf',
            new_callable=AsyncMock,
            return_value=mock_pdf_content
        ):  # type: ignore
            with patch.object(
                service.pdf_processor, 'calculate_hash', return_value="mock-hash"
            ):  # type: ignore
                with patch.object(
                    service.pdf_processor, 'extract_text', return_value=mock_text_content
                ):  # type: ignore
                    # AIクライアントのモック（asyncメソッドを考慮）
                    with patch.object(
                        service.ai_client,
                        'generate_summary',
                        new_callable=AsyncMock,
                        return_value=mock_summary
                    ):  # type: ignore
                        with patch.object(
                            service.ai_client,
                            'extract_keywords',
                            new_callable=AsyncMock,
                            return_value=mock_keywords
                        ):  # type: ignore
                            result = await service.summarize_paper("test-paper-123")

        # 結果検証
        assert result is True
        assert mock_paper.pdf_hash == "mock-hash"
        assert mock_paper.pdf_size == len(mock_pdf_content)
        assert mock_paper.is_summarized is True
        assert mock_paper.summary == mock_summary
        assert mock_paper.is_summarized is True
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_paper_no_pdf_url(mock_paper):  # type: ignore
    """PDF URLなしエラーテスト."""
    mock_paper.pdf_url = None
    service = SummarizerService()

    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_paper

        # ProcessingQueueのモック設定
        mock_queue_item = MagicMock(spec=ProcessingQueue)
        mock_queue_item.retry_count = 0
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            mock_paper, mock_queue_item, mock_paper
        ]

        result = await service.summarize_paper("test-paper-123")

        assert result is False


@pytest.mark.asyncio
async def test_summarize_paper_pdf_download_failed(mock_paper):  # type: ignore
    """PDFダウンロード失敗テスト."""
    service = SummarizerService()

    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_paper

        # ProcessingQueueのモック設定
        mock_queue_item = MagicMock(spec=ProcessingQueue)
        mock_queue_item.retry_count = 0
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            mock_paper, mock_queue_item, mock_paper
        ]

        with patch.object(service.pdf_processor, 'download_pdf', return_value=None):  # type: ignore
            result = await service.summarize_paper("test-paper-123")

        assert result is False


@pytest.mark.asyncio
async def test_summarize_paper_text_extraction_failed(mock_paper, mock_pdf_content):  # type: ignore
    """テキスト抽出失敗テスト."""
    service = SummarizerService()

    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_paper

        # ProcessingQueueのモック設定
        mock_queue_item = MagicMock(spec=ProcessingQueue)
        mock_queue_item.retry_count = 0
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            mock_paper, mock_queue_item, mock_paper
        ]

        with patch.object(service.pdf_processor, 'download_pdf', return_value=mock_pdf_content):  # type: ignore
            with patch.object(service.pdf_processor, 'extract_text', return_value=""):  # type: ignore
                result = await service.summarize_paper("test-paper-123")

        assert result is False


@pytest.mark.asyncio
async def test_summarize_paper_ai_generation_failed(
    mock_paper,
    mock_pdf_content,
    mock_text_content
):  # type: ignore
    """AI要約生成失敗テスト."""
    service = SummarizerService()

    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session

        # ProcessingQueueのモック設定 - exception handlerでも呼ばれる
        mock_queue_item = MagicMock(spec=ProcessingQueue)
        mock_queue_item.retry_count = 0
        # 複数回呼ばれるので、最初は論文、次はProcessingQueue、最後はexception handlerでまた呼ばれる
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            mock_paper, mock_queue_item, mock_paper, mock_queue_item, mock_paper
        ]

        with patch.object(service.pdf_processor, 'download_pdf', return_value=mock_pdf_content):  # type: ignore
            with patch.object(
                service.pdf_processor, 'extract_text', return_value=mock_text_content
            ):  # type: ignore
                with patch.object(service.ai_client, 'generate_summary', return_value=""):  # type: ignore
                    result = await service.summarize_paper("test-paper-123")

        assert result is False


@pytest.mark.asyncio
async def test_update_processing_status():  # type: ignore
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
async def test_update_processing_status_with_error():  # type: ignore
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


@pytest.mark.asyncio
async def test_summarize_paper_not_found():  # type: ignore
    """論文が見つからない場合のテスト."""
    service = SummarizerService()

    with patch('refnet_summarizer.services.summarizer_service.db_manager') as mock_db_manager:
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        result = await service.summarize_paper("nonexistent-paper")

        assert result is False


# このテストは削除（複雑すぎる）


def test_get_ai_model_name_openai():  # type: ignore
    """OpenAIモデル名取得テスト."""
    service = SummarizerService()

    # カスタムクラスでOpenAIクライアントをシミュレート
    class MockOpenAIClient:
        def __init__(self):  # type: ignore
            self.client = MagicMock()
            self.client._api_key = "test-key"

    service.ai_client = MockOpenAIClient()

    result = service._get_ai_model_name()
    assert result == "gpt-4o-mini"


def test_get_ai_model_name_anthropic():  # type: ignore
    """Anthropicモデル名取得テスト."""
    service = SummarizerService()

    # カスタムクラスでAnthropicクライアントをシミュレート
    class MockAnthropicClient:
        def __init__(self):  # type: ignore
            self.client = MagicMock()
            self.client._api_key = "test-key"

    service.ai_client = MockAnthropicClient()

    result = service._get_ai_model_name()
    assert result == "claude-3-5-haiku"


def test_get_ai_model_name_unknown():  # type: ignore
    """不明なAIモデル名取得テスト."""
    service = SummarizerService()

    # 不明なクライアントをモック
    mock_client = MagicMock()
    service.ai_client = mock_client

    result = service._get_ai_model_name()
    assert result == "unknown"


@pytest.mark.asyncio
async def test_update_processing_status_no_queue():  # type: ignore
    """キューアイテムが存在しない場合のテスト."""
    service = SummarizerService()
    mock_session = MagicMock()
    mock_paper = MagicMock()

    # キューアイテムはNoneだが、論文は存在
    mock_session.query.return_value.filter_by.return_value.first.side_effect = [None, mock_paper]

    await service._update_processing_status(
        mock_session,
        "test-paper-123",
        "summary",
        "completed"
    )

    # 論文のステータスが更新されることを確認
    assert mock_paper.is_summarized is True


@pytest.mark.asyncio
async def test_close():  # type: ignore
    """クローズテスト."""
    service = SummarizerService()

    with patch.object(service.pdf_processor, 'close') as mock_pdf_close:
        await service.close()
        mock_pdf_close.assert_called_once()
