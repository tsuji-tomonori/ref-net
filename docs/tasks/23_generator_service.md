# Task: Markdownジェネレーターサービス実装

## タスクの目的

Obsidian形式のMarkdownファイルを生成し、論文ネットワークを可視化するためのMarkdownジェネレーターサービスを実装する。

## 実施内容

### 1. パッケージ構造の作成

```bash
cd package/generator
mkdir -p src/refnet_generator/{services,tasks,templates,formatters}
touch src/refnet_generator/__init__.py
touch src/refnet_generator/main.py
touch src/refnet_generator/services/__init__.py
touch src/refnet_generator/tasks/__init__.py
touch src/refnet_generator/templates/__init__.py
touch src/refnet_generator/formatters/__init__.py
```

### 2. pyproject.toml の設定

```toml
[project]
name = "refnet-generator"
version = "0.1.0"
description = "RefNet Markdown Generator Service"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "celery>=5.3.0",
    "redis>=5.0.0",
    "jinja2>=3.1.0",
    "sqlalchemy>=2.0.0",
    "psycopg2-binary>=2.9.0",
    "structlog>=23.0.0",
    "pydantic>=2.0.0",
    "refnet-shared",
    "mypy>=1.16.1",
    "pytest>=8.4.1",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.12.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
refnet-generator = "refnet_generator.main:main"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
extra_checks = true
```

### 3. moon.yml の設定

```yaml
type: application
language: python

dependsOn:
  - shared

tasks:
  install:
    command: uv sync
    inputs:
      - "pyproject.toml"
      - "uv.lock"

  worker:
    command: celery -A refnet_generator.tasks.celery_app worker --loglevel=info --queue=generate
    inputs:
      - "src/**/*.py"
    local: true

  lint:
    command: ruff check src/
    inputs:
      - "src/**/*.py"

  format:
    command: ruff format src/
    inputs:
      - "src/**/*.py"

  typecheck:
    command: mypy src/
    inputs:
      - "src/**/*.py"

  test:
    command: pytest tests/
    inputs:
      - "src/**/*.py"
      - "tests/**/*.py"

  build:
    command: docker build -t refnet-generator .
    inputs:
      - "src/**/*.py"
      - "Dockerfile"
    outputs:
      - "dist/"

  check:
    deps:
      - lint
      - typecheck
      - test
```

### 4. Obsidianフォーマッター

`src/refnet_generator/formatters/obsidian_formatter.py`:

```python
"""Obsidian形式フォーマッター."""

from typing import List, Dict, Any, Optional
from datetime import datetime
from refnet_shared.models.database import Paper, Author, PaperRelation, PaperKeyword
import structlog


logger = structlog.get_logger(__name__)


class ObsidianFormatter:
    """Obsidian形式のMarkdownフォーマッター."""

    def __init__(self):
        """初期化."""
        pass

    def format_paper(
        self,
        paper: Paper,
        citations: List[PaperRelation],
        references: List[PaperRelation],
        keywords: List[PaperKeyword]
    ) -> str:
        """論文をObsidian形式でフォーマット."""
        # フロントマター生成
        frontmatter = self._generate_frontmatter(paper, keywords)

        # 本文生成
        content = self._generate_content(paper, citations, references, keywords)

        # Markdown結合
        markdown = f"---\n{frontmatter}\n---\n\n{content}"

        return markdown

    def _generate_frontmatter(self, paper: Paper, keywords: List[PaperKeyword]) -> str:
        """フロントマター生成."""
        frontmatter_data = {
            "paper_id": paper.paper_id,
            "title": paper.title or "Untitled",
            "year": paper.year,
            "citation_count": paper.citation_count,
            "reference_count": paper.reference_count,
            "crawl_status": paper.crawl_status,
            "pdf_status": paper.pdf_status,
            "summary_status": paper.summary_status,
            "created_at": paper.created_at.isoformat() if paper.created_at else None,
            "updated_at": paper.updated_at.isoformat() if paper.updated_at else None,
        }

        # 著者情報
        if paper.authors:
            frontmatter_data["authors"] = [author.name for author in paper.authors]

        # 会場・ジャーナル情報
        if paper.venue:
            frontmatter_data["venue"] = paper.venue.name
        if paper.journal:
            frontmatter_data["journal"] = paper.journal.name

        # PDF情報
        if paper.pdf_url:
            frontmatter_data["pdf_url"] = paper.pdf_url
        if paper.pdf_hash:
            frontmatter_data["pdf_hash"] = paper.pdf_hash

        # キーワード
        if keywords:
            frontmatter_data["keywords"] = [kw.keyword for kw in keywords]

        # タグ
        tags = ["paper"]
        if paper.year:
            tags.append(f"year/{paper.year}")
        if paper.venue:
            tags.append(f"venue/{self._slugify(paper.venue.name)}")
        frontmatter_data["tags"] = tags

        # YAML形式で出力
        lines = []
        for key, value in frontmatter_data.items():
            if value is not None:
                if isinstance(value, list):
                    if value:  # 空リストでない場合のみ
                        lines.append(f"{key}:")
                        for item in value:
                            lines.append(f"  - {self._escape_yaml_value(item)}")
                else:
                    lines.append(f"{key}: {self._escape_yaml_value(value)}")

        return "\n".join(lines)

    def _generate_content(
        self,
        paper: Paper,
        citations: List[PaperRelation],
        references: List[PaperRelation],
        keywords: List[PaperKeyword]
    ) -> str:
        """論文本文生成."""
        sections = []

        # タイトル
        if paper.title:
            sections.append(f"# {paper.title}")

        # 基本情報
        sections.append(self._generate_basic_info_section(paper))

        # 要約
        if paper.summary:
            sections.append(self._generate_summary_section(paper.summary))

        # アブストラクト
        if paper.abstract:
            sections.append(self._generate_abstract_section(paper.abstract))

        # 引用関係
        if citations or references:
            sections.append(self._generate_relations_section(citations, references))

        # キーワード
        if keywords:
            sections.append(self._generate_keywords_section(keywords))

        # 外部リンク
        sections.append(self._generate_links_section(paper))

        # メタデータ
        sections.append(self._generate_metadata_section(paper))

        return "\n\n".join(sections)

    def _generate_basic_info_section(self, paper: Paper) -> str:
        """基本情報セクション生成."""
        lines = ["## 基本情報"]

        # 著者
        if paper.authors:
            author_links = [f"[[{author.name}]]" for author in paper.authors]
            lines.append(f"**著者**: {', '.join(author_links)}")

        # 発行年
        if paper.year:
            lines.append(f"**発行年**: {paper.year}")

        # 会場・ジャーナル
        if paper.venue:
            lines.append(f"**会場**: {paper.venue.name}")
        if paper.journal:
            lines.append(f"**ジャーナル**: {paper.journal.name}")

        # 統計情報
        lines.append(f"**引用数**: {paper.citation_count}")
        lines.append(f"**参考文献数**: {paper.reference_count}")

        return "\n".join(lines)

    def _generate_summary_section(self, summary: str) -> str:
        """要約セクション生成."""
        return f"## 要約\n\n{summary}"

    def _generate_abstract_section(self, abstract: str) -> str:
        """アブストラクトセクション生成."""
        return f"## アブストラクト\n\n{abstract}"

    def _generate_relations_section(
        self,
        citations: List[PaperRelation],
        references: List[PaperRelation]
    ) -> str:
        """関係セクション生成."""
        lines = ["## 論文関係"]

        # 引用論文（この論文を引用している論文）
        if citations:
            lines.append("\n### 引用論文")
            citation_map = {}
            for citation in citations:
                hop_count = citation.hop_count
                if hop_count not in citation_map:
                    citation_map[hop_count] = []
                citation_map[hop_count].append(citation)

            for hop_count in sorted(citation_map.keys()):
                lines.append(f"\n#### ホップ数 {hop_count}")
                for citation in citation_map[hop_count]:
                    paper_link = f"[[{citation.source_paper_id}]]"
                    lines.append(f"- {paper_link}")

        # 参考文献（この論文が引用している論文）
        if references:
            lines.append("\n### 参考文献")
            reference_map = {}
            for reference in references:
                hop_count = reference.hop_count
                if hop_count not in reference_map:
                    reference_map[hop_count] = []
                reference_map[hop_count].append(reference)

            for hop_count in sorted(reference_map.keys()):
                lines.append(f"\n#### ホップ数 {hop_count}")
                for reference in reference_map[hop_count]:
                    paper_link = f"[[{reference.target_paper_id}]]"
                    lines.append(f"- {paper_link}")

        return "\n".join(lines)

    def _generate_keywords_section(self, keywords: List[PaperKeyword]) -> str:
        """キーワードセクション生成."""
        lines = ["## キーワード"]

        # 関連度スコア順でソート
        sorted_keywords = sorted(keywords, key=lambda k: k.relevance_score or 0, reverse=True)

        keyword_tags = []
        for keyword in sorted_keywords:
            if keyword.relevance_score:
                keyword_tags.append(f"#{self._slugify(keyword.keyword)} (関連度: {keyword.relevance_score:.2f})")
            else:
                keyword_tags.append(f"#{self._slugify(keyword.keyword)}")

        lines.append("\n".join(keyword_tags))

        return "\n".join(lines)

    def _generate_links_section(self, paper: Paper) -> str:
        """外部リンクセクション生成."""
        lines = ["## 外部リンク"]

        # PDF URL
        if paper.pdf_url:
            lines.append(f"- [PDF]({paper.pdf_url})")

        # 外部ID
        if paper.external_ids:
            for external_id in paper.external_ids:
                if external_id.id_type == "DOI" and external_id.external_id:
                    lines.append(f"- [DOI](https://doi.org/{external_id.external_id})")
                elif external_id.id_type == "ArXiv" and external_id.external_id:
                    lines.append(f"- [ArXiv](https://arxiv.org/abs/{external_id.external_id})")
                elif external_id.id_type == "PubMed" and external_id.external_id:
                    lines.append(f"- [PubMed](https://pubmed.ncbi.nlm.nih.gov/{external_id.external_id}/)")

        # Semantic Scholar
        lines.append(f"- [Semantic Scholar](https://www.semanticscholar.org/paper/{paper.paper_id})")

        return "\n".join(lines)

    def _generate_metadata_section(self, paper: Paper) -> str:
        """メタデータセクション生成."""
        lines = ["## メタデータ"]

        lines.append(f"- **Paper ID**: `{paper.paper_id}`")
        lines.append(f"- **クロール状態**: {paper.crawl_status}")
        lines.append(f"- **PDF状態**: {paper.pdf_status}")
        lines.append(f"- **要約状態**: {paper.summary_status}")

        if paper.pdf_hash:
            lines.append(f"- **PDF Hash**: `{paper.pdf_hash}`")

        if paper.created_at:
            lines.append(f"- **作成日時**: {paper.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if paper.updated_at:
            lines.append(f"- **更新日時**: {paper.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)

    def _escape_yaml_value(self, value: Any) -> str:
        """YAML値のエスケープ."""
        if isinstance(value, str):
            # 特殊文字を含む場合はクォート
            if any(char in value for char in [':', '"', "'", '[', ']', '{', '}', '#', '&', '*', '!', '|', '>', '%', '@', '`']):
                return f'"{value.replace('"', '\\"')}"'
            return value
        return str(value)

    def _slugify(self, text: str) -> str:
        """文字列をスラッグ化."""
        import re
        # 英数字とハイフン、アンダースコアのみ残す
        slug = re.sub(r'[^\w\-_\s]', '', text)
        # スペースをハイフンに変換
        slug = re.sub(r'[\s_]+', '-', slug)
        # 連続するハイフンを1つに
        slug = re.sub(r'-+', '-', slug)
        # 前後のハイフンを削除
        slug = slug.strip('-')
        return slug.lower()

    def generate_index_file(self, papers: List[Paper]) -> str:
        """インデックスファイル生成."""
        lines = ["# 論文ネットワーク", ""]

        # 統計情報
        lines.extend([
            "## 統計情報",
            f"- 総論文数: {len(papers)}",
            f"- 総引用数: {sum(p.citation_count for p in papers)}",
            ""
        ])

        # 年別論文数
        year_counts = {}
        for paper in papers:
            if paper.year:
                year_counts[paper.year] = year_counts.get(paper.year, 0) + 1

        if year_counts:
            lines.append("## 年別論文数")
            for year in sorted(year_counts.keys(), reverse=True):
                lines.append(f"- {year}: {year_counts[year]}論文")
            lines.append("")

        # 引用数上位論文
        top_cited = sorted(papers, key=lambda p: p.citation_count, reverse=True)[:10]
        if top_cited:
            lines.append("## 引用数上位論文")
            for i, paper in enumerate(top_cited, 1):
                title = paper.title or "Untitled"
                lines.append(f"{i}. [[{paper.paper_id}|{title}]] ({paper.citation_count} citations)")
            lines.append("")

        # 最近の論文
        recent_papers = sorted(
            [p for p in papers if p.year],
            key=lambda p: p.year,
            reverse=True
        )[:10]
        if recent_papers:
            lines.append("## 最近の論文")
            for paper in recent_papers:
                title = paper.title or "Untitled"
                lines.append(f"- ({paper.year}) [[{paper.paper_id}|{title}]]")
            lines.append("")

        return "\n".join(lines)

    def generate_graph_config(self) -> str:
        """Obsidianグラフ設定生成."""
        config = {
            "graph": {
                "colorGroups": [
                    {
                        "query": "tag:#paper",
                        "color": {"a": 1, "rgb": 5431378}
                    },
                    {
                        "query": "tag:#year/2023",
                        "color": {"a": 1, "rgb": 14701138}
                    },
                    {
                        "query": "tag:#year/2022",
                        "color": {"a": 1, "rgb": 14725458}
                    }
                ],
                "showTags": True,
                "showAttachments": False,
                "hideUnresolved": True,
                "showOrphans": False,
                "linkDistance": 250,
                "linkStrength": 1,
                "repelStrength": 10,
                "centerStrength": 0.5,
                "textFadeMultiplier": 0,
                "nodeSizeMultiplier": 1,
                "lineSizeMultiplier": 5
            }
        }

        import json
        return json.dumps(config, indent=2)
```

### 5. ジェネレーターサービス

`src/refnet_generator/services/generator_service.py`:

```python
"""ジェネレーターサービス."""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from refnet_shared.models.database import Paper, PaperRelation, PaperKeyword, ProcessingQueue
from refnet_shared.models.database_manager import db_manager
from refnet_generator.formatters.obsidian_formatter import ObsidianFormatter
import structlog


logger = structlog.get_logger(__name__)


class GeneratorService:
    """Markdownジェネレーターサービス."""

    def __init__(self, output_dir: str = "./output"):
        """初期化."""
        self.output_dir = Path(output_dir)
        self.papers_dir = self.output_dir / "papers"
        self.formatter = ObsidianFormatter()

        # 出力ディレクトリの作成
        self.papers_dir.mkdir(parents=True, exist_ok=True)

    async def generate_paper_markdown(self, paper_id: str) -> bool:
        """論文のMarkdownを生成."""
        try:
            with db_manager.get_session() as session:
                # 論文情報取得
                paper = session.query(Paper).filter_by(paper_id=paper_id).first()
                if not paper:
                    logger.error("Paper not found", paper_id=paper_id)
                    return False

                # 関連情報取得
                citations = session.query(PaperRelation).filter_by(
                    target_paper_id=paper_id,
                    relation_type="citation"
                ).all()

                references = session.query(PaperRelation).filter_by(
                    source_paper_id=paper_id,
                    relation_type="reference"
                ).all()

                keywords = session.query(PaperKeyword).filter_by(paper_id=paper_id).all()

                # 処理状態を更新
                await self._update_processing_status(session, paper_id, "generate", "running")

            # Markdown生成
            markdown = self.formatter.format_paper(paper, citations, references, keywords)

            # ファイル出力
            await self._write_markdown_file(paper_id, markdown)

            # 処理状態を更新
            with db_manager.get_session() as session:
                await self._update_processing_status(session, paper_id, "generate", "completed")

            logger.info("Paper markdown generated successfully", paper_id=paper_id)
            return True

        except Exception as e:
            logger.error("Failed to generate paper markdown", paper_id=paper_id, error=str(e))

            with db_manager.get_session() as session:
                await self._update_processing_status(session, paper_id, "generate", "failed", str(e))

            return False

    async def generate_all_papers(self) -> Dict[str, bool]:
        """全論文のMarkdownを生成."""
        results = {}

        with db_manager.get_session() as session:
            papers = session.query(Paper).all()

            for paper in papers:
                result = await self.generate_paper_markdown(paper.paper_id)
                results[paper.paper_id] = result

        logger.info("Batch markdown generation completed", total=len(results), successful=sum(results.values()))
        return results

    async def generate_index_file(self) -> bool:
        """インデックスファイルを生成."""
        try:
            with db_manager.get_session() as session:
                papers = session.query(Paper).all()

            # インデックス生成
            index_content = self.formatter.generate_index_file(papers)

            # ファイル出力
            index_path = self.output_dir / "README.md"
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(index_content)

            logger.info("Index file generated successfully", path=str(index_path))
            return True

        except Exception as e:
            logger.error("Failed to generate index file", error=str(e))
            return False

    async def generate_obsidian_config(self) -> bool:
        """Obsidian設定ファイルを生成."""
        try:
            # .obsidianディレクトリ作成
            obsidian_dir = self.output_dir / ".obsidian"
            obsidian_dir.mkdir(exist_ok=True)

            # グラフ設定生成
            graph_config = self.formatter.generate_graph_config()

            # 設定ファイル出力
            config_path = obsidian_dir / "graph.json"
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(graph_config)

            # workspace設定
            workspace_config = {
                "main": {
                    "id": "refnet-workspace",
                    "type": "split",
                    "children": [
                        {
                            "id": "refnet-main",
                            "type": "leaf",
                            "state": {
                                "type": "markdown",
                                "state": {
                                    "file": "README.md",
                                    "mode": "source"
                                }
                            }
                        }
                    ]
                },
                "left": {
                    "id": "refnet-left",
                    "type": "split",
                    "children": [
                        {
                            "id": "refnet-file-explorer",
                            "type": "leaf",
                            "state": {
                                "type": "file-explorer",
                                "state": {}
                            }
                        },
                        {
                            "id": "refnet-search",
                            "type": "leaf",
                            "state": {
                                "type": "search",
                                "state": {
                                    "query": "",
                                    "matchingCase": False,
                                    "explainSearch": False,
                                    "collapseAll": False,
                                    "extraContext": False,
                                    "sortOrder": "alphabetical"
                                }
                            }
                        }
                    ]
                },
                "right": {
                    "id": "refnet-right",
                    "type": "split",
                    "children": [
                        {
                            "id": "refnet-graph",
                            "type": "leaf",
                            "state": {
                                "type": "graph",
                                "state": {}
                            }
                        }
                    ]
                },
                "active": "refnet-main",
                "lastOpenFiles": ["README.md"]
            }

            workspace_path = obsidian_dir / "workspace.json"
            import json
            with open(workspace_path, "w", encoding="utf-8") as f:
                json.dump(workspace_config, f, indent=2)

            logger.info("Obsidian config generated successfully", path=str(obsidian_dir))
            return True

        except Exception as e:
            logger.error("Failed to generate Obsidian config", error=str(e))
            return False

    async def _write_markdown_file(self, paper_id: str, content: str) -> None:
        """Markdownファイルの書き込み."""
        # ファイル名の安全化
        safe_filename = self._safe_filename(paper_id)
        file_path = self.papers_dir / f"{safe_filename}.md"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.debug("Markdown file written", paper_id=paper_id, path=str(file_path))

    def _safe_filename(self, filename: str) -> str:
        """ファイル名の安全化."""
        import re
        # 不正な文字を除去
        safe = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 長さ制限
        if len(safe) > 100:
            safe = safe[:100]
        return safe

    async def _update_processing_status(
        self,
        session: Session,
        paper_id: str,
        task_type: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """処理状態を更新."""
        # 処理キューの更新
        queue_item = session.query(ProcessingQueue).filter_by(
            paper_id=paper_id,
            task_type=task_type
        ).first()

        if queue_item:
            queue_item.status = status
            if error_message:
                queue_item.error_message = error_message
                queue_item.retry_count += 1

        session.commit()

    async def get_generation_stats(self) -> Dict[str, Any]:
        """生成統計取得."""
        try:
            # 生成されたファイル数
            markdown_files = list(self.papers_dir.glob("*.md"))
            file_count = len(markdown_files)

            # ファイルサイズ統計
            total_size = sum(f.stat().st_size for f in markdown_files)
            avg_size = total_size / file_count if file_count > 0 else 0

            # データベース統計
            with db_manager.get_session() as session:
                total_papers = session.query(Paper).count()
                completed_papers = session.query(Paper).filter_by(summary_status="completed").count()

            return {
                "generated_files": file_count,
                "total_papers": total_papers,
                "completion_rate": completed_papers / total_papers if total_papers > 0 else 0,
                "total_file_size": total_size,
                "average_file_size": avg_size,
                "output_directory": str(self.output_dir),
            }

        except Exception as e:
            logger.error("Failed to get generation stats", error=str(e))
            return {}

    async def cleanup_generated_files(self) -> bool:
        """生成ファイルのクリーンアップ."""
        try:
            import shutil

            if self.output_dir.exists():
                shutil.rmtree(self.output_dir)
                self.papers_dir.mkdir(parents=True, exist_ok=True)

            logger.info("Generated files cleaned up successfully")
            return True

        except Exception as e:
            logger.error("Failed to cleanup generated files", error=str(e))
            return False
```

### 6. Celeryタスク定義

`src/refnet_generator/tasks/__init__.py`:

```python
"""Celeryタスク定義."""

import asyncio
from celery import Celery
from refnet_shared.config import settings
from refnet_generator.services.generator_service import GeneratorService
import structlog


logger = structlog.get_logger(__name__)

# Celeryアプリケーション
celery_app = Celery(
    "refnet_generator",
    broker=settings.redis.url,
    backend=settings.redis.url,
    include=["refnet_generator.tasks"]
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30分
    task_soft_time_limit=1500,  # 25分
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=500,
)


@celery_app.task(bind=True, name="refnet.generator.generate_markdown")
def generate_markdown_task(self, paper_id: str, output_dir: str = "./output") -> bool:
    """Markdown生成タスク."""
    logger.info("Starting markdown generation task", paper_id=paper_id)

    async def _generate():
        generator = GeneratorService(output_dir)
        return await generator.generate_paper_markdown(paper_id)

    try:
        result = asyncio.run(_generate())
        logger.info("Markdown generation task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Markdown generation task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=3)


@celery_app.task(name="refnet.generator.generate_all_papers")
def generate_all_papers_task(output_dir: str = "./output") -> dict:
    """全論文Markdown生成タスク."""
    logger.info("Starting batch markdown generation task")

    async def _generate_all():
        generator = GeneratorService(output_dir)
        return await generator.generate_all_papers()

    try:
        results = asyncio.run(_generate_all())
        logger.info("Batch markdown generation task completed", total=len(results))
        return results
    except Exception as e:
        logger.error("Batch markdown generation task failed", error=str(e))
        raise


@celery_app.task(name="refnet.generator.generate_index")
def generate_index_task(output_dir: str = "./output") -> bool:
    """インデックス生成タスク."""
    logger.info("Starting index generation task")

    async def _generate_index():
        generator = GeneratorService(output_dir)
        index_result = await generator.generate_index_file()
        config_result = await generator.generate_obsidian_config()
        return index_result and config_result

    try:
        result = asyncio.run(_generate_index())
        logger.info("Index generation task completed", success=result)
        return result
    except Exception as e:
        logger.error("Index generation task failed", error=str(e))
        raise


@celery_app.task(name="refnet.generator.cleanup_files")
def cleanup_files_task(output_dir: str = "./output") -> bool:
    """ファイルクリーンアップタスク."""
    logger.info("Starting file cleanup task")

    async def _cleanup():
        generator = GeneratorService(output_dir)
        return await generator.cleanup_generated_files()

    try:
        result = asyncio.run(_cleanup())
        logger.info("File cleanup task completed", success=result)
        return result
    except Exception as e:
        logger.error("File cleanup task failed", error=str(e))
        raise
```

### 7. テストの作成

`tests/test_obsidian_formatter.py`:

```python
"""Obsidianフォーマッターのテスト."""

import pytest
from datetime import datetime
from refnet_shared.models.database import Paper, Author, PaperRelation, PaperKeyword
from refnet_generator.formatters.obsidian_formatter import ObsidianFormatter


@pytest.fixture
def formatter():
    """テスト用フォーマッター."""
    return ObsidianFormatter()


@pytest.fixture
def sample_paper():
    """サンプル論文."""
    paper = Paper(
        paper_id="test-paper-1",
        title="Test Paper Title",
        abstract="This is a test abstract.",
        year=2023,
        citation_count=10,
        reference_count=5,
        summary="This is a test summary.",
        crawl_status="completed",
        pdf_status="completed",
        summary_status="completed",
        created_at=datetime(2023, 1, 1, 12, 0, 0),
        updated_at=datetime(2023, 1, 2, 12, 0, 0),
    )

    # 著者を追加
    author = Author(author_id="author-1", name="Test Author")
    paper.authors = [author]

    return paper


@pytest.fixture
def sample_keywords():
    """サンプルキーワード."""
    return [
        PaperKeyword(
            paper_id="test-paper-1",
            keyword="machine learning",
            relevance_score=0.9
        ),
        PaperKeyword(
            paper_id="test-paper-1",
            keyword="neural networks",
            relevance_score=0.8
        ),
    ]


def test_format_paper(formatter, sample_paper, sample_keywords):
    """論文フォーマットテスト."""
    citations = []
    references = []

    result = formatter.format_paper(sample_paper, citations, references, sample_keywords)

    assert "---" in result  # フロントマター
    assert "paper_id: test-paper-1" in result
    assert "title: Test Paper Title" in result
    assert "# Test Paper Title" in result  # タイトル
    assert "## 基本情報" in result
    assert "## 要約" in result
    assert "This is a test summary." in result
    assert "## アブストラクト" in result
    assert "This is a test abstract." in result
    assert "## キーワード" in result


def test_generate_frontmatter(formatter, sample_paper, sample_keywords):
    """フロントマター生成テスト."""
    frontmatter = formatter._generate_frontmatter(sample_paper, sample_keywords)

    assert "paper_id: test-paper-1" in frontmatter
    assert "title: Test Paper Title" in frontmatter
    assert "year: 2023" in frontmatter
    assert "citation_count: 10" in frontmatter
    assert "Test Author" in frontmatter
    assert "machine learning" in frontmatter
    assert "neural networks" in frontmatter


def test_slugify(formatter):
    """スラッグ化テスト."""
    assert formatter._slugify("Machine Learning") == "machine-learning"
    assert formatter._slugify("Deep Neural Networks!") == "deep-neural-networks"
    assert formatter._slugify("Test_with_underscores") == "test-with-underscores"


def test_escape_yaml_value(formatter):
    """YAML値エスケープテスト."""
    assert formatter._escape_yaml_value("simple text") == "simple text"
    assert formatter._escape_yaml_value('text with "quotes"') == '"text with \\"quotes\\""'
    assert formatter._escape_yaml_value("text: with colon") == '"text: with colon"'
    assert formatter._escape_yaml_value(123) == "123"


def test_generate_index_file(formatter, sample_paper):
    """インデックスファイル生成テスト."""
    papers = [sample_paper]

    result = formatter.generate_index_file(papers)

    assert "# 論文ネットワーク" in result
    assert "## 統計情報" in result
    assert "総論文数: 1" in result
    assert "総引用数: 10" in result
    assert "## 年別論文数" in result
    assert "2023: 1論文" in result
    assert "## 引用数上位論文" in result
    assert "Test Paper Title" in result
```

### 8. Dockerfileの作成

`Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# システム依存関係
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係
COPY pyproject.toml uv.lock ./
RUN pip install uv
RUN uv sync --frozen

# アプリケーションコピー
COPY src/ ./src/

# 環境変数
ENV PYTHONPATH=/app/src

# 出力ディレクトリ
VOLUME ["/app/output"]

# 起動コマンド
CMD ["celery", "-A", "refnet_generator.tasks.celery_app", "worker", "--loglevel=info", "--queue=generate"]
```

## スコープ

- Obsidian形式Markdownフォーマッター実装
- ファイル生成・管理機能
- インデックスファイル生成
- Obsidian設定ファイル生成
- Celeryタスク実装
- 基本的なテストケース

**スコープ外:**
- 高度なテンプレートエンジン統合
- リアルタイムファイル更新
- 複数フォーマット対応
- 大規模ファイル生成最適化

## 参照するドキュメント

- `/docs/generator/obsidian-format.md`
- `/docs/development/coding-standards.md`
- `/docs/tasks/10_database_models.md`

## 完了条件

- [ ] Obsidianフォーマッターが実装されている
- [ ] ジェネレーターサービスが実装されている
- [ ] Celeryタスクが実装されている
- [ ] インデックスファイル生成機能が実装されている
- [ ] Obsidian設定ファイル生成機能が実装されている
- [ ] 基本的なテストケースが作成されている
- [ ] Dockerfileが作成されている
- [ ] `cd package/generator && moon check` が正常終了する
- [ ] テストカバレッジが80%以上である

## レビュー観点

### 技術的正確性
- [ ] Obsidian形式のMarkdown生成が仕様に準拠している
- [ ] フロントマターのYAML形式が正しい
- [ ] ファイルリンク（[[]]記法）が適切に生成される
- [ ] Celeryタスクの定義とファイル操作が正しい
- [ ] ファイルエンコーディング（UTF-8）が適切に処理される

### 実装可能性
- [ ] 大量ファイル生成時のメモリ使用量が適切である
- [ ] ファイルシステムの権限・容量制限に対応している
- [ ] 長時間実行タスクの進捗管理が実装されている
- [ ] 並行ファイル生成が安全に実装されている

### 統合考慮事項
- [ ] データベースモデルとの整合性が保たれている
- [ ] 要約サービスからのデータ受け取りが適切である
- [ ] 共通ライブラリ（refnet-shared）との依存関係が適切である
- [ ] Docker環境でのボリュームマウントが考慮されている

### 品質基準
- [ ] 生成されるMarkdownの品質が高い
- [ ] エラー発生時のファイル一貫性が保たれる
- [ ] ログ出力が適切で監視・デバッグに役立つ
- [ ] テンプレートの変更・拡張が容易である

### セキュリティ考慮事項
- [ ] ファイル名のサニタイゼーションが適切である
- [ ] ディレクトリトラバーサル攻撃への対策がある
- [ ] 生成されるファイルの権限設定が適切である
- [ ] 機密情報がファイルに出力されないよう配慮されている

### パフォーマンス考慮事項
- [ ] ファイル生成の効率化（バッチ処理等）が実装されている
- [ ] インデックスファイル生成が効率的である
- [ ] 不要なファイル再生成を避ける仕組みがある
- [ ] 論文ネットワークの可視化が効果的である

### 保守性
- [ ] 新しいフォーマットの追加が容易である
- [ ] テンプレートの修正・拡張が容易である
- [ ] 生成統計の監視・管理が適切である
- [ ] ファイル構造の変更が容易である
