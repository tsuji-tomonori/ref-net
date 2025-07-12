"""Markdownジェネレーターサービス."""

from datetime import datetime
from pathlib import Path

import networkx as nx  # type: ignore[import-untyped]
import structlog
from jinja2 import Environment, FileSystemLoader
from refnet_shared.config.environment import load_environment_settings
from refnet_shared.models.database import Author, Paper, PaperRelation
from refnet_shared.models.database_manager import db_manager
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)
settings = load_environment_settings()


class GeneratorService:
    """Markdownジェネレーターサービス."""

    def __init__(self) -> None:
        """初期化."""
        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        self.output_dir = Path(settings.output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate_paper_markdown_sync(
        self, paper: Paper, references: list[Paper], citations: list[Paper]
    ) -> str:
        """論文のMarkdownコンテンツを同期的に生成して返す."""
        try:
            # 著者情報を取得（paperから直接取得）
            authors = getattr(paper, 'authors', [])

            # テンプレートレンダリング
            template = self.jinja_env.get_template("paper.md.j2")
            content = template.render(
                paper=paper,
                authors=authors,
                references=references,
                citations=citations,
                generated_at=datetime.now().isoformat(),
            )

            logger.info("Paper markdown content generated", paper_id=paper.paper_id)
            return str(content)

        except Exception as e:
            logger.error(
                "Failed to generate paper markdown content",
                paper_id=paper.paper_id,
                error=str(e)
            )
            raise

    async def generate_markdown(self, paper_id: str) -> bool:
        """論文Markdown生成."""
        try:
            with db_manager.get_session() as session:
                # 論文情報取得
                paper = session.query(Paper).filter_by(paper_id=paper_id).first()
                if not paper:
                    logger.warning("Paper not found", paper_id=paper_id)
                    return False

                # 論文単体のMarkdown生成
                await self._generate_paper_markdown(session, paper)

                # ネットワーク図の生成
                await self._generate_network_diagram(session, paper_id)

                # インデックスファイルの更新
                await self._update_index_file(session)

            logger.info("Markdown generated successfully", paper_id=paper_id)
            return True

        except Exception as e:
            logger.error("Failed to generate markdown", paper_id=paper_id, error=str(e))
            return False

    async def _generate_paper_markdown(self, session: Session, paper: Paper) -> None:
        """個別論文のMarkdown生成."""
        # 著者情報取得
        authors = (
            session.query(Author).join(Author.papers).filter(Paper.paper_id == paper.paper_id).all()
        )

        # 関連論文取得
        citations = (
            session.query(PaperRelation)
            .filter_by(target_paper_id=paper.paper_id, relation_type="citation")
            .limit(10)
            .all()
        )

        references = (
            session.query(PaperRelation)
            .filter_by(source_paper_id=paper.paper_id, relation_type="reference")
            .limit(10)
            .all()
        )

        # テンプレートレンダリング
        template = self.jinja_env.get_template("paper.md.j2")
        content = template.render(
            paper=paper,
            authors=authors,
            citations=citations,
            references=references,
            generated_at=datetime.now().isoformat(),
        )

        # ファイル保存
        file_path = self.output_dir / f"{paper.paper_id}.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Paper markdown generated", paper_id=paper.paper_id, file_path=str(file_path))

    async def _generate_network_diagram(self, session: Session, paper_id: str) -> None:
        """ネットワーク図のMarkdown生成."""
        # 関連論文のネットワーク構築
        G = nx.DiGraph()

        # 中心論文を追加
        G.add_node(paper_id)

        # 引用・参考文献関係を追加
        relations = (
            session.query(PaperRelation)
            .filter(
                (PaperRelation.source_paper_id == paper_id)
                | (PaperRelation.target_paper_id == paper_id)
            )
            .all()
        )

        for relation in relations:
            G.add_edge(
                relation.source_paper_id,
                relation.target_paper_id,
                relation_type=relation.relation_type,
            )

        # ネットワーク統計
        network_stats = {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "in_degree": G.in_degree(paper_id) if paper_id in G else 0,
            "out_degree": G.out_degree(paper_id) if paper_id in G else 0,
        }

        # テンプレートレンダリング
        template = self.jinja_env.get_template("network.md.j2")
        content = template.render(
            paper_id=paper_id,
            network_stats=network_stats,
            relations=relations,
            generated_at=datetime.now().isoformat(),
        )

        # ファイル保存
        file_path = self.output_dir / f"{paper_id}_network.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Network diagram generated", paper_id=paper_id, file_path=str(file_path))

    async def _update_index_file(self, session: Session) -> None:
        """インデックスファイルの更新."""
        # 全論文のリスト取得
        papers = (
            session.query(Paper)
            .filter(Paper.is_summarized.is_(True))
            .order_by(Paper.citation_count.desc())
            .limit(100)
            .all()
        )

        # 統計情報
        stats = {
            "total_papers": session.query(Paper).count(),
            "completed_papers": session.query(Paper)
            .filter(Paper.is_summarized.is_(True))
            .count(),
            "generated_at": datetime.now().isoformat(),
        }

        # テンプレートレンダリング
        template = self.jinja_env.get_template("index.md.j2")
        content = template.render(papers=papers, stats=stats)

        # ファイル保存
        file_path = self.output_dir / "index.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Index file updated", total_papers=len(papers))
