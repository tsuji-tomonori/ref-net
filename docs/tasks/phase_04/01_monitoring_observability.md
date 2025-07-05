# Task: 監視・可観測性システム構築

## タスクの目的

Prometheus・Grafana・ELK Stackを使用して包括的な監視・ログ・メトリクス収集システムを構築し、RefNetシステムの健全性とパフォーマンスを可視化する。

## 前提条件

- Phase 4の00_docker_setup.md が完了している
- Docker環境が正常稼働
- 全サービスがコンテナ化済み
- ヘルスチェックエンドポイントが利用可能

## 実施内容

### 1. Docker Composeに監視サービス追加

#### docker-compose.monitoring.yml

```yaml
version: '3.8'

services:
  # Prometheus メトリクス収集
  prometheus:
    image: prom/prometheus:latest
    container_name: refnet-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./monitoring/prometheus/rules:/etc/prometheus/rules
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
      - '--web.enable-admin-api'
    networks:
      - refnet

  # Grafana 可視化
  grafana:
    image: grafana/grafana:latest
    container_name: refnet-grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
      GF_USERS_ALLOW_SIGN_UP: false
    volumes:
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus
    networks:
      - refnet

  # Elasticsearch ログ保存
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: refnet-elasticsearch
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    networks:
      - refnet

  # Logstash ログ処理
  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    container_name: refnet-logstash
    ports:
      - "5000:5000"
      - "9600:9600"
    volumes:
      - ./monitoring/logstash/pipeline:/usr/share/logstash/pipeline
      - ./monitoring/logstash/config:/usr/share/logstash/config
    environment:
      LS_JAVA_OPTS: "-Xmx256m -Xms256m"
    depends_on:
      - elasticsearch
    networks:
      - refnet

  # Kibana ログ可視化
  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    container_name: refnet-kibana
    ports:
      - "5601:5601"
    environment:
      ELASTICSEARCH_HOSTS: http://elasticsearch:9200
    depends_on:
      - elasticsearch
    networks:
      - refnet

  # Node Exporter システムメトリクス
  node-exporter:
    image: prom/node-exporter:latest
    container_name: refnet-node-exporter
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    networks:
      - refnet

  # Alertmanager アラート管理
  alertmanager:
    image: prom/alertmanager:latest
    container_name: refnet-alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./monitoring/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    networks:
      - refnet

volumes:
  prometheus_data:
  grafana_data:
  elasticsearch_data:
  alertmanager_data:

networks:
  refnet:
    external: true
```

### 2. Prometheus設定

#### monitoring/prometheus/prometheus.yml

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "rules/*.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  # Prometheus自体の監視
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # システムメトリクス
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  # RefNet APIサービス
  - job_name: 'refnet-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: /metrics
    scrape_interval: 30s

  # PostgreSQL
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']
    metrics_path: /metrics

  # Redis
  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  # Nginx
  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx:80']
    metrics_path: /nginx_status

  # Celery Workers
  - job_name: 'celery-flower'
    static_configs:
      - targets: ['flower:5555']
    metrics_path: /api/workers
```

#### monitoring/prometheus/rules/refnet_alerts.yml

```yaml
groups:
  - name: refnet_alerts
    rules:
      # API サービスアラート
      - alert: APIServiceDown
        expr: up{job="refnet-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "RefNet API service is down"
          description: "API service has been down for more than 1 minute"

      - alert: HighAPIResponseTime
        expr: http_request_duration_seconds{quantile="0.95"} > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API response time"
          description: "95th percentile response time is {{ $value }}s"

      # データベースアラート
      - alert: DatabaseDown
        expr: up{job="postgres"} == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "PostgreSQL database is down"
          description: "Database has been unreachable for more than 30 seconds"

      - alert: HighDatabaseConnections
        expr: pg_stat_database_numbackends > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High database connection count"
          description: "Database has {{ $value }} active connections"

      # システムリソースアラート
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value }}%"

      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}%"

      - alert: LowDiskSpace
        expr: (1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100 > 90
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Low disk space"
          description: "Disk usage is {{ $value }}%"

      # Celeryワーカーアラート
      - alert: CeleryWorkerDown
        expr: flower_workers{state="ONLINE"} < 1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Celery worker is down"
          description: "No online Celery workers detected"

      - alert: HighTaskFailureRate
        expr: rate(celery_task_total{state="FAILURE"}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High task failure rate"
          description: "Task failure rate is {{ $value }} tasks/sec"
```

### 3. Grafana設定

#### monitoring/grafana/provisioning/datasources/prometheus.yml

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Elasticsearch
    type: elasticsearch
    access: proxy
    url: http://elasticsearch:9200
    database: "refnet-logs-*"
    timeField: "@timestamp"
```

#### monitoring/grafana/provisioning/dashboards/dashboard.yml

```yaml
apiVersion: 1

providers:
  - name: 'RefNet Dashboards'
    orgId: 1
    folder: 'RefNet'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

### 4. アプリケーションメトリクス実装

#### package/shared/src/refnet_shared/utils/metrics.py

```python
"""アプリケーションメトリクス."""

from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
import structlog
import time


logger = structlog.get_logger(__name__)

# メトリクス定義
REQUEST_COUNT = Counter(
    'refnet_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'refnet_http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

TASK_COUNT = Counter(
    'refnet_celery_tasks_total',
    'Total Celery tasks',
    ['task_name', 'state']
)

TASK_DURATION = Histogram(
    'refnet_celery_task_duration_seconds',
    'Celery task duration',
    ['task_name']
)

PAPER_COUNT = Gauge(
    'refnet_papers_total',
    'Total papers in database'
)

PAPER_STATUS_COUNT = Gauge(
    'refnet_papers_by_status',
    'Papers by processing status',
    ['status_type', 'status']
)

ACTIVE_CONNECTIONS = Gauge(
    'refnet_db_connections_active',
    'Active database connections'
)


class MetricsCollector:
    """メトリクス収集クラス."""

    @staticmethod
    def track_request(method: str, endpoint: str, status_code: int, duration: float) -> None:
        """HTTPリクエストメトリクス記録."""
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status_code)).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

    @staticmethod
    def track_task(task_name: str, state: str, duration: float = None) -> None:
        """Celeryタスクメトリクス記録."""
        TASK_COUNT.labels(task_name=task_name, state=state).inc()
        if duration is not None:
            TASK_DURATION.labels(task_name=task_name).observe(duration)

    @staticmethod
    def update_paper_counts(total: int, status_counts: Dict[str, Dict[str, int]]) -> None:
        """論文数メトリクス更新."""
        PAPER_COUNT.set(total)

        for status_type, counts in status_counts.items():
            for status, count in counts.items():
                PAPER_STATUS_COUNT.labels(status_type=status_type, status=status).set(count)

    @staticmethod
    def update_db_connections(count: int) -> None:
        """データベース接続数更新."""
        ACTIVE_CONNECTIONS.set(count)

    @staticmethod
    def get_metrics() -> bytes:
        """Prometheusメトリクス取得."""
        return generate_latest()


# FastAPI用ミドルウェア
class PrometheusMiddleware:
    """Prometheusメトリクス収集ミドルウェア."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = time.time() - start_time

                MetricsCollector.track_request(
                    method=scope["method"],
                    endpoint=scope["path"],
                    status_code=status_code,
                    duration=duration
                )

            await send(message)

        await self.app(scope, receive, send_wrapper)
```

### 5. Logstash設定

#### monitoring/logstash/pipeline/refnet.conf

```ruby
input {
  beats {
    port => 5044
  }

  tcp {
    port => 5000
    codec => json
  }
}

filter {
  if [fields][service] {
    mutate {
      add_field => { "service" => "%{[fields][service]}" }
    }
  }

  # 構造化ログの解析
  if [message] =~ /^\{/ {
    json {
      source => "message"
    }
  }

  # タイムスタンプの正規化
  date {
    match => [ "timestamp", "ISO8601" ]
  }

  # ログレベルの正規化
  mutate {
    uppercase => [ "level" ]
  }

  # エラーログの特別処理
  if [level] == "ERROR" {
    mutate {
      add_tag => [ "error" ]
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "refnet-logs-%{+YYYY.MM.dd}"
  }

  # デバッグ用（開発環境のみ）
  if [@metadata][debug] {
    stdout {
      codec => rubydebug
    }
  }
}
```

### 6. Alertmanager設定

#### monitoring/alertmanager/alertmanager.yml

```yaml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@refnet.local'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
  - name: 'web.hook'
    webhook_configs:
      - url: 'http://localhost:5001/alerts'
        send_resolved: true

  - name: 'email'
    email_configs:
      - to: 'admin@refnet.local'
        subject: '[RefNet Alert] {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          {{ end }}

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

### 7. 統合テスト

#### tests/test_monitoring.py

```python
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
```

## スコープ

- Prometheus・Grafanaによるメトリクス監視
- ELK Stackによるログ集約・分析
- アラート・通知システム
- アプリケーションメトリクス統合
- 基本的な監視テスト

**スコープ外:**
- APM（Application Performance Monitoring）
- 分散トレーシング
- 高度なログ分析・機械学習
- 外部監視サービス統合

## 参照するドキュメント

- `/docs/monitoring/metrics.md`
- `/docs/monitoring/alerting.md`
- `/docs/development/coding-standards.md`

## 完了条件

### 必須条件
- [ ] Prometheus・Grafanaが正常稼働
- [ ] ELK Stackが正常稼働
- [ ] アプリケーションメトリクス収集
- [ ] アラート設定が動作
- [ ] ダッシュボードが表示
- [ ] ログ収集・可視化が動作

### 監視条件
- [ ] システムメトリクス（CPU・メモリ・ディスク）収集
- [ ] アプリケーションメトリクス（レスポンス時間・エラー率）収集
- [ ] データベースメトリクス収集
- [ ] ログの構造化・集約
- [ ] アラートルールが適切に設定

### テスト条件
- [ ] 監視システムのテストが作成されている
- [ ] メトリクス収集が確認されている
- [ ] ログ取り込みが確認されている
- [ ] アラート動作が確認されている

## トラブルシューティング

### よくある問題

1. **メトリクス収集失敗**
   - 解決策: ターゲット設定、エンドポイント疎通を確認

2. **ログ取り込み失敗**
   - 解決策: Logstash設定、Elasticsearch容量を確認

3. **Grafanaダッシュボード表示エラー**
   - 解決策: データソース設定、クエリ構文を確認

4. **アラート通知失敗**
   - 解決策: Alertmanager設定、通知先設定を確認

## 次のタスクへの引き継ぎ

### 02_security_configuration.md への前提条件
- 監視システムが正常稼働
- メトリクス・ログ収集が動作
- セキュリティ監視ベースが整備済み

### 引き継ぎファイル
- `monitoring/` - 監視設定ディレクトリ
- `docker-compose.monitoring.yml` - 監視サービス定義
- Prometheusメトリクス・アラート設定
- Grafanaダッシュボード設定
