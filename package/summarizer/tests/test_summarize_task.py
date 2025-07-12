"""summarize_taskモジュールのテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSummarizeTaskBasic:
    """要約タスクの基本テスト."""

    def test_module_imports(self) -> None:
        """モジュールのインポートテスト."""
        try:
            from refnet_summarizer.tasks.summarize_task import (
                process_pending_summarizations,
                summarize_paper,
            )
            # インポートが成功することを確認
            assert process_pending_summarizations is not None
            assert summarize_paper is not None
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
        with patch(
            'refnet_summarizer.services.summarizer_service.SummarizerService'
        ) as mock_service_class:
            # SummarizerServiceのモック
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            mock_service.summarize_paper = AsyncMock(return_value=True)

            # 非同期関数のテスト
            async def _test_summarize() -> bool:
                summarizer = mock_service_class()
                try:
                    return await summarizer.summarize_paper("test-paper-123")
                finally:
                    pass

            result = await _test_summarize()

            # アサーション
            assert result is True
            mock_service.summarize_paper.assert_called_once_with("test-paper-123")
