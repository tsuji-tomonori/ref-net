"""Markdown生成関連タスク."""

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from refnet_shared.celery_app import app as celery_app
from refnet_shared.models.database import Paper
from refnet_shared.models.database_manager import db_manager
from refnet_shared.models.paper import Citation
from sqlalchemy import and_

from refnet_generator.services.generator_service import GeneratorService

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, name="refnet_generator.tasks.generate_task.generate_pending_markdowns")  # type: ignore[misc]
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
                "timestamp": datetime.now(UTC).isoformat(),
            }

            logger.info("Scheduled markdown generation tasks", **result)
            return result

    except Exception as e:
        logger.error("Failed to generate pending markdowns", error=str(e))
        self.retry(exc=e, countdown=60, max_retries=3)
        return {}


@celery_app.task(bind=True, name='refnet_generator.tasks.generate_task.generate_markdown')
def generate_markdown(self: Any, paper_id: str) -> dict:
    """論文のMarkdownを生成"""
    try:
        with db_manager.get_session() as session:
            paper = session.query(Paper).filter(Paper.paper_id == paper_id).first()
            if not paper:
                raise ValueError(f"Paper {paper_id} not found")

            # 関連論文情報を取得
            references = session.query(Paper).join(
                Citation, Citation.cited_paper_id == Paper.paper_id
            ).filter(Citation.citing_paper_id == paper_id).all()

            citations = session.query(Paper).join(
                Citation, Citation.citing_paper_id == Paper.paper_id
            ).filter(Citation.cited_paper_id == paper_id).all()

            # Markdown生成
            generator = GeneratorService()
            markdown_content = generator.generate_paper_markdown(
                paper=paper,
                references=references,
                citations=citations
            )

            # ファイルパスを生成
            output_dir = Path(os.getenv('OBSIDIAN_VAULT_PATH', '/output/obsidian'))
            output_dir.mkdir(parents=True, exist_ok=True)

            # ファイル名をサニタイズ
            safe_title = "".join(
                c for c in paper.title if c.isalnum() or c in (' ', '-', '_')
            ).rstrip()
            safe_title = safe_title[:100]  # 最大100文字
            filename = f"{safe_title}_{paper.paper_id[:8]}.md"
            filepath = output_dir / filename

            # Markdownファイルを保存
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            # データベースを更新
            paper.markdown_path = str(filepath)
            paper.is_generated = True
            session.commit()

            # 参照論文の自動クロールをトリガー（深さ制限あり）
            current_depth = getattr(paper, 'crawl_depth', 0) or 0
            max_depth = int(os.getenv('MAX_CRAWL_DEPTH', '2'))

            if current_depth < max_depth:
                for ref in references[:5]:  # 最大5つの参照論文をクロール
                    if not ref.is_crawled:
                        if not hasattr(ref, 'crawl_depth') or ref.crawl_depth is None:
                            ref.crawl_depth = current_depth + 1
                            session.commit()

                        celery_app.send_task(
                            'refnet_crawler.tasks.crawl_task.crawl_paper',
                            args=[ref.paper_id],
                            queue='crawler',
                            countdown=10  # 10秒後に実行
                        )

            result = {
                'status': 'success',
                'paper_id': paper.paper_id,
                'filepath': str(filepath),
                'references_triggered': min(5, len([r for r in references if not r.is_crawled]))
            }

            logger.info("Markdown generation completed", **result)
            return result

    except Exception as e:
        logger.error("Markdown generation failed", paper_id=paper_id, error=str(e))
        self.retry(exc=e, countdown=60, max_retries=3)
        return {}
