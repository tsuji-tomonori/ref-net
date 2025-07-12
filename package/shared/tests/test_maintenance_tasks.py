"""メンテナンスタスクのテスト."""

from unittest.mock import MagicMock, patch

import pytest

from refnet_shared.tasks.maintenance import cleanup_old_data


class TestMaintenanceTasks:
    """メンテナンスタスクのテストクラス."""

    @patch("refnet_shared.tasks.maintenance.db_manager")
    def test_cleanup_old_data_success(self, mock_db_manager: MagicMock) -> None:
        """cleanup_old_data正常系テスト."""
        # モックセッションの設定
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session

        # 削除されたレコード数をモック
        mock_session.query.return_value.filter.return_value.delete.return_value = 5

        # タスクを実行
        result = cleanup_old_data()

        # 結果の検証
        assert result["status"] == "success"
        assert result["deleted_papers"] == 5
        assert result["orphan_authors"] == 5
        assert "timestamp" in result

        # コミットが呼ばれたか確認
        mock_session.commit.assert_called_once()

    @patch("refnet_shared.tasks.maintenance.db_manager")
    def test_cleanup_old_data_exception(self, mock_db_manager: MagicMock) -> None:
        """cleanup_old_data例外発生テスト."""
        # 例外を発生させる
        mock_db_manager.get_session.side_effect = Exception("Database error")

        # retryをモック
        with patch("refnet_shared.tasks.maintenance.cleanup_old_data.retry") as mock_retry:
            mock_retry.side_effect = Exception("Retry exception")

            with pytest.raises(Exception, match="Retry exception"):
                cleanup_old_data()

    @patch("refnet_shared.tasks.maintenance.db_manager")
    def test_cleanup_old_data_no_records(self, mock_db_manager: MagicMock) -> None:
        """cleanup_old_dataレコードなしテスト."""
        # モックセッションの設定
        mock_session = MagicMock()
        mock_db_manager.get_session.return_value.__enter__.return_value = mock_session

        # 削除されたレコード数を0に設定
        mock_session.query.return_value.filter.return_value.delete.return_value = 0

        # タスクを実行
        result = cleanup_old_data()

        # 結果の検証
        assert result["status"] == "success"
        assert result["deleted_papers"] == 0
        assert result["orphan_authors"] == 0
