"""アプリケーションメトリクス."""

import time
from typing import Any

import structlog
from prometheus_client import Counter, Gauge, Histogram, generate_latest

logger = structlog.get_logger(__name__)

# メトリクス定義
REQUEST_COUNT = Counter("refnet_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])

REQUEST_DURATION = Histogram("refnet_http_request_duration_seconds", "HTTP request duration", ["method", "endpoint"])

TASK_COUNT = Counter("refnet_celery_tasks_total", "Total Celery tasks", ["task_name", "state"])

TASK_DURATION = Histogram("refnet_celery_task_duration_seconds", "Celery task duration", ["task_name"])

PAPER_COUNT = Gauge("refnet_papers_total", "Total papers in database")

PAPER_STATUS_COUNT = Gauge("refnet_papers_by_status", "Papers by processing status", ["status_type", "status"])

ACTIVE_CONNECTIONS = Gauge("refnet_db_connections_active", "Active database connections")

# Celeryタスク専用メトリクス
CELERY_TASK_DURATION = Histogram(
    "celery_task_duration_seconds",
    "Celery task execution time",
    ["task_name", "status"]
)

CELERY_TASK_TOTAL = Counter(
    "celery_task_total",
    "Total number of Celery tasks",
    ["task_name", "status"]
)

CELERY_BEAT_SCHEDULE_RUNS = Counter(
    "celery_beat_schedule_runs_total",
    "Total scheduled task executions",
    ["schedule_name"]
)


class MetricsCollector:
    """メトリクス収集クラス."""

    @staticmethod
    def track_request(method: str, endpoint: str, status_code: int, duration: float) -> None:
        """HTTPリクエストメトリクス記録."""
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status_code)).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

    @staticmethod
    def track_task(task_name: str, state: str, duration: float | None = None) -> None:
        """Celeryタスクメトリクス記録."""
        TASK_COUNT.labels(task_name=task_name, state=state).inc()
        if duration is not None:
            TASK_DURATION.labels(task_name=task_name).observe(duration)

    @staticmethod
    def update_paper_counts(total: int, status_counts: dict[str, dict[str, int]]) -> None:
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
    def track_celery_task(task_name: str, status: str, duration: float | None = None) -> None:
        """Celeryタスク実行メトリクス記録."""
        CELERY_TASK_TOTAL.labels(task_name=task_name, status=status).inc()
        if duration is not None:
            CELERY_TASK_DURATION.labels(task_name=task_name, status=status).observe(duration)

    @staticmethod
    def track_beat_schedule(schedule_name: str) -> None:
        """Celery Beatスケジュール実行メトリクス記録."""
        CELERY_BEAT_SCHEDULE_RUNS.labels(schedule_name=schedule_name).inc()

    @staticmethod
    def get_metrics() -> bytes:
        """Prometheusメトリクス取得."""
        return generate_latest()


# FastAPI用ミドルウェア
class PrometheusMiddleware:
    """Prometheusメトリクス収集ミドルウェア."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = time.time() - start_time

                MetricsCollector.track_request(method=scope["method"], endpoint=scope["path"], status_code=status_code, duration=duration)

            await send(message)

        await self.app(scope, receive, send_wrapper)
