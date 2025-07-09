"""監視システムテスト."""

import pytest
import requests
import time
from urllib.parse import urljoin


class TestMonitoring:
    """監視システムテスト."""

    PROMETHEUS_URL = "http://localhost:9090"
    GRAFANA_URL = "http://localhost:3000"
    KIBANA_URL = "http://localhost:5601"
    ELASTICSEARCH_URL = "http://localhost:9200"

    def test_prometheus_health(self):
        """Prometheusヘルスチェック."""
        response = requests.get(f"{self.PROMETHEUS_URL}/-/healthy")
        assert response.status_code == 200

    def test_prometheus_metrics(self):
        """Prometheusメトリクス収集確認."""
        response = requests.get(f"{self.PROMETHEUS_URL}/api/v1/query",
                              params={"query": "up"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["data"]["result"]) > 0

    def test_grafana_health(self):
        """Grafanaヘルスチェック."""
        response = requests.get(f"{self.GRAFANA_URL}/api/health")
        assert response.status_code == 200

    def test_elasticsearch_health(self):
        """Elasticsearchヘルスチェック."""
        response = requests.get(f"{self.ELASTICSEARCH_URL}/_health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["green", "yellow"]

    def test_kibana_health(self):
        """Kibanaヘルスチェック."""
        response = requests.get(f"{self.KIBANA_URL}/api/status")
        assert response.status_code == 200

    def test_metrics_collection(self):
        """メトリクス収集確認."""
        # APIリクエストを発生
        requests.get("http://localhost/api/health")

        # メトリクスが収集されるまで少し待機
        time.sleep(5)

        # Prometheusでメトリクス確認
        response = requests.get(
            f"{self.PROMETHEUS_URL}/api/v1/query",
            params={"query": "refnet_http_requests_total"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @pytest.mark.slow
    def test_log_ingestion(self):
        """ログ取り込み確認."""
        # ログ生成のためAPIを呼び出し
        requests.get("http://localhost/api/health")

        # ログが取り込まれるまで待機
        time.sleep(30)

        # Elasticsearchでログ確認
        response = requests.get(
            f"{self.ELASTICSEARCH_URL}/refnet-logs-*/_search",
            json={"query": {"match_all": {}}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hits"]["total"]["value"] > 0
