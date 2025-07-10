# システムアーキテクチャ図

## 概要

RefNetは、学術論文の参照関係を分析・可視化するシステムです。本ドキュメントでは、システム全体のアーキテクチャとコンポーネント間の関係を説明します。

## システム全体図

```mermaid
graph TB
    subgraph "外部サービス"
        SS[Semantic Scholar API]
        LLM[LLM API<br/>Claude/GPT]
    end

    subgraph "フロントエンド"
        OBS[Obsidian<br/>ローカルPC]
    end

    subgraph "RefNet Core System"
        subgraph "API Gateway"
            NGINX[Nginx<br/>リバースプロキシ]
        end

        subgraph "APIサービス"
            API[RefNet API<br/>FastAPI]
        end

        subgraph "バックグラウンドサービス"
            CRAWLER[Crawler Service<br/>論文収集]
            SUMMARIZER[Summarizer Service<br/>要約生成]
            GENERATOR[Generator Service<br/>Obsidian形式生成]
        end

        subgraph "メッセージキュー"
            REDIS[Redis<br/>Celeryブローカー]
            CELERY[Celery Workers]
            BEAT[Celery Beat<br/>スケジューラ]
        end

        subgraph "データストレージ"
            POSTGRES[(PostgreSQL<br/>メインDB)]
            OBSIDIAN_VAULT[Obsidian Vault<br/>ローカルストレージ]
        end

        subgraph "監視・可観測性"
            PROM[Prometheus<br/>メトリクス収集]
            GRAFANA[Grafana<br/>ダッシュボード]
            FLOWER[Flower<br/>Celery監視]
        end
    end

    %% データフロー
    OBS -->|API呼び出し| NGINX
    NGINX -->|リクエスト転送| API

    API -->|タスク登録| REDIS
    REDIS -->|タスク配信| CELERY

    CELERY -->|実行| CRAWLER
    CELERY -->|実行| SUMMARIZER
    CELERY -->|実行| GENERATOR

    BEAT -->|スケジュール| REDIS

    CRAWLER -->|論文取得| SS
    SUMMARIZER -->|要約生成| LLM

    CRAWLER -->|保存| POSTGRES
    SUMMARIZER -->|保存| POSTGRES
    GENERATOR -->|ファイル生成| OBSIDIAN_VAULT

    API -->|読み取り| POSTGRES
    OBS -->|読み取り| OBSIDIAN_VAULT

    %% 監視
    API -.->|メトリクス| PROM
    CELERY -.->|メトリクス| PROM
    POSTGRES -.->|メトリクス| PROM
    REDIS -.->|メトリクス| PROM

    PROM -->|データ提供| GRAFANA
    CELERY -.->|タスク情報| FLOWER
```

## コンポーネント詳細

### 1. フロントエンド層

#### Obsidian
- **役割**: 論文ネットワークの可視化
- **実行環境**: ローカルPC
- **通信**: RefNet APIと連携してデータ取得

### 2. API Gateway層

#### Nginx
- **役割**: リバースプロキシ、負荷分散
- **ポート**: 80 (HTTP), 443 (HTTPS)
- **機能**:
  - リクエストルーティング
  - SSL/TLS終端
  - 静的コンテンツ配信

### 3. アプリケーション層

#### RefNet API
- **フレームワーク**: FastAPI
- **ポート**: 8000
- **主要エンドポイント**:
  - `/papers`: 論文情報の取得・更新
  - `/jobs`: ジョブの作成・管理
  - `/metrics`: Prometheusメトリクス

### 4. バックグラウンドサービス層

#### Crawler Service
- **機能**: Semantic Scholar APIから論文情報を収集
- **トリガー**: APIリクエストまたはスケジュール実行

#### Summarizer Service
- **機能**: LLM APIを使用して論文要約を生成
- **LLM**: Claude 3.5 Sonnet / GPT-4

#### Generator Service
- **機能**: Obsidian用のMarkdownファイル生成
- **出力**: 構造化されたノートファイル

### 5. メッセージキュー層

#### Redis
- **役割**: Celeryのメッセージブローカー
- **ポート**: 6379
- **永続化**: AOF (Append Only File)

#### Celery Workers
- **並列度**: 4ワーカープロセス
- **キュー**: default, crawler, summarizer, generator

#### Celery Beat
- **役割**: 定期タスクのスケジューリング
- **スケジュール**:
  - 論文更新チェック: 毎日午前2時
  - メトリクス集計: 1時間ごと

### 6. データストレージ層

#### PostgreSQL
- **バージョン**: 15
- **ポート**: 5432
- **主要テーブル**:
  - papers: 論文メタデータ
  - citations: 引用関係
  - summaries: 要約データ
  - jobs: ジョブ管理

#### ローカルストレージ
- **用途**: Obsidian Vaultファイル
- **形式**: Markdown (.md)
- **構造**: 年/月/論文ID.md

### 7. 監視・可観測性層

#### Prometheus
- **ポート**: 9090
- **スクレイプ間隔**: 15秒
- **データ保持期間**: 15日

#### Grafana
- **ポート**: 3000
- **ダッシュボード**:
  - システム全体監視
  - Celeryタスク監視
  - データベース性能

#### Flower
- **ポート**: 5555
- **機能**: Celeryタスクのリアルタイム監視

## ネットワーク構成

```mermaid
graph LR
    subgraph "Docker Network: refnet-network"
        API[API<br/>:8000]
        NGINX[Nginx<br/>:80]
        POSTGRES[PostgreSQL<br/>:5432]
        REDIS[Redis<br/>:6379]
        PROM[Prometheus<br/>:9090]
        GRAFANA[Grafana<br/>:3000]
        FLOWER[Flower<br/>:5555]
    end

    subgraph "ホストマシン"
        HOST[localhost]
    end

    HOST -->|80| NGINX
    HOST -->|3000| GRAFANA
    HOST -->|5555| FLOWER
    HOST -->|9090| PROM
```

## セキュリティ考慮事項

1. **ネットワーク分離**: すべてのサービスは専用Dockerネットワーク内で通信
2. **認証**: API認証にJWT使用（将来実装）
3. **シークレット管理**: 環境変数による管理
4. **監査ログ**: すべてのAPIアクセスをログ記録

## スケーラビリティ

1. **水平スケーリング**: Celeryワーカーの追加が容易
2. **キャッシュ**: Redis によるクエリキャッシュ（将来実装）
3. **非同期処理**: 重い処理はすべてCeleryタスク化

## デプロイメント

すべてのサービスはDocker Composeで管理され、単一のコマンドで起動可能：

```bash
docker-compose up -d
```

詳細な起動手順は[運用手順書](../operations/startup-shutdown.md)を参照してください。
