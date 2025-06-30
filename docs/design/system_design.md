## 1. はじめに

本設計書は、ObsidianによるRAG論文関係性の可視化システムのシステム設計をまとめたものである。
本システムは、手動投入された論文IDを起点に、SQS→Lambda→Obsidianマークダウン自動生成→S3保存→DynamoDB登録→再投入フローを繰り返し、引用・被引用関係を重み付け順に処理する。

## 2. システム全体構成

```
[ユーザー] →(手動投入)→ SQS (入力キュー)
    ↓Lambda①
Obsidian用Markdown生成 ─→ S3 (マークダウンファイル)
    ↓DynamoDB登録
引用・被引用情報取得・重み判定 → SQS (優先キュー)
    ↓Lambda② (救い上げ)
タイムアウト処理 → DynamoDBフラグ更新

GitHub Actions: S3からマークダウン取得 → PR自動作成
```

### 2.1 モノレポ構成

- ルートディレクトリ: Monorepo (MoonRepo)

  - `docs/` (設計書・仕様書)
  - `package/`

    - `infra/` (CDKでAWSリソース定義)
    - `batch/` (Lambda関数群、テストコード含む)

## 3. コンポーネント設計

### 3.1 SQS キュー

- 入力キュー: `paper-processing-queue`

  - イベント: `{ paper_id: string }`
  - 可視性タイムアウト: 1日
  - メッセージ保持期間: 1日
- 救い上げキュー (DLQとは別): `paper-retry-queue`

  - 手動または自動クリア用

### 3.2 Lambda① (初期処理)

- トリガー: `paper-processing-queue`
- 用途:

  1. Semantic Scholar APIから論文情報・参照・引用リスト取得
  2. Obsidianマークダウン生成
  3. S3へファイル保存 (`bucket/〈paper_id〉.md`)
  4. DynamoDBにレコード登録/更新
  5. 参照・引用先を重み付け順にSQSへ登録
- 入力例:

  ```json
  { "paper_id": "10.1234/abcd.efgh" }
  ```

#### 3.2.1 Semantic Scholar API利用

- エンドポイント: `https://api.semanticscholar.org/graph/v1/paper/{paper_id}`
- 取得フィールド:
  - 基本情報: `title`, `authors`, `year`, `abstract`, `citationCount`
  - 関連論文: `references`, `citations`
  - フィールド: `fieldsOfStudy`
- API制限:
  - 100リクエスト/5分（API key未使用時）
  - 1000リクエスト/5分（API key使用時）
- エラーハンドリング: 404 (論文未発見), 429 (レート制限), 500 (サーバエラー)

### 3.3 Lambda② (救い上げ処理)

- 実行方法: Lambdaコンソールから手動起動
- 用途:

  - `paper-processing-queue`から期限切れで消失したIDをDynamoDBから取得
  - まだ未処理フラグの論文を再度Semantic Scholar APIで取得 → マークダウン生成 → S3
  - 処理完了フラグ更新

### 3.4 S3 バケット

- 用途: Markdownファイルの保存先
- ファイル構成: `papers/〈paper_id〉.md`
- バージョニング: 有効化

### 3.5 DynamoDB テーブル

- テーブル名: `PaperRecords`
- PK: `paper_id` (文字列)
- 属性:

  - `processed`: boolean (処理完了フラグ)
  - `citation_count`: number
  - `reference_count`: number
  - `last_updated`: ISO8601 timestamp

## 4. ワークフロー詳細

1. ユーザーが論文IDイベントを`paper-processing-queue`へ手動投入
2. Lambda①起動 → Semantic Scholar APIから論文メタ取得 → Markdown生成 → S3保存
3. 同時にDynamoDBにレコード作成 (processed=false)
4. 取得した参照・引用データから重み付け (=引用数+参照数) を計算
5. 重み順に同キューへ新規エントリ投入
6. キュー期限切れ分はLambda②で補完処理（Semantic Scholar API再呼び出し）
7. S3上のMarkdownはGitHub Actionsで定期pull & PR作成

## 5. テスト・CI/CD

- テスト駆動開発 (TDD): pytest + MyPy + Ruff
- CI/CD: GitHub Actions

  - プッシュ時: インフラ(CDK synth/test)、ユニットテスト実行
  - スケジュール: 既存S3ファイル pull & PR作成

## 6. 非機能要件

- コスト最適化: サーバレス＆従量課金
- 可用性: SQSの保持期間切れを救い上げLambdaで補完
- 運用性: Monorepo管理 + MoonRepo

## 7. 図表作成指針

### 7.1 アーキテクチャ図

- AWSサービス間の関係をdrawioで表現
- ユーザー → SQS → Lambda① → (S3, DynamoDB) → Lambda② の主要フロー
- Semantic Scholar APIへの外部接続
- GitHub Actionsによる定期処理
- 詳細: [architecture.drawio](../design/architecture.drawio)

### 7.2 シーケンス図

- アクター: User, SQS, Lambda①, SemanticScholar, S3, DynamoDB, Lambda②
- 正常フロー: 論文ID投入から重み付け再投入まで
- 異常フロー: 救い上げ処理とエラーハンドリング
- 詳細: [sequence.md](../design/sequence.md)

### 7.3 フローチャート図

- Lambda①の処理フロー（API呼び出し → マークダウン生成 → 保存 → 重み計算 → 再投入）
- Lambda②の処理フロー（救い上げ処理とエラーハンドリング）
- 詳細:
  - [Lambda① 初期処理](../spec/flowchart/lambda_initial.md)
  - [Lambda② 救い上げ処理](../spec/flowchart/lambda_retry.md)

### 7.4 テーブル定義書

- PaperRecordsテーブル: PK, 属性, データ型, 制約
- インデックス設計: GSI不要（単純なPK検索のみ）
- TTL設定: 不要（永続保存）
- 詳細: [PaperRecords](../spec/table/paper_records.md)

### 7.5 ストレージ仕様書

- S3バケット設計: フォルダ構成, ファイル命名規則, アクセス権限
- DynamoDB容量設計: オンデマンドとプロビジョニング比較
- データライフサイクル: バージョニング, 削除ポリシー
- 詳細:
  - [S3バケット](../spec/storage/s3_bucket.md)
  - [DynamoDBテーブル](../spec/storage/dynamodb_table.md)
