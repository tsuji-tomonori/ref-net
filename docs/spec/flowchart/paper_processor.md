# Paper Processor フローチャート

## 概要

Paper Processorは、Semantic Scholar APIを使用して論文情報を取得し、引用・被引用関係を再帰的に収集するサービスです。

## フローチャート

```mermaid
flowchart TD
    Start([開始]) --> Input[論文ID入力]
    Input --> CheckDB{DBに存在?}
    
    CheckDB -->|Yes| CheckProcessed{処理済み?}
    CheckDB -->|No| FetchAPI[Semantic Scholar API呼び出し]
    
    CheckProcessed -->|Yes| End([終了])
    CheckProcessed -->|No| GenerateMD[Markdownファイル生成]
    
    FetchAPI --> CheckRateLimit{レート制限?}
    CheckRateLimit -->|Yes| Wait[待機<br/>バックオフ処理]
    CheckRateLimit -->|No| ParseData[論文データ解析]
    
    Wait --> FetchAPI
    
    ParseData --> SaveDB[PostgreSQLに保存]
    SaveDB --> GenerateMD
    
    GenerateMD --> OutputFile["Obsidianファイル出力<br/>/output/{paper_id}.md"]
    
    OutputFile --> GetRelations[引用・被引用関係取得]
    
    GetRelations --> CalcWeight[重み付け計算<br/>- ホップ数（距離）<br/>- 引用数<br/>- 発行年<br/>- 分野]
    
    CalcWeight --> AddQueue[処理キューに追加]
    
    AddQueue --> ProcessNext{次の論文あり?}
    ProcessNext -->|Yes| GetNext[キューから次を取得<br/>優先度順]
    ProcessNext -->|No| End
    
    GetNext --> CheckDB
    
    style Start fill:#90EE90
    style End fill:#FFB6C1
    style FetchAPI fill:#87CEEB
    style SaveDB fill:#DDA0DD
    style OutputFile fill:#F0E68C
    style Wait fill:#FFA07A
```

## エラーハンドリング

```mermaid
flowchart TD
    API[API呼び出し] --> Error{エラー?}
    
    Error -->|404| NotFound[論文未発見<br/>ログ記録]
    Error -->|429| RateLimit[レート制限<br/>リトライ]
    Error -->|500| ServerError[サーバエラー<br/>リトライ]
    Error -->|その他| OtherError[その他エラー<br/>失敗記録]
    
    NotFound --> UpdateStatus[ステータス更新<br/>failed]
    RateLimit --> Backoff[指数バックオフ<br/>待機]
    ServerError --> Retry{リトライ<br/>カウント?}
    OtherError --> UpdateStatus
    
    Backoff --> API
    Retry -->|< 3| API
    Retry -->|>= 3| UpdateStatus
```

## 処理ステータス管理

```mermaid
stateDiagram-v2
    [*] --> pending: 新規追加
    pending --> processing: 処理開始
    processing --> completed: 正常完了
    processing --> failed: エラー発生
    failed --> pending: リトライ
    completed --> [*]
    failed --> [*]: 最大リトライ超過
```

## 重み付けアルゴリズム

```mermaid
flowchart LR
    Paper[論文] --> Factors[評価要素]
    
    Factors --> Distance["距離（ホップ数）<br/>元論文からの距離<br/>1 / (hop + 1)"]
    Factors --> Citation["引用数<br/>log10(count + 1)"]
    Factors --> Year[発行年<br/>新しいほど高]
    Factors --> Field[分野一致<br/>起点と同じ分野]
    
    Distance --> Score[総合スコア<br/>距離による重み×その他要素]
    Citation --> Score
    Year --> Score
    Field --> Score
    
    Score --> Priority[優先度<br/>スコア降順]
```

### 距離（ホップ数）による優先度

- **ホップ数0（元論文）**: 重み = 1.0
- **ホップ数1（直接の引用・被引用）**: 重み = 0.5
- **ホップ数2（引用の引用）**: 重み = 0.33
- **ホップ数3以降**: 重み = 1 / (hop + 1)

この方式により、元論文に近い論文ほど高い優先度で処理され、離れるほど優先度が下がります。