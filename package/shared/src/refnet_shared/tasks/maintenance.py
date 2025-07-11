"""メンテナンスタスク."""

from datetime import datetime, timedelta

import structlog
from sqlalchemy import and_

from refnet_shared.celery_app import app
from refnet_shared.models.database import Author, Paper
from refnet_shared.models.database_manager import db_manager

logger = structlog.get_logger(__name__)


@app.task(bind=True, name="refnet_shared.tasks.maintenance.cleanup_old_data")
def cleanup_old_data(self):
    """90日以上前の未処理データをクリーンアップ."""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=90)

        with db_manager.get_session() as session:
            # 古い未処理論文の削除
            deleted_papers = (
                session.query(Paper)
                .filter(
                    and_(
                        Paper.created_at < cutoff_date,
                        Paper.crawl_status == "pending",
                    )
                )
                .delete(synchronize_session=False)
            )

            # 参照されていない著者の削除
            orphan_authors = session.query(Author).filter(~Author.papers.any()).delete(synchronize_session=False)

            session.commit()

            result = {
                "status": "success",
                "deleted_papers": deleted_papers,
                "orphan_authors": orphan_authors,
                "timestamp": datetime.utcnow().isoformat(),
            }

            logger.info("Data cleanup completed", **result)
            return result

    except Exception as e:
        logger.error("Data cleanup failed", error=str(e))
        self.retry(exc=e, countdown=300, max_retries=3)
        return {}
