"""論文クローリング関連タスク."""

import asyncio
from typing import Any

import structlog
from refnet_shared.models.database import Paper
from refnet_shared.models.database_manager import db_manager

from refnet_crawler.celery_app import celery_app
from refnet_crawler.services.crawler_service import CrawlerService

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, name="refnet_crawler.tasks.crawl_task.check_and_crawl_new_papers")
def check_and_crawl_new_papers(self: Any) -> dict:
    """新しい論文をチェックしてクロール."""
    try:
        with db_manager.get_session() as session:
            # 未処理の論文を取得
            pending_papers = (
                session.query(Paper)
                .filter(Paper.crawl_status == "pending")
                .limit(10)
                .all()
            )

            for paper in pending_papers:
                # 非同期でクロールタスクを起動
                crawl_paper.apply_async(args=[paper.paper_id], queue="crawler")

            result = {
                "status": "success",
                "scheduled_papers": len(pending_papers),
            }

            logger.info("Scheduled crawl tasks", **result)
            return result

    except Exception as e:
        logger.error("Failed to check and crawl new papers", error=str(e))
        self.retry(exc=e, countdown=60, max_retries=3)
        return {}


@celery_app.task(bind=True, name="refnet_crawler.tasks.crawl_task.crawl_paper")
def crawl_paper(self: Any, paper_id: str, hop_count: int = 0, max_hops: int = 3) -> bool:
    """論文クローリングタスク."""
    logger.info("Starting paper crawl task", paper_id=paper_id, hop_count=hop_count)

    async def _crawl() -> bool:
        crawler = CrawlerService()
        try:
            return await crawler.crawl_paper(paper_id, hop_count, max_hops)
        finally:
            # CrawlerServiceのcloseメソッドが存在しない場合は省略
            pass

    try:
        result = asyncio.run(_crawl())
        logger.info("Paper crawl task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Paper crawl task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3) from e
