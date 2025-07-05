# シーケンス図

本文書は、RAG論文関係性可視化システムの処理フローをシーケンス図で表現したものです。

## 論文メタデータ収集フロー

論文IDを起点として、引用・被引用関係を再帰的に収集する処理フローです。

```mermaid
sequenceDiagram
    participant User as User
    participant PP as PaperProcessor
    participant DB as PostgreSQL
    participant SS as SemanticScholar
    participant Gen as MarkdownGenerator
    participant OV as ObsidianVault

    User->>PP: 論文ID投入
    PP->>SS: 論文情報取得要求
    SS-->>PP: メタデータ返却

    Note over PP: メタデータ解析
    PP->>DB: 論文メタデータ保存

    PP->>Gen: Markdown生成要求
    Gen->>DB: 論文情報取得
    Gen->>OV: Obsidian形式で保存

    loop 再帰的処理
        PP->>SS: 引用・被引用論文取得
        SS-->>PP: 関連論文リスト
        PP->>DB: 関連論文をキューに追加
        Note over PP: 重み付けによる優先度判定
    end
```

## PDF要約フロー

独立したサイクルで動作するPDF要約処理フローです。

```mermaid
sequenceDiagram
    participant User as User
    participant PS as PDFSummarizer
    participant DB as PostgreSQL
    participant LLM as LLM
    participant OV as ObsidianVault

    User->>PS: PDF要約リクエスト
    PS->>DB: 論文情報取得
    DB-->>PS: 論文メタデータ

    Note over PS: PDF URL確認
    PS->>PS: PDFダウンロード
    PS->>PS: テキスト抽出

    PS->>LLM: 要約生成要求
    LLM-->>PS: 要約結果返却

    PS->>DB: 要約・キーワード保存
    PS->>OV: Markdownファイル更新
```

## エラー処理フロー

API制限やネットワークエラーに対する処理フローです。

```mermaid
sequenceDiagram
    participant PP as PaperProcessor
    participant SS as SemanticScholar
    participant DB as PostgreSQL

    PP->>SS: API要求
    alt 正常応答
        SS-->>PP: データ返却
        PP->>DB: 処理成功を記録
    else レート制限 (429)
        SS-->>PP: 429 Too Many Requests
        PP->>PP: バックオフ待機
        PP->>DB: リトライ状態を保存
        PP->>SS: リトライ
    else 論文未発見 (404)
        SS-->>PP: 404 Not Found
        PP->>DB: 論文未発見を記録
    else サーバーエラー (5xx)
        SS-->>PP: 5xx Server Error
        PP->>DB: エラー状態を保存
        PP->>DB: 処理キューに再登録
    end
```

## 処理優先度管理フロー

引用数による重み付けと処理優先度の管理フローです。

```mermaid
sequenceDiagram
    participant PP as PaperProcessor
    participant DB as PostgreSQL
    participant Queue as ProcessingQueue

    PP->>DB: 新規論文発見
    PP->>PP: 重み付けスコア計算
    Note over PP: citation_count * 係数

    PP->>Queue: キューに追加（優先度付き）

    loop キュー処理
        Queue->>PP: 最高優先度の論文取得
        PP->>PP: 論文処理実行
        PP->>Queue: 処理完了を通知
    end
```
