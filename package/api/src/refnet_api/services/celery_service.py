"""Celery統合サービス."""

import structlog
from celery import Celery
from refnet_shared.config.environment import load_environment_settings

logger = structlog.get_logger(__name__)
settings = load_environment_settings()


class CeleryService:
    """Celery統合サービス."""

    def __init__(self) -> None:
        """初期化."""
        self.celery_app = Celery(
            "refnet",
            broker=settings.celery_broker_url or settings.redis.url,
            backend=settings.celery_result_backend or settings.redis.url,
        )

    def queue_crawl_task(self, paper_id: str) -> str:
        """クローリングタスクをキューに追加."""
        task = self.celery_app.send_task(
            "refnet.crawler.crawl_paper", args=[paper_id], queue="crawl"
        )
        return task.id

    def queue_summarize_task(self, paper_id: str) -> str:
        """要約タスクをキューに追加."""
        task = self.celery_app.send_task(
            "refnet.summarizer.summarize_paper", args=[paper_id], queue="summarize"
        )
        return task.id

    def queue_generate_task(self, paper_id: str) -> str:
        """生成タスクをキューに追加."""
        task = self.celery_app.send_task(
            "refnet.generator.generate_markdown", args=[paper_id], queue="generate"
        )
        return task.id

    def get_task_status(self, task_id: str) -> dict:
        """タスク状態取得."""
        task = self.celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": task.status,
            "result": task.result,
        }
