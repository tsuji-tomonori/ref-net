"""Markdown生成関連タスク."""

import asyncio
from typing import Any

import structlog
from refnet_shared.models.database import Paper
from refnet_shared.models.database_manager import db_manager
from sqlalchemy import and_

from refnet_generator.celery_app import celery_app
from refnet_generator.services.generator_service import GeneratorService

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, name="refnet_generator.tasks.generate_task.generate_pending_markdowns")
def generate_pending_markdowns(self: Any) -> dict:
    """保留中のMarkdown生成を実行."""
    try:
        with db_manager.get_session() as session:
            # Markdown生成待ちの論文を取得
            pending_papers = (
                session.query(Paper)
                .filter(
                    and_(
                        Paper.summary_status == "completed",
                        Paper.pdf_status != "completed",
                    )
                )
                .limit(10)
                .all()
            )

            for paper in pending_papers:
                # 非同期でMarkdown生成タスクを起動
                generate_markdown.apply_async(args=[paper.paper_id], queue="generator")

            result = {
                "status": "success",
                "scheduled_papers": len(pending_papers),
            }

            logger.info("Scheduled markdown generation tasks", **result)
            return result

    except Exception as e:
        logger.error("Failed to generate pending markdowns", error=str(e))
        self.retry(exc=e, countdown=60, max_retries=3)
        return {}


@celery_app.task(bind=True, name="refnet_generator.tasks.generate_task.generate_markdown")
def generate_markdown(self: Any, paper_id: str) -> bool:
    """Markdown生成タスク."""
    logger.info("Starting markdown generation task", paper_id=paper_id)

    async def _generate() -> bool:
        generator = GeneratorService()
        try:
            return await generator.generate_markdown(paper_id)
        finally:
            # GeneratorServiceのcloseメソッドが存在しない場合は省略
            pass

    try:
        result = asyncio.run(_generate())
        logger.info("Markdown generation task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Markdown generation task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3) from e
