# Task: Markdownジェネレーターサービス実装

## タスクの目的

Obsidian形式のMarkdownファイルを生成し、論文ネットワークを可視化するためのMarkdownジェネレーターサービスを実装する。Phase 3の最終出力サービスとして機能する。

## 前提条件

- Phase 2 が完了している
- データベースモデルが利用可能
- 共通ライブラリ（shared）が利用可能
- 環境設定管理システムが動作

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
    "networkx>=3.0.0",
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
    "E", "W", "F", "I", "B", "C4", "UP",
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

### 4. Markdownジェネレーターサービス

`src/refnet_generator/services/generator_service.py`:

```python
"""Markdownジェネレーターサービス."""

from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader
import networkx as nx
from refnet_shared.models.database import Paper, Author, PaperRelation
from refnet_shared.models.database_manager import db_manager
from refnet_shared.config.environment import load_environment_settings
import structlog


logger = structlog.get_logger(__name__)
settings = load_environment_settings()


class GeneratorService:
    """Markdownジェネレーターサービス."""

    def __init__(self):
        """初期化."""
        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        self.output_dir = Path(settings.output_dir)
        self.output_dir.mkdir(exist_ok=True)

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
        authors = session.query(Author).join(
            Author.papers
        ).filter(Paper.paper_id == paper.paper_id).all()

        # 関連論文取得
        citations = session.query(PaperRelation).filter_by(
            target_paper_id=paper.paper_id,
            relation_type="citation"
        ).limit(10).all()

        references = session.query(PaperRelation).filter_by(
            source_paper_id=paper.paper_id,
            relation_type="reference"
        ).limit(10).all()

        # テンプレートレンダリング
        template = self.jinja_env.get_template("paper.md.j2")
        content = template.render(
            paper=paper,
            authors=authors,
            citations=citations,
            references=references,
            generated_at=datetime.now().isoformat()
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
        relations = session.query(PaperRelation).filter(
            (PaperRelation.source_paper_id == paper_id) |
            (PaperRelation.target_paper_id == paper_id)
        ).all()

        for relation in relations:
            G.add_edge(relation.source_paper_id, relation.target_paper_id,
                      relation_type=relation.relation_type)

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
            generated_at=datetime.now().isoformat()
        )

        # ファイル保存
        file_path = self.output_dir / f"{paper_id}_network.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Network diagram generated", paper_id=paper_id, file_path=str(file_path))

    async def _update_index_file(self, session: Session) -> None:
        """インデックスファイルの更新."""
        # 全論文のリスト取得
        papers = session.query(Paper).filter(
            Paper.summary_status == "completed"
        ).order_by(Paper.citation_count.desc()).limit(100).all()

        # 統計情報
        stats = {
            "total_papers": session.query(Paper).count(),
            "completed_papers": session.query(Paper).filter(
                Paper.summary_status == "completed"
            ).count(),
            "generated_at": datetime.now().isoformat()
        }

        # テンプレートレンダリング
        template = self.jinja_env.get_template("index.md.j2")
        content = template.render(
            papers=papers,
            stats=stats
        )

        # ファイル保存
        file_path = self.output_dir / "index.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Index file updated", total_papers=len(papers))
```

### 5. Jinja2テンプレート

`src/refnet_generator/templates/paper.md.j2`:

```jinja2
# {{ paper.title or "Unknown Title" }}

## 基本情報

- **Paper ID**: {{ paper.paper_id }}
- **年**: {{ paper.year or "不明" }}
- **引用数**: {{ paper.citation_count }}
- **参考文献数**: {{ paper.reference_count }}

{% if authors %}
## 著者
{% for author in authors %}
- {{ author.name }}
{% endfor %}
{% endif %}

## 概要

{{ paper.abstract or "概要なし" }}

{% if paper.summary %}
## AI要約

{{ paper.summary }}

*要約生成モデル: {{ paper.summary_model }}*
{% endif %}

## 関連論文

{% if citations %}
### 本論文を引用している論文
{% for citation in citations %}
- [[{{ citation.source_paper_id }}]]
{% endfor %}
{% endif %}

{% if references %}
### 本論文が引用している論文
{% for reference in references %}
- [[{{ reference.target_paper_id }}]]
{% endfor %}
{% endif %}

## メタデータ

- **クロール状態**: {{ paper.crawl_status }}
- **PDF状態**: {{ paper.pdf_status }}
- **要約状態**: {{ paper.summary_status }}
- **生成日時**: {{ generated_at }}

{% if paper.pdf_url %}
## リンク

- [PDF]( {{ paper.pdf_url }} )
{% endif %}

## ネットワーク

- [[{{ paper.paper_id }}_network|ネットワーク図]]

---
*Generated by RefNet v0.1.0*
```

`src/refnet_generator/templates/network.md.j2`:

```jinja2
# {{ paper_id }} - ネットワーク図

## ネットワーク統計

- **総ノード数**: {{ network_stats.total_nodes }}
- **総エッジ数**: {{ network_stats.total_edges }}
- **入次数**: {{ network_stats.in_degree }}
- **出次数**: {{ network_stats.out_degree }}

## 関係図

```mermaid
graph TD
    {{ paper_id }}[{{ paper_id }}]

    {% for relation in relations %}
    {% if relation.relation_type == "citation" %}
    {{ relation.source_paper_id }} --> {{ relation.target_paper_id }}
    {% elif relation.relation_type == "reference" %}
    {{ relation.source_paper_id }} -.-> {{ relation.target_paper_id }}
    {% endif %}
    {% endfor %}
```

## 関係リスト

{% for relation in relations %}
- {{ relation.source_paper_id }} {{ "→" if relation.relation_type == "citation" else "⇢" }} {{ relation.target_paper_id }} ({{ relation.relation_type }})
{% endfor %}

---
*Generated at: {{ generated_at }}*
```

### 6. Celeryタスク定義

`src/refnet_generator/tasks/__init__.py`:

```python
"""Celeryタスク定義."""

import asyncio
from celery import Celery
from refnet_shared.config.environment import load_environment_settings
from refnet_generator.services.generator_service import GeneratorService
import structlog


logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# Celeryアプリケーション
celery_app = Celery(
    "refnet_generator",
    broker=settings.celery_broker_url or settings.redis.url,
    backend=settings.celery_result_backend or settings.redis.url,
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
    task_time_limit=600,  # 10分
    task_soft_time_limit=540,  # 9分
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(bind=True, name="refnet.generator.generate_markdown")
def generate_markdown_task(self, paper_id: str) -> bool:
    """Markdown生成タスク."""
    logger.info("Starting markdown generation task", paper_id=paper_id)

    async def _generate():
        service = GeneratorService()
        return await service.generate_markdown(paper_id)

    try:
        result = asyncio.run(_generate())
        logger.info("Markdown generation task completed", paper_id=paper_id, success=result)
        return result
    except Exception as e:
        logger.error("Markdown generation task failed", paper_id=paper_id, error=str(e))
        raise self.retry(exc=e, countdown=60, max_retries=2)


@celery_app.task(name="refnet.generator.batch_generate")
def batch_generate_task(paper_ids: list[str]) -> dict:
    """バッチ生成タスク."""
    logger.info("Starting batch generation task", paper_count=len(paper_ids))

    results = {}
    for paper_id in paper_ids:
        result = generate_markdown_task.delay(paper_id)
        results[paper_id] = result.id

    return results
```

### 7. Dockerfileの作成

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

# 起動コマンド
CMD ["celery", "-A", "refnet_generator.tasks.celery_app", "worker", "--loglevel=info", "--queue=generate"]
```

## スコープ

- Obsidian形式Markdown生成
- 論文ネットワーク図生成
- Jinja2テンプレートシステム
- Celeryタスクの実装
- 基本的なテストケース

**スコープ外:**
- 高度なグラフ可視化
- 動的なネットワーク分析
- カスタムテンプレート管理
- リアルタイム生成

## 参照するドキュメント

- `/docs/generator/templates.md`
- `/docs/development/coding-standards.md`
- `/docs/tasks/phase_02/00_database_models.md`

## 完了条件

### 必須条件
- [ ] Markdownジェネレーターサービスが実装されている
- [ ] Jinja2テンプレートが作成されている
- [ ] Celeryタスクが実装されている
- [ ] 基本的なテストケースが作成されている
- [ ] Dockerfileが作成されている
- [ ] `cd package/generator && moon run generator:check` が正常終了する

### 動作確認
- [ ] Markdown生成が正常動作
- [ ] テンプレートレンダリングが正常動作
- [ ] Celeryワーカーが正常動作
- [ ] ファイル出力が適切に動作

### テスト条件
- [ ] 単体テストが作成されている
- [ ] 統合テストが作成されている
- [ ] テストカバレッジが80%以上
- [ ] 型チェックが通る
- [ ] リントチェックが通る

## レビュー観点

### 技術的正確性と実装の妥当性
- [ ] Jinja2テンプレートシステムが適切に実装されている
- [ ] NetworkXを使用したネットワーク解析が正しく実装されている
- [ ] Markdownファイル生成ロジックが適切である
- [ ] ファイル出力処理が安全である（パストラバーサル対策）
- [ ] テンプレートレンダリングのエラーハンドリングが適切である
- [ ] 非同期処理が適切に実装されている

### 統合性と連携
- [ ] データベースモデルとの整合性が取れている
- [ ] Celeryタスクキューイングが正しく実装されている
- [ ] 他のサービスとの連携インターフェースが適切である
- [ ] 共通ライブラリ（shared）の使用が適切である
- [ ] 環境設定管理が統一されている

### 品質標準
- [ ] エラーハンドリングが包括的で一貫している
- [ ] ログ出力が適切で運用可能である（structlog使用）
- [ ] テストカバレッジが80%以上である
- [ ] 型ヒントが適切に使用されている
- [ ] コーディング規約に準拠している
- [ ] モックを使用した適切なテストが作成されている

### セキュリティとパフォーマンス
- [ ] ファイルシステムへのアクセスが適切に制御されている
- [ ] メモリ使用量が適切に管理されている
- [ ] 大規模データ処理時のパフォーマンスが考慮されている
- [ ] ファイル書き込みのアトミック性が確保されている
- [ ] 同時実行時の競合状態対策が実装されている
- [ ] ディスク容量の管理が適切である

### 保守性とドキュメント
- [ ] コードが読みやすく保守しやすい構造になっている
- [ ] 適切なDocstringとコメントが記述されている
- [ ] テンプレートファイルが保守しやすい構造になっている
- [ ] 設定ファイル（pyproject.toml、moon.yml）が適切に構成されている
- [ ] Dockerfileが本番環境を考慮した設計になっている
- [ ] 依存関係管理が適切である

### ジェネレーター固有の観点
- [ ] Obsidian形式の適合性が確保されている（リンク、タグ等）
- [ ] Mermaid図表の正しいシンタックスが使用されている
- [ ] ネットワーク統計情報の精度が適切である
- [ ] インデックスファイルの更新機構が適切である
- [ ] テンプレートのカスタマイズ性が考慮されている
- [ ] バッチ生成と単一生成のバランスが適切である

## 次のタスクへの引き継ぎ

### Phase 4 への前提条件
- ジェネレーターサービスが動作確認済み
- 他のPhase 3サービスとの連携が確認済み
- 基本的なE2Eテストが完了

### 引き継ぎファイル
- `package/generator/` - ジェネレーターサービス実装
- Markdownテンプレート
- テストファイル・設定ファイル
