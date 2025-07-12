"""要約生成関連タスク."""

from typing import Any

import structlog
from refnet_shared.celery_app import app as celery_app
from refnet_shared.models.database import Paper
from refnet_shared.models.database_manager import db_manager
from sqlalchemy import and_

from refnet_summarizer.services.ai_client import get_ai_client
from refnet_summarizer.services.pdf_processor import PDFProcessor

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


@celery_app.task(bind=True, name='refnet_summarizer.tasks.summarize_task.summarize_paper')
def summarize_paper(self: Any, paper_id: str) -> dict:
    """論文を要約し、次の処理をトリガー"""
    try:
        with db_manager.get_session() as session:
            paper = session.query(Paper).filter(Paper.paper_id == paper_id).first()
            if not paper:
                raise ValueError(f"Paper {paper_id} not found")

            if not paper.pdf_url:
                # PDFがない場合はスキップ
                paper.is_summarized = True
                paper.summary = "PDF not available"
                session.commit()

                # Markdown生成をトリガー
                celery_app.send_task(
                    'refnet_generator.tasks.generate_task.generate_markdown',
                    args=[paper.paper_id],
                    queue='generator'
                )
                return {'status': 'skipped', 'reason': 'no_pdf'}

            # PDFをダウンロードして処理
            pdf_processor = PDFProcessor()
            pdf_content = pdf_processor.download_pdf(paper.pdf_url)
            text_content = pdf_processor.extract_text(pdf_content)

            # AI要約を生成
            ai_client = get_ai_client()
            summary = ai_client.summarize(
                text_content,
                max_length=1000,
                language='japanese'
            )

            # 要約を保存
            paper.summary = summary
            paper.full_text = text_content[:50000]  # 最初の50,000文字を保存
            paper.is_summarized = True
            session.commit()

            # Markdown生成をトリガー
            celery_app.send_task(
                'refnet_generator.tasks.generate_task.generate_markdown',
                args=[paper.paper_id],
                queue='generator'
            )

            result = {
                'status': 'success',
                'paper_id': paper.paper_id,
                'summary_length': len(summary)
            }

            logger.info("Paper summarization completed", **result)
            return result

    except Exception as e:
        logger.error("Paper summarization failed", paper_id=paper_id, error=str(e))
        self.retry(exc=e, countdown=120, max_retries=3)
        return {}
