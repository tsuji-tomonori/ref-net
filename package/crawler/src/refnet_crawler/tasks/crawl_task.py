"""論文クローリング関連タスク."""

from typing import Any

import structlog
from refnet_shared.celery_app import app as celery_app
from refnet_shared.models.database import Paper
from refnet_shared.models.database_manager import db_manager

from refnet_crawler.clients.semantic_scholar import SemanticScholarClient

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, name="refnet_crawler.tasks.crawl_task.check_and_crawl_new_papers")  # type: ignore[misc]
def check_and_crawl_new_papers(self: Any) -> dict:
    """新しい論文をチェックしてクロール."""
    try:
        with db_manager.get_session() as session:
            # 未処理の論文を取得
            pending_papers = (
                session.query(Paper)
                .filter(Paper.is_crawled.is_(False))
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


@celery_app.task(bind=True, name='refnet_crawler.tasks.crawl_task.crawl_paper')  # type: ignore[misc]
def crawl_paper(self: Any, paper_id: str) -> dict:
    """論文をクロールし、次の処理をトリガー"""
    import asyncio

    async def _crawl_paper_async() -> dict:
        try:
            with db_manager.get_session() as session:
                paper = session.query(Paper).filter(Paper.paper_id == paper_id).first()
                if not paper:
                    raise ValueError(f"Paper {paper_id} not found")

                # Semantic Scholar APIから論文情報を取得
                client = SemanticScholarClient()
                paper_data = await client.get_paper(paper_id)
                if not paper_data:
                    raise ValueError(f"Failed to fetch paper data for {paper_id}")

                # 論文情報を更新
                paper.title = paper_data.title or paper.title
                paper.abstract = paper_data.abstract or paper.abstract
                paper.year = paper_data.year or paper.year
                paper.citation_count = paper_data.citationCount or paper.citation_count
                paper.reference_count = paper_data.referenceCount or paper.reference_count
                paper.is_crawled = True

                session.commit()

                # 要約タスクをトリガー
                celery_app.send_task(
                    'refnet_summarizer.tasks.summarize_task.summarize_paper',
                    args=[paper.paper_id],
                    queue='summarizer'
                )

                result = {
                    'status': 'success',
                    'paper_id': paper.paper_id,
                    'title': paper.title,
                    'citation_count': paper_data.citationCount or 0,
                    'reference_count': paper_data.referenceCount or 0
                }

                logger.info("Paper crawl completed", **result)
                return result

        except Exception as e:
            logger.error("Paper crawl failed", paper_id=paper_id, error=str(e))
            raise e

    try:
        return asyncio.run(_crawl_paper_async())
    except Exception as e:
        logger.error("Paper crawl failed", paper_id=paper_id, error=str(e))
        self.retry(exc=e, countdown=60, max_retries=3)
        return {}
