"""Celeryタスク定義."""

import asyncio

import structlog
from celery import Celery
from refnet_shared.config.environment import load_environment_settings

from refnet_summarizer.services.summarizer_service import SummarizerService

logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# Celeryアプリケーション
celery_app = Celery(
    "refnet_summarizer",
    broker=settings.celery_broker_url or settings.redis.url,
    backend=settings.celery_result_backend or settings.redis.url,
    include=["refnet_summarizer.tasks"],
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30分
    task_soft_time_limit=1500,  # 25分
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,  # メモリリーク対策
)


@celery_app.task(bind=True, name="refnet.summarizer.summarize_paper")
def summarize_paper_task(self, paper_id: str) -> bool:
    """論文要約タスク."""
    logger.info("Starting paper summarization task", paper_id=paper_id)

    async def _summarize():
        service = SummarizerService()
        try:
            return await service.summarize_paper(paper_id)
        finally:
            await service.close()

    try:
        result = asyncio.run(_summarize())
        logger.info("Paper summarization task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Paper summarization task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=300, max_retries=2) from e  # 5分後にリトライ


@celery_app.task(name="refnet.summarizer.batch_summarize")
def batch_summarize_task(paper_ids: list[str]) -> dict:
    """バッチ要約タスク."""
    logger.info("Starting batch summarization task", paper_count=len(paper_ids))

    results = {}
    for paper_id in paper_ids:
        # 個別タスクとして実行
        result = summarize_paper_task.delay(paper_id)
        results[paper_id] = result.id

    return results
