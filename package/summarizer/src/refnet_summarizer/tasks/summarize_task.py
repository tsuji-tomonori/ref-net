"""要約生成関連タスク."""

import asyncio
from typing import Any

import structlog
from refnet_shared.models.database import Paper
from refnet_shared.models.database_manager import db_manager
from sqlalchemy import and_

from refnet_summarizer.celery_app import celery_app
from refnet_summarizer.services.summarizer_service import SummarizerService

logger = structlog.get_logger(__name__)


@celery_app.task(
    bind=True, name="refnet_summarizer.tasks.summarize_task.process_pending_summarizations"
)  # type: ignore[misc]
def process_pending_summarizations(self: Any) -> dict:
    """保留中の要約処理を実行."""
    try:
        with db_manager.get_session() as session:
            # 要約待ちの論文を取得
            pending_papers = (
                session.query(Paper)
                .filter(
                    and_(
                        Paper.crawl_status == "completed",
                        Paper.summary_status == "pending",
                    )
                )
                .limit(5)
                .all()
            )

            for paper in pending_papers:
                # 非同期で要約タスクを起動
                summarize_paper.apply_async(args=[paper.paper_id], queue="summarizer")

            result = {
                "status": "success",
                "scheduled_papers": len(pending_papers),
            }

            logger.info("Scheduled summarization tasks", **result)
            return result

    except Exception as e:
        logger.error("Failed to process pending summarizations", error=str(e))
        self.retry(exc=e, countdown=60, max_retries=3)
        return {}


@celery_app.task(bind=True, name="refnet_summarizer.tasks.summarize_task.summarize_paper")  # type: ignore[misc]
def summarize_paper(self: Any, paper_id: str) -> bool:
    """論文要約タスク."""
    logger.info("Starting paper summarization task", paper_id=paper_id)

    async def _summarize() -> bool:
        summarizer = SummarizerService()
        try:
            return await summarizer.summarize_paper(paper_id)
        finally:
            # SummarizerServiceのcloseメソッドが存在しない場合は省略
            pass

    try:
        result = asyncio.run(_summarize())
        logger.info("Paper summarization task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Paper summarization task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3) from e
