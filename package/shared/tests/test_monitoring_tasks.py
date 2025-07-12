"""モニタリングタスクのテスト."""

from unittest.mock import MagicMock, patch

import httpx

from refnet_shared.tasks.monitoring import health_check_all_services


class TestMonitoringTasks:
    """モニタリングタスクのテストクラス."""

    @patch("refnet_shared.tasks.monitoring.httpx.get")
    def test_health_check_all_services_success(self, mock_get: MagicMock) -> None:
        """health_check_all_services正常系テスト."""
        # 正常なレスポンスをモック
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_get.return_value = mock_response

        # タスクを実行
        result = health_check_all_services()

        # 結果の検証
        assert "timestamp" in result
        assert "api" in result
        assert result["api"]["status"] == "healthy"
        assert result["api"]["status_code"] == 200
        assert result["api"]["response_time"] == 0.1

        # 全サービスが含まれているか確認
        for service in ["api", "crawler", "summarizer", "generator"]:
            assert service in result
            assert result[service]["status"] == "healthy"

    @patch("refnet_shared.tasks.monitoring.httpx.get")
    def test_health_check_all_services_partial_failure(self, mock_get: MagicMock) -> None:
        """health_check_all_services一部失敗テスト."""
        # APIは正常、他は異常
        def side_effect(url: str, timeout: float) -> MagicMock:
            mock_response = MagicMock()
            if "api" in url:
                mock_response.status_code = 200
                mock_response.elapsed.total_seconds.return_value = 0.1
            else:
                mock_response.status_code = 500
                mock_response.elapsed.total_seconds.return_value = 0.5
            return mock_response

        mock_get.side_effect = side_effect

        # タスクを実行
        result = health_check_all_services()

        # 結果の検証
        assert result["api"]["status"] == "healthy"
        assert result["crawler"]["status"] == "unhealthy"
        assert result["summarizer"]["status"] == "unhealthy"
        assert result["generator"]["status"] == "unhealthy"

    @patch("refnet_shared.tasks.monitoring.httpx.get")
    def test_health_check_all_services_exception(self, mock_get: MagicMock) -> None:
        """health_check_all_services例外発生テスト."""
        # タイムアウト例外を発生させる
        mock_get.side_effect = httpx.TimeoutException("Connection timeout")

        # タスクを実行
        result = health_check_all_services()

        # 結果の検証
        for service in ["api", "crawler", "summarizer", "generator"]:
            assert service in result
            assert result[service]["status"] == "error"
            assert "Connection timeout" in result[service]["error"]

    @patch("refnet_shared.tasks.monitoring.httpx.get")
    @patch("refnet_shared.tasks.monitoring.logger")
    def test_health_check_warning_log(self, mock_logger: MagicMock, mock_get: MagicMock) -> None:
        """health_check_all_services警告ログテスト."""
        # 一部サービスを異常にする
        def side_effect(url: str, timeout: float) -> MagicMock:
            mock_response = MagicMock()
            if "api" in url:
                mock_response.status_code = 200
            else:
                mock_response.status_code = 500
            mock_response.elapsed.total_seconds.return_value = 0.1
            return mock_response

        mock_get.side_effect = side_effect

        # タスクを実行
        health_check_all_services()

        # 警告ログが出力されたか確認
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "Unhealthy services detected"
        assert "services" in call_args[1]
        assert len(call_args[1]["services"]) == 3  # crawler, summarizer, generator
