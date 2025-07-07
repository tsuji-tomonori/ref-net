"""クローラーサービス."""

import structlog
from refnet_shared.models.database import Author, Paper, PaperRelation, ProcessingQueue  # type: ignore
from refnet_shared.models.database_manager import db_manager  # type: ignore
from sqlalchemy.orm import Session

from refnet_crawler.clients.semantic_scholar import SemanticScholarClient
from refnet_crawler.models.paper_data import SemanticScholarPaper

logger = structlog.get_logger(__name__)


class CrawlerService:
    """クローラーサービス."""

    def __init__(self) -> None:
        """初期化."""
        self.client = SemanticScholarClient()

    async def crawl_paper(self, paper_id: str, hop_count: int = 0, max_hops: int = 3) -> bool:
        """論文情報を収集."""
        try:
            # 論文情報取得
            paper_data = await self.client.get_paper(paper_id)
            if not paper_data:
                logger.warning("Paper not found", paper_id=paper_id)
                return False

            # データベース保存
            with db_manager.get_session() as session:
                await self._save_paper_data(session, paper_data)

                # 引用関係の収集（再帰的）
                if hop_count < max_hops:
                    await self._crawl_citations(session, paper_id, hop_count + 1, max_hops)
                    await self._crawl_references(session, paper_id, hop_count + 1, max_hops)

                # 処理状態を更新
                await self._update_processing_status(session, paper_id, "crawl", "completed")

            logger.info("Paper crawled successfully", paper_id=paper_id, hop_count=hop_count)
            return True

        except Exception as e:
            logger.error("Failed to crawl paper", paper_id=paper_id, error=str(e))

            # エラー状態を記録
            with db_manager.get_session() as session:
                await self._update_processing_status(session, paper_id, "crawl", "failed", str(e))

            return False

    async def _save_paper_data(self, session: Session, paper_data: SemanticScholarPaper) -> None:
        """論文データを保存."""
        # 既存チェック
        existing_paper = session.query(Paper).filter_by(paper_id=paper_data.paperId).first()

        if existing_paper:
            # 既存論文の更新
            existing_paper.title = paper_data.title or existing_paper.title
            existing_paper.abstract = paper_data.abstract or existing_paper.abstract
            existing_paper.year = paper_data.year or existing_paper.year
            existing_paper.citation_count = (
                paper_data.citationCount or existing_paper.citation_count
            )
            existing_paper.reference_count = (
                paper_data.referenceCount or existing_paper.reference_count
            )
            existing_paper.crawl_status = "completed"
        else:
            # 新規論文の作成
            paper_dict = paper_data.to_paper_create_dict()
            paper_dict["crawl_status"] = "completed"
            paper = Paper(**paper_dict)
            session.add(paper)

        # 著者情報の保存
        if paper_data.authors:
            await self._save_authors(session, paper_data.paperId, paper_data.authors)

        session.commit()

    async def _save_authors(self, session: Session, paper_id: str, authors_data: list) -> None:
        """著者情報を保存."""
        for position, author_data in enumerate(authors_data):
            if not author_data.authorId:
                continue

            # 既存著者チェック
            existing_author = (
                session.query(Author).filter_by(author_id=author_data.authorId).first()
            )

            if not existing_author:
                author = Author(author_id=author_data.authorId, name=author_data.name or "Unknown")
                session.add(author)

            # 論文-著者関係の作成（重複チェック）
            from refnet_shared.models.database import paper_authors

            existing_relation = session.execute(
                paper_authors.select().where(
                    paper_authors.c.paper_id == paper_id,
                    paper_authors.c.author_id == author_data.authorId,
                )
            ).fetchone()

            if not existing_relation:
                session.execute(
                    paper_authors.insert().values(
                        paper_id=paper_id, author_id=author_data.authorId, position=position
                    )
                )

    async def _crawl_citations(
        self, session: Session, paper_id: str, hop_count: int, max_hops: int
    ) -> None:
        """引用論文の収集."""
        try:
            citations = await self.client.get_paper_citations(paper_id, limit=100)

            for citation in citations:
                # 関係の保存
                await self._save_paper_relation(
                    session,
                    source_paper_id=citation.paperId,
                    target_paper_id=paper_id,
                    relation_type="citation",
                    hop_count=hop_count,
                )

                # 優先度に基づく再帰的収集
                if await self._should_crawl_recursively(citation, hop_count, max_hops):
                    await self._queue_paper_for_crawling(session, citation.paperId, hop_count)

        except Exception as e:
            logger.error("Failed to crawl citations", paper_id=paper_id, error=str(e))

    async def _crawl_references(
        self, session: Session, paper_id: str, hop_count: int, max_hops: int
    ) -> None:
        """参考文献の収集."""
        try:
            references = await self.client.get_paper_references(paper_id, limit=100)

            for reference in references:
                # 関係の保存
                await self._save_paper_relation(
                    session,
                    source_paper_id=paper_id,
                    target_paper_id=reference.paperId,
                    relation_type="reference",
                    hop_count=hop_count,
                )

                # 優先度に基づく再帰的収集
                if await self._should_crawl_recursively(reference, hop_count, max_hops):
                    await self._queue_paper_for_crawling(session, reference.paperId, hop_count)

        except Exception as e:
            logger.error("Failed to crawl references", paper_id=paper_id, error=str(e))

    async def _save_paper_relation(
        self,
        session: Session,
        source_paper_id: str,
        target_paper_id: str,
        relation_type: str,
        hop_count: int,
    ) -> None:
        """論文関係を保存."""
        # 重複チェック
        existing_relation = (
            session.query(PaperRelation)
            .filter_by(
                source_paper_id=source_paper_id,
                target_paper_id=target_paper_id,
                relation_type=relation_type,
            )
            .first()
        )

        if not existing_relation:
            relation = PaperRelation(
                source_paper_id=source_paper_id,
                target_paper_id=target_paper_id,
                relation_type=relation_type,
                hop_count=hop_count,
            )
            session.add(relation)

    async def _should_crawl_recursively(
        self, paper_data: SemanticScholarPaper, hop_count: int, max_hops: int
    ) -> bool:
        """再帰的収集の判定."""
        if hop_count >= max_hops:
            return False

        # 優先度計算（引用数、発行年、ホップ数を考慮）
        citation_count = paper_data.citationCount or 0
        year = paper_data.year or 1900

        # 重み付けスコア計算
        citation_score = min(citation_count / 100, 1.0)  # 正規化
        year_score = max(0, (year - 1990) / 34)  # 1990年以降を重視
        hop_penalty = 0.5 ** (hop_count - 1)  # ホップ数による減衰

        priority_score = (citation_score * 0.5 + year_score * 0.3) * hop_penalty

        # 閾値を超えた場合のみ収集
        return priority_score > 0.1

    async def _queue_paper_for_crawling(
        self, session: Session, paper_id: str, hop_count: int
    ) -> None:
        """論文をクローリングキューに追加."""
        # 既存キューチェック
        existing_queue = (
            session.query(ProcessingQueue)
            .filter_by(paper_id=paper_id, task_type="crawl", status="pending")
            .first()
        )

        if not existing_queue:
            priority = max(0, 100 - hop_count * 10)  # ホップ数が少ないほど高優先度
            queue_item = ProcessingQueue(
                paper_id=paper_id, task_type="crawl", priority=priority, status="pending"
            )
            session.add(queue_item)

    async def _update_processing_status(
        self,
        session: Session,
        paper_id: str,
        task_type: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """処理状態を更新."""
        queue_item = (
            session.query(ProcessingQueue).filter_by(paper_id=paper_id, task_type=task_type).first()
        )

        if queue_item:
            queue_item.status = status
            if error_message:
                queue_item.error_message = error_message
                queue_item.retry_count += 1

        # 論文テーブルの状態も更新
        paper = session.query(Paper).filter_by(paper_id=paper_id).first()
        if paper:
            if task_type == "crawl":
                paper.crawl_status = status

    async def close(self) -> None:
        """リソースのクリーンアップ."""
        await self.client.close()
