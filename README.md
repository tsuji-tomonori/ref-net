# ref-net

[![CI](https://github.com/tsuji-tomonori/ref-net/actions/workflows/ci.yml/badge.svg)](https://github.com/tsuji-tomonori/ref-net/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Moon](https://img.shields.io/badge/moon-task_runner-purple.svg)](https://moonrepo.dev/)
[![uv](https://img.shields.io/badge/uv-package_manager-green.svg)](https://docs.astral.sh/uv/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-database-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-cache-red.svg)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-task_queue-green.svg)](https://docs.celeryproject.org/)
[![Docker](https://img.shields.io/badge/Docker-containerization-blue.svg)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-web_framework-green.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red.svg)](https://www.sqlalchemy.org/)
[![Ruff](https://img.shields.io/badge/Ruff-linter-yellow.svg)](https://docs.astral.sh/ruff/)
[![MyPy](https://img.shields.io/badge/MyPy-type_checker-blue.svg)](https://mypy.readthedocs.io/)
[![pytest](https://img.shields.io/badge/pytest-testing-orange.svg)](https://docs.pytest.org/)

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
