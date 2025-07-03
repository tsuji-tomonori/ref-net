## 1. はじめに

本設計書は、ObsidianによるRAG論文関係性の可視化システムのシステム設計をまとめたものである。
本システムは、Docker Composeによるローカル環境で動作し、論文IDを起点に引用・被引用関係を再帰的に収集し、Obsidian用のマークダウンファイルを自動生成する。

## 2. システム全体構成

### 2.1 Docker Compose構成

本システムはローカルPC上でDocker Composeを使用して動作する。以下のコンテナで構成される：

```yaml
# docker-compose.yml概要
services:
  # API Gateway & オーケストレーター
  api:
    - FastAPI/Flask
    - 論文検索・登録エンドポイント
    - ジョブキュー管理

  # 論文メタデータ収集ワーカー
  crawler:
    - Semantic Scholar API連携
    - 引用・被引用関係の収集
    - メタデータ抽出

  # PDF要約サービス
  summarizer:
    - PDFダウンロード・パース
    - LLM連携（OpenAI/Claude API）
    - 要約・キーワード抽出

  # Markdownジェネレーター
  markdown-generator:
    - Obsidianフォーマット生成
    - グラフビュー用メタデータ付与
    - ファイル出力

  # PostgreSQLデータベース
  postgres:
    - 論文メタデータ永続化
    - 処理状態管理
    - 関係性グラフデータ

  # Redisキャッシュ&キュー
  redis:
    - ジョブキュー（Celery）
    - APIレスポンスキャッシュ
    - レート制限カウンター
```

### 2.2 データフロー

```
[ユーザー] → 論文ID投入
    ↓
Paper Processor → PostgreSQL
    ↓
Obsidian Vault (./output/)

[ユーザー] → PDF要約リクエスト
    ↓
PDF Summarizer → PostgreSQL
    ↓
Obsidian Vault更新
```

### 2.3 モノレポ構成

- ルートディレクトリ: Monorepo (MoonRepo)

  - `docs/` (設計書・仕様書)
  - `package/`
    - `api/` (FastAPI/Flaskアプリケーション)
    - `crawler/` (論文メタデータ収集ワーカー)
    - `summarizer/` (PDF要約サービス)
    - `generator/` (Markdownジェネレーター)
    - `shared/` (共通ライブラリ・モデル)
  - `docker/` (Dockerfile群)
  - `output/` (生成されたObsidianファイル)

## 3. コンポーネント設計

### 3.1 Paper Processorサービス

- コマンドライン実行: `python -m paper_processor <paper_id>`
- 機能:
  1. Semantic Scholar APIから論文情報取得
  2. 引用・被引用関係の収集
  3. PostgreSQLにデータ保存
  4. Obsidian形式のMarkdown生成
  5. 重み付けによる再帰的処理
- レート制限対応（リトライ・バックオフ）

### 3.2 PDF Summarizerサービス

- コマンドライン実行: `python -m pdf_summarizer <paper_id>`
- 機能:
  1. PostgreSQLから論文情報取得
  2. PDF URL取得・ダウンロード
  3. テキスト抽出（PyPDF2/pdfplumber）
  4. LLM APIで要約生成
  5. PostgreSQLに要約保存
  6. Markdownファイル更新

### 3.3 Semantic Scholar API利用

- エンドポイント: `https://api.semanticscholar.org/graph/v1/paper/{paper_id}`
- 取得フィールド:
  - 基本情報: `title`, `authors`, `year`, `abstract`, `citationCount`
  - 関連論文: `references`, `citations`
  - フィールド: `fieldsOfStudy`
- API制限:
  - 100リクエスト/5分（API key未使用時）
  - 1000リクエスト/5分（API key使用時）
- エラーハンドリング: 404 (論文未発見), 429 (レート制限), 500 (サーバエラー)

### 3.4 PostgreSQLデータベース

#### 3.4.1 テーブル設計

- **papers**テーブル:
  - `paper_id` (VARCHAR, PK)
  - `title` (TEXT)
  - `authors` (JSONB)
  - `year` (INTEGER)
  - `abstract` (TEXT)
  - `citation_count` (INTEGER)
  - `fields_of_study` (JSONB)
  - `pdf_url` (TEXT)
  - `summary` (TEXT) - AI生成要約
  - `keywords` (JSONB) - AI抽出キーワード
  - `processed_at` (TIMESTAMP)
  - `created_at` (TIMESTAMP)
  - `updated_at` (TIMESTAMP)

- **paper_relations**テーブル:
  - `source_paper_id` (VARCHAR, FK)
  - `target_paper_id` (VARCHAR, FK)
  - `relation_type` (ENUM: 'cites', 'cited_by')
  - `created_at` (TIMESTAMP)
  - PRIMARY KEY (source_paper_id, target_paper_id, relation_type)

- **processing_queue**テーブル:
  - `id` (SERIAL, PK)
  - `paper_id` (VARCHAR)
  - `priority` (INTEGER) - 重み付けスコア
  - `status` (ENUM: 'pending', 'processing', 'completed', 'failed')
  - `retry_count` (INTEGER)
  - `error_message` (TEXT)
  - `created_at` (TIMESTAMP)
  - `updated_at` (TIMESTAMP)

#### 3.4.2 インデックス

- `idx_papers_year` (year)
- `idx_papers_citation` (citation_count DESC)
- `idx_queue_status_priority` (status, priority DESC)
- `idx_relations_target` (target_paper_id)

## 4. ワークフロー詳細

### 4.1 論文メタデータ収集フロー

1. ユーザーがPaper Processorに論文IDを指定
2. Semantic Scholar APIから論文情報取得
3. PostgreSQLにメタデータ保存
4. Obsidian形式のMarkdown生成・保存
5. 引用・被引用論文を重み付け順に再帰的処理

### 4.2 PDF要約フロー（独立サイクル）

1. ユーザーがPDF Summarizerに論文IDを指定
2. PostgreSQLから論文情報取得
3. PDF URL取得・ダウンロード
4. LLM APIで要約生成
5. PostgreSQLに要約保存
6. 既存Markdownファイルを更新

## 5. コンテナ間通信

### 5.1 ネットワーク構成

- Docker Composeネットワーク: `refnet-network`
- コンテナ名で相互参照
- ポートマッピング:
  - PostgreSQL: 5432:5432

### 5.2 環境変数

```yaml
# .envファイル
DATABASE_URL=postgresql://user:password@postgres:5432/refnet
SEMANTIC_SCHOLAR_API_KEY=オプション
OPENAI_API_KEY=PDF要約用
OUTPUT_DIR=./output
```

## 6. テスト・CI/CD

- テスト駆動開発 (TDD): pytest + MyPy + Ruff
- モック化: 外部API・データベース接続

## 7. 非機能要件

- ローカル実行: Docker Composeで完結
- シンプルな構成: 必要最小限のコンテナと依存関係
- レート制限対応: リトライ・バックオフ
- 運用性: Monorepo管理 + MoonRepo

## 8. 図表作成指針

### 8.1 アーキテクチャ図

- Docker Composeコンテナ構成をMermaidで表現
- ユーザー → Paper Processor/PDF Summarizer → PostgreSQL → Obsidian Vault
- Semantic Scholar API・LLM APIへの外部接続
- 詳細: [architecture.md](../design/architecture.md)

### 8.2 シーケンス図

- アクター: User, PaperProcessor, PDFSummarizer, PostgreSQL, SemanticScholar, LLM
- メタデータ収集フロー: 論文ID投入から再帰的処理
- PDF要約フロー: 独立した要約処理
- 詳細: [sequence.md](../design/sequence.md)

### 8.3 フローチャート図

- Paper Processor処理フロー
- PDF Summarizer処理フロー
- 詳細:
  - [Paper Processor](../spec/flowchart/paper_processor.md)
  - [PDF Summarizer](../spec/flowchart/pdf_summarizer.md)

### 8.4 テーブル定義書

- papers テーブル: 論文メタデータ
- paper_relations テーブル: 引用関係
- processing_queue テーブル: 処理キュー
- 詳細: [PostgreSQLテーブル](../spec/table/postgresql_tables.md)

### 8.5 ストレージ仕様書

- ローカル出力ディレクトリ: `./output/`
- Markdownファイル命名規則: `{paper_id}.md`
- PostgreSQLデータベース容量設計
- 詳細:
  - [ローカルストレージ](../spec/storage/local_storage.md)
  - [PostgreSQL容量](../spec/storage/postgresql_capacity.md)
