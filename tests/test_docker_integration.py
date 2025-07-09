"""Docker統合テスト."""

import pytest
import time
import requests
from urllib.parse import urljoin


class TestDockerIntegration:
    """Docker環境統合テスト."""

    BASE_URL = "http://localhost"

    def test_nginx_health_check(self):
        """Nginxヘルスチェック."""
        response = requests.get(f"{self.BASE_URL}/health")
        assert response.status_code == 200
        assert "healthy" in response.text

    def test_api_health_check(self):
        """APIサービスヘルスチェック."""
        response = requests.get(f"{self.BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_api_root_endpoint(self):
        """APIルートエンドポイント."""
        response = requests.get(f"{self.BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "RefNet API" in data["message"]

    def test_flower_monitoring(self):
        """Flower監視システム."""
        response = requests.get(f"{self.BASE_URL}/flower/")
        assert response.status_code == 200

    def test_database_connection(self):
        """データベース接続テスト."""
        # APIを通じてデータベース接続確認
        response = requests.get(f"{self.BASE_URL}/api/v1/papers/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_redis_connection(self):
        """Redis接続テスト（Celeryタスク経由）."""
        # 簡単なタスクを送信して確認
        pass  # 実装はタスクエンドポイント次第

    @pytest.mark.slow
    def test_service_startup_time(self):
        """サービス起動時間テスト."""
        start_time = time.time()

        # 全サービスが利用可能になるまで待機
        services_ready = False
        max_wait = 120  # 2分

        while not services_ready and (time.time() - start_time) < max_wait:
            try:
                # 主要サービスの確認
                nginx_ok = requests.get(f"{self.BASE_URL}/health").status_code == 200
                api_ok = requests.get(f"{self.BASE_URL}/api/health").status_code == 200

                if nginx_ok and api_ok:
                    services_ready = True
                else:
                    time.sleep(5)

            except requests.exceptions.ConnectionError:
                time.sleep(5)

        assert services_ready, "Services did not start within expected time"
        startup_time = time.time() - start_time
        assert startup_time < max_wait
