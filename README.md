# ref-net

[![CI](https://github.com/tsuji-tomonori/ref-net/actions/workflows/ci.yml/badge.svg)](https://github.com/tsuji-tomonori/ref-net/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/tsuji-tomonori/ref-net/branch/main/graph/badge.svg?token=YOUR_TOKEN)](https://codecov.io/gh/tsuji-tomonori/ref-net)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=tsuji-tomonori_ref-net&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=tsuji-tomonori_ref-net)

### 🔧 Core Technologies
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7+-DC382D.svg)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-24+-2496ED.svg)](https://www.docker.com/)
[![Docker Compose](https://img.shields.io/badge/Docker_Compose-2+-2496ED.svg)](https://docs.docker.com/compose/)

### 🛠️ Development Tools
[![Moon](https://img.shields.io/badge/moon-task_runner-7F52FF.svg)](https://moonrepo.dev/)
[![uv](https://img.shields.io/badge/uv-0.4+-00ADD8.svg)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/Ruff-0.12+-D7FF64.svg)](https://docs.astral.sh/ruff/)
[![MyPy](https://img.shields.io/badge/MyPy-1.16+-1E5082.svg)](https://mypy.readthedocs.io/)
[![pytest](https://img.shields.io/badge/pytest-8.4+-0A9EDC.svg)](https://docs.pytest.org/)
[![pre-commit](https://img.shields.io/badge/pre--commit-3.5+-FAB040.svg)](https://pre-commit.com/)

### 📦 Backend Components
[![Celery](https://img.shields.io/badge/Celery-5.3+-37814A.svg)](https://docs.celeryproject.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00.svg)](https://www.sqlalchemy.org/)
[![Pydantic](https://img.shields.io/badge/Pydantic-2.0+-E92063.svg)](https://docs.pydantic.dev/)
[![Alembic](https://img.shields.io/badge/Alembic-1.13+-6BA81E.svg)](https://alembic.sqlalchemy.org/)
[![httpx](https://img.shields.io/badge/httpx-0.27+-0055FF.svg)](https://www.python-httpx.org/)
[![Jinja2](https://img.shields.io/badge/Jinja2-3.1+-B41717.svg)](https://jinja.palletsprojects.com/)

### 📊 Monitoring & Observability
[![Prometheus](https://img.shields.io/badge/Prometheus-2.48+-E6522C.svg)](https://prometheus.io/)
[![Grafana](https://img.shields.io/badge/Grafana-10+-F46800.svg)](https://grafana.com/)
[![Flower](https://img.shields.io/badge/Flower-2.0+-007A88.svg)](https://flower.readthedocs.io/)

### 🌐 Infrastructure
[![Nginx](https://img.shields.io/badge/Nginx-1.25+-009639.svg)](https://nginx.org/)
[![Semantic Scholar](https://img.shields.io/badge/Semantic_Scholar-API-005A9C.svg)](https://www.semanticscholar.org/product/api)
[![Claude](https://img.shields.io/badge/Claude-3.5_Sonnet-7C3AED.svg)](https://www.anthropic.com/claude)
[![Obsidian](https://img.shields.io/badge/Obsidian-1.5+-7C3AED.svg)](https://obsidian.md/)

論文のつながりを表現するRAGシステム

## 概要

"Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"を起点として、参照文献・被引用文献を網羅的に収集し、Obsidianで論文ネットワークを可視化するシステムです。

## ドキュメント

### 設計ドキュメント

| カテゴリ | ドキュメント | 概要 |
|----------|-------------|------|
| 🏗️ アーキテクチャ | [アーキテクチャ図](docs/design/architecture.md) | システム全体の構成とコンポーネント関係 |
| 🔄 シーケンス | [シーケンス図](docs/design/sequence.md) | 主要な処理フローとデータの流れ |
| 📋 システム設計 | [システム設計書](docs/design/system_design.md) | 詳細な設計仕様と技術選択 |

### 開発ガイド

| カテゴリ | ドキュメント | 概要 |
|----------|-------------|------|
| 📏 コーディング規約 | [基本規約](docs/development/coding-standards.md) | Python開発の基本ルールとベストプラクティス |
| 🧪 テスト規約 | [テスト実装](docs/development/coding-test.md) | pytest実装規約とテスト戦略 |

### 仕様書

| カテゴリ | ドキュメント | 概要 |
|----------|-------------|------|
| 🗄️ データベース | [テーブル定義](docs/spec/table/postgresql_tables.md) | PostgreSQLテーブル設計と関係 |
| 📊 フローチャート | [論文処理](docs/spec/flowchart/paper_processor.md) | 論文データ処理フロー |
| 📄 PDF要約 | [要約処理](docs/spec/flowchart/pdf_summarizer.md) | PDF要約処理の詳細フロー |
| 🗂️ ストレージ | [ローカルストレージ](docs/spec/storage/local_storage.md) | ファイル管理とディレクトリ構成 |
| ⚡ キュー | [Celeryキュー](docs/spec/queue/celery_queue.md) | 非同期タスク処理の設計 |

### 開発フェーズ

| フェーズ | ドキュメント | 概要 |
|----------|-------------|------|
| Phase 1 | [基盤構築](docs/tasks/phase_01/README.md) | プロジェクト構造・モノレポ・環境設定 |
| Phase 2 | [データベース](docs/tasks/phase_02/README.md) | モデル定義・マイグレーション |
| Phase 3 | [サービス実装](docs/tasks/phase_03/README.md) | API・クローラー・要約・生成サービス |
| Phase 4 | [運用基盤](docs/tasks/phase_04/README.md) | Docker・監視・セキュリティ・バッチ |

## 🚀 クイックスタート

### Docker環境での起動

```bash
# プロジェクトルートで実行
docker-compose up -d

# 各サービスの確認
docker-compose ps
```

### 監視UI

#### Flower (Celery監視)

Celeryタスクキューの監視とデバッグには[Flower](https://flower.readthedocs.io/)を使用します。

- **URL**: [http://localhost:5555](http://localhost:5555)
- **認証**: Basic認証（初期値: admin / secure_password）
- **機能**:
  - タスクの実行状況確認
  - ワーカーのステータス監視
  - タスクの実行履歴とエラー情報
  - Celery Beatスケジュールの確認

認証情報は`.env`ファイルで変更可能です：
```bash
FLOWER_USER=your_username
FLOWER_PASSWORD=your_secure_password
```
