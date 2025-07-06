# RefNet パッケージ

## 構成

- `shared/` - 共通ライブラリ（モデル、設定、ユーティリティ）
- `api/` - FastAPI APIゲートウェイサービス
- `crawler/` - Semantic Scholar APIクローラーサービス
- `summarizer/` - PDF処理・LLM要約サービス
- `generator/` - Obsidian Markdown生成サービス

## 開発フロー

1. `shared` パッケージから開発開始
2. 各サービスは `shared` に依存
3. サービス間の直接依存は禁止
