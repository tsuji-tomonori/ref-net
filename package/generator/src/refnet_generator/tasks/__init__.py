"""Celeryタスク定義."""

import asyncio

import structlog
from celery import Celery
from refnet_shared.config.environment import load_environment_settings

from refnet_generator.services.generator_service import GeneratorService

logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# Celeryアプリケーション
celery_app = Celery(
    "refnet_generator",
    broker=settings.celery_broker_url or settings.redis.url,
    backend=settings.celery_result_backend or settings.redis.url,
    include=["refnet_generator.tasks"],
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10分
    task_soft_time_limit=540,  # 9分
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(bind=True, name="refnet.generator.generate_markdown")  # type: ignore[misc]
def generate_markdown_task(self: object, paper_id: str) -> bool:
    """Markdown生成タスク."""
    logger.info("Starting markdown generation task", paper_id=paper_id)

    async def _generate() -> bool:
        service = GeneratorService()
        return await service.generate_markdown(paper_id)

    try:
        result = asyncio.run(_generate())
        logger.info("Markdown generation task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Markdown generation task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=2) from e  # type: ignore[attr-defined]


@celery_app.task(name="refnet.generator.batch_generate")  # type: ignore[misc]
def batch_generate_task(paper_ids: list[str]) -> dict[str, str]:
    """バッチ生成タスク."""
    logger.info("Starting batch generation task", paper_count=len(paper_ids))

    results = {}
    for paper_id in paper_ids:
        result = generate_markdown_task.delay(paper_id)
        results[paper_id] = result.id

    return results
