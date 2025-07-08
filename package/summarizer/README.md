# RefNet Summarizer

PDF論文の要約とキーワード抽出を行うサービス。Claude Code、OpenAI、Anthropic APIに対応。

## 特徴

- **マルチAI対応**: Claude Code (推奨)、OpenAI、Anthropic
- **PDF処理**: PyPDF2/pdfplumberによるテキスト抽出
- **非同期処理**: Celeryによるバックグラウンド処理
- **フォールバック**: 複数手法での障害対応

## セットアップ

### 1. Claude Code（推奨）

```bash
# Claude Code CLIをインストール
npm install -g @anthropic-ai/claude-code

# 動作確認
claude --version
```

### 2. 環境変数

```bash
# プロバイダー選択
export AI_PROVIDER=claude-code  # または openai, anthropic, auto

# APIキー（Claude Code以外を使用する場合）
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
```

### 3. 依存関係とテスト

```bash
uv sync
moon run summarizer:check
```

## 使用方法

### CLI

```bash
# 論文要約
refnet-summarizer summarize paper-123

# Celeryワーカー起動
moon run summarizer:worker
```

### プログラム

```python
from refnet_summarizer.services.summarizer_service import SummarizerService

service = SummarizerService()
result = await service.summarize_paper("paper-123")
```

## 対応AI

| プロバイダー | モデル | 特徴 |
|------------|--------|------|
| Claude Code | claude-3.5-sonnet | ローカル実行、セキュア |
| OpenAI | gpt-4o-mini | 高速・低コスト |
| Anthropic | claude-3-5-haiku | 高品質・大容量 |

自動選択: Claude Code → OpenAI → Anthropic

## 開発

```bash
# テスト実行
moon run summarizer:test

# 品質チェック
moon run summarizer:check

# フォーマット
moon run summarizer:format
```

## アーキテクチャ

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PDF Processor │    │   AI Client     │    │  Summarizer     │
│                 │    │                 │    │  Service        │
│ • Download      │───▶│ • Claude Code   │───▶│                 │
│ • Extract Text  │    │ • OpenAI        │    │ • Orchestration │
│ • Clean         │    │ • Anthropic     │    │ • DB Updates    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Celery Tasks  │    │   Error Handler │    │   Database      │
│                 │    │                 │    │                 │
│ • Async Jobs    │    │ • Retry Logic   │    │ • Papers        │
│ • Batch Process │    │ • Fallback      │    │ • Queue Status  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```
