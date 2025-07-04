# PDF Summarizer フローチャート

## 概要

PDF Summarizerは、論文のPDFをダウンロードしてLLM APIを使用して要約を生成するサービスです。Paper Processorとは独立して動作します。

## フローチャート

```mermaid
flowchart TD
    Start([開始]) --> InputID[論文ID入力]
    InputID --> CheckDBExists{DBに論文存在?}
    
    CheckDBExists -->|No| ErrorNoData[エラー: 論文データなし]
    CheckDBExists -->|Yes| CheckSummary{要約済み?}
    
    ErrorNoData --> End([終了])
    CheckSummary -->|Yes| End
    CheckSummary -->|No| GetPDFUrl[DBからPDF URL取得]
    
    GetPDFUrl --> CheckURL{PDF URLあり?}
    CheckURL -->|No| SearchOpenAccess[OpenAccessPDF検索]
    CheckURL -->|Yes| DownloadPDF[PDFダウンロード]
    
    SearchOpenAccess --> FoundURL{URL発見?}
    FoundURL -->|No| ErrorNoPDF[エラー: PDF未発見]
    FoundURL -->|Yes| DownloadPDF
    
    ErrorNoPDF --> End
    
    DownloadPDF --> CheckDownload{ダウンロード成功?}
    CheckDownload -->|No| RetryDownload{リトライ?}
    CheckDownload -->|Yes| ExtractText[テキスト抽出<br/>PyPDF2/pdfplumber]
    
    RetryDownload -->|Yes<br/>< 3回| DownloadPDF
    RetryDownload -->|No<br/>>= 3回| ErrorDownload[エラー: ダウンロード失敗]
    ErrorDownload --> End
    
    ExtractText --> CheckText{テキスト抽出成功?}
    CheckText -->|No| ErrorExtract[エラー: 抽出失敗]
    CheckText -->|Yes| PreparePrompt[プロンプト準備]
    
    ErrorExtract --> End
    
    PreparePrompt --> CallLLM[LLM API呼び出し<br/>OpenAI/Claude]
    
    CallLLM --> CheckLLM{API成功?}
    CheckLLM -->|No| RetryLLM{リトライ?}
    CheckLLM -->|Yes| ParseResult[結果解析<br/>- 要約<br/>- キーワード]
    
    RetryLLM -->|Yes<br/>< 3回| CallLLM
    RetryLLM -->|No<br/>>= 3回| ErrorLLM[エラー: LLM失敗]
    ErrorLLM --> End
    
    ParseResult --> SaveDB[PostgreSQL更新<br/>summary, keywords]
    SaveDB --> UpdateMD[Markdownファイル更新<br/>/output/{paper_id}.md]
    UpdateMD --> End
    
    style Start fill:#90EE90
    style End fill:#FFB6C1
    style CallLLM fill:#87CEEB
    style SaveDB fill:#DDA0DD
    style UpdateMD fill:#F0E68C
```

## LLM処理詳細

```mermaid
flowchart TD
    Text[論文テキスト] --> Chunk[チャンク分割<br/>トークン制限対応]
    
    Chunk --> Prompt[プロンプト構築]
    
    Prompt --> Abstract[Abstract優先]
    Prompt --> Introduction[Introduction追加]
    Prompt --> Conclusion[Conclusion追加]
    
    Abstract --> LLMCall[LLM API呼び出し]
    Introduction --> LLMCall
    Conclusion --> LLMCall
    
    LLMCall --> Response[レスポンス]
    
    Response --> Summary[要約テキスト<br/>200-300単語]
    Response --> Keywords[キーワード抽出<br/>5-10個]
    Response --> MainFindings[主要な発見<br/>箇条書き]
```

## エラーハンドリング戦略

```mermaid
flowchart LR
    Error[エラー発生] --> Type{エラー種別}
    
    Type -->|Network| NetworkRetry[ネットワークリトライ<br/>指数バックオフ]
    Type -->|PDF Parse| FallbackParser[代替パーサー使用<br/>pdfplumber → PyPDF2]
    Type -->|LLM Rate| RateWait[レート制限待機<br/>60秒]
    Type -->|LLM Error| SimplifyPrompt[プロンプト簡略化<br/>再試行]
    
    NetworkRetry --> Continue[処理継続]
    FallbackParser --> Continue
    RateWait --> Continue
    SimplifyPrompt --> Continue
```

## ファイル更新フロー

```mermaid
flowchart TD
    Original[既存Markdownファイル] --> Read[ファイル読み込み]
    Read --> Parse[内容解析]
    
    Parse --> Update[要約セクション更新]
    Update --> AddKeywords[キーワード追加]
    AddKeywords --> AddFindings[主要発見追加]
    
    AddFindings --> Write[ファイル書き込み]
    Write --> Updated[更新済みMarkdownファイル]
    
    style Original fill:#E6E6FA
    style Updated fill:#98FB98
```