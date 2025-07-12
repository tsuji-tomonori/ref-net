"""論文クローリング関連タスク."""

import json
from typing import Any

import structlog
from refnet_shared.celery_app import app as celery_app
from refnet_shared.models.database import Paper
from refnet_shared.models.database_manager import db_manager
from refnet_shared.models.paper import Citation

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


@celery_app.task(bind=True, name='refnet_crawler.tasks.crawl_task.crawl_paper')  # type: ignore[misc]
def crawl_paper(self: Any, paper_id: str) -> dict:
    """論文をクロールし、次の処理をトリガー"""
    try:
        with db_manager.get_session() as session:
            paper = session.query(Paper).filter(Paper.paper_id == paper_id).first()
            if not paper:
                raise ValueError(f"Paper {paper_id} not found")

            # Semantic Scholar APIから論文情報を取得
            client = SemanticScholarClient()
            paper_data = client.get_paper(paper_id)

            # 論文情報を更新
            paper.title = paper_data['title']
            paper.abstract = paper_data['abstract']
            paper.authors = json.dumps(paper_data['authors'])
            paper.year = paper_data['year']
            paper.venue = paper_data['venue']
            paper.pdf_url = paper_data.get('openAccessPdf', {}).get('url')
            paper.is_crawled = True

            # 参照論文を追加
            for ref in paper_data.get('references', []):
                if ref.get('paperId'):
                    ref_paper = Paper(
                        paper_id=ref['paperId'],
                        title=ref.get('title', ''),
                        is_crawled=False,
                        is_summarized=False,
                        is_generated=False
                    )
                    session.merge(ref_paper)  # 既存の場合は更新

                    # 関係を作成
                    citation = Citation(
                        citing_paper_id=paper.paper_id,
                        cited_paper_id=ref['paperId']
                    )
                    session.merge(citation)

            # 被引用論文を追加
            for cit in paper_data.get('citations', []):
                if cit.get('paperId'):
                    cit_paper = Paper(
                        paper_id=cit['paperId'],
                        title=cit.get('title', ''),
                        is_crawled=False,
                        is_summarized=False,
                        is_generated=False
                    )
                    session.merge(cit_paper)

                    # 関係を作成
                    citation = Citation(
                        citing_paper_id=cit['paperId'],
                        cited_paper_id=paper.paper_id
                    )
                    session.merge(citation)

            session.commit()

            # PDFが利用可能な場合、要約タスクをトリガー
            if paper.pdf_url:
                celery_app.send_task(
                    'refnet_summarizer.tasks.summarize_task.summarize_paper',
                    args=[paper.paper_id],
                    queue='summarizer'
                )
            else:
                # PDFがない場合は直接Markdown生成へ
                celery_app.send_task(
                    'refnet_generator.tasks.generate_task.generate_markdown',
                    args=[paper.paper_id],
                    queue='generator'
                )

            result = {
                'status': 'success',
                'paper_id': paper.paper_id,
                'title': paper.title,
                'references_count': len(paper_data.get('references', [])),
                'citations_count': len(paper_data.get('citations', []))
            }

            logger.info("Paper crawl completed", **result)
            return result

    except Exception as e:
        logger.error("Paper crawl failed", paper_id=paper_id, error=str(e))
        self.retry(exc=e, countdown=60, max_retries=3)
        return {}
