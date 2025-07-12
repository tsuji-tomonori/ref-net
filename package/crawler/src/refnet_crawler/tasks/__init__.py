"""Celeryタスク定義."""

import asyncio
from typing import Any

import structlog
from celery import Celery
from refnet_shared.config.environment import load_environment_settings

from refnet_crawler.services.crawler_service import CrawlerService

logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# Celeryアプリケーション
celery_app = Celery(
    "refnet_crawler",
    broker=settings.celery_broker_url or settings.redis.url,
    backend=settings.celery_result_backend or settings.redis.url,
    include=["refnet_crawler.tasks"]
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1時間
    task_soft_time_limit=3300,  # 55分
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(bind=True, name="refnet.crawler.crawl_paper")  # type: ignore[misc]
def crawl_paper_task(self: Any, paper_id: str, hop_count: int = 0, max_hops: int = 3) -> bool:
    """論文クローリングタスク."""
    logger.info("Starting paper crawl task", paper_id=paper_id, hop_count=hop_count)

    async def _crawl() -> bool:
        crawler = CrawlerService()
        try:
            return await crawler.crawl_paper(paper_id, hop_count, max_hops)
        finally:
            await crawler.close()

    try:
        result = asyncio.run(_crawl())
        logger.info("Paper crawl task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Paper crawl task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3) from e


@celery_app.task(name="refnet.crawler.batch_crawl")  # type: ignore[misc]
def batch_crawl_task(paper_ids: list[str], hop_count: int = 0, max_hops: int = 3) -> dict:
    """バッチクローリングタスク."""
    logger.info("Starting batch crawl task", paper_count=len(paper_ids))

    results = {}
    for paper_id in paper_ids:
        # 個別タスクとして実行
        result = crawl_paper_task.delay(paper_id, hop_count, max_hops)
        results[paper_id] = result.id

    return results
