"""論文サービスクラス."""


import structlog
from refnet_shared.models.database import Paper, PaperRelation, ProcessingQueue
from refnet_shared.models.schemas import PaperCreate, PaperUpdate
from sqlalchemy.orm import Session

from refnet_api.services.celery_service import CeleryService

logger = structlog.get_logger(__name__)


class PaperService:
    """論文サービス."""

    def __init__(self, db: Session):
        """初期化."""
        self.db = db
        self.celery_service = CeleryService()

    def get_papers(self, skip: int = 0, limit: int = 100) -> list[Paper]:
        """論文一覧取得."""
        return self.db.query(Paper).offset(skip).limit(limit).all()

    def get_paper(self, paper_id: str) -> Paper | None:
        """論文取得."""
        return self.db.query(Paper).filter(Paper.paper_id == paper_id).first()

    def create_paper(self, paper_data: PaperCreate) -> Paper:
        """論文作成."""
        paper = Paper(**paper_data.model_dump())
        self.db.add(paper)
        self.db.commit()
        self.db.refresh(paper)

        logger.info("Paper created", paper_id=paper.paper_id)
        return paper

    def update_paper(self, paper_id: str, paper_update: PaperUpdate) -> Paper:
        """論文更新."""
        paper = self.get_paper(paper_id)
        if not paper:
            raise ValueError("Paper not found")

        update_data = paper_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(paper, field, value)

        self.db.commit()
        self.db.refresh(paper)

        logger.info("Paper updated", paper_id=paper.paper_id)
        return paper

    def queue_paper_processing(self, paper_id: str) -> str:
        """論文処理をキューに追加."""
        # クローリングタスクを追加
        task_id = self.celery_service.queue_crawl_task(paper_id)

        # 処理キューに記録
        queue_item = ProcessingQueue(paper_id=paper_id, task_type="crawl", status="pending")
        self.db.add(queue_item)
        self.db.commit()

        logger.info("Paper processing queued", paper_id=paper_id, task_id=task_id)
        return task_id

    def get_paper_relations(
        self, paper_id: str, relation_type: str | None = None
    ) -> list[PaperRelation]:
        """論文関係取得."""
        query = self.db.query(PaperRelation).filter(
            (PaperRelation.source_paper_id == paper_id)
            | (PaperRelation.target_paper_id == paper_id)
        )

        if relation_type:
            query = query.filter(PaperRelation.relation_type == relation_type)

        return query.all()
