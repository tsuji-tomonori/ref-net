# AI API統合仕様

## 概要

RefNet Summarizerサービスは、OpenAIとAnthropicのAI APIを使用して論文の要約とキーワード抽出を行います。環境設定に基づいて適切なAIプロバイダーを選択し、フォールバック機構により高可用性を実現します。

## 対応AIプロバイダー

### Claude Code (推奨)
- **モデル**: ローカルCLI経由でClaude
- **用途**: 直接統合・セキュアな処理
- **特徴**: APIキー不要、プロジェクト連携
- **必要**: `npm install -g @anthropic-ai/claude-code`

### OpenAI
- **モデル**: gpt-4o-mini
- **用途**: 高速・低コストな要約生成
- **レート制限**: 60 RPM（リクエスト/分）
- **トークン制限**: 入力8000トークン、出力500トークン

### Anthropic
- **モデル**: claude-3-5-haiku-20241022
- **用途**: 高品質・大容量テキスト処理
- **レート制限**: 50 RPM
- **トークン制限**: 入力100000トークン、出力500トークン

## プロンプト設計

### 要約生成プロンプト

```
システムプロンプト:
あなたは論文要約の専門家です。以下の論文テキストを読んで、研究内容、手法、結果、意義を含む簡潔で有用な要約を作成してください。要約は日本語で記述し、専門用語は適切に説明してください。

ユーザープロンプト:
以下の論文テキストを要約してください（最大{max_tokens}トークン）:
{論文テキスト}
```

### キーワード抽出プロンプト

```
システムプロンプト:
以下の論文テキストから重要なキーワードを{max_keywords}個抽出してください。技術用語、手法名、概念名を優先し、カンマ区切りで返してください。

ユーザープロンプト:
{論文テキスト}
```

## エラーハンドリング

### リトライ戦略

1. **指数バックオフ**: 初回4秒、最大10秒まで増加
2. **最大試行回数**: 3回
3. **レート制限対応**: 429エラー時は60秒待機

### フォールバック機構

1. OpenAI → Anthropic の順で試行
2. 両方失敗時はエラーをキューに戻す

## 環境設定

### 必須環境変数

```bash
# プロバイダー選択（省略時は自動）
AI_PROVIDER=claude-code  # または openai, anthropic, auto

# OpenAI設定（オプション）
OPENAI_API_KEY=sk-...

# Anthropic設定（オプション）
ANTHROPIC_API_KEY=sk-ant-...
```

### Claude Code セットアップ

```bash
# Claude Code CLIのインストール
npm install -g @anthropic-ai/claude-code

# Claude Codeの初期設定（必要な場合）
claude

# 動作確認
claude --version
```

### Claude認証情報の設定

Dockerコンテナ内でClaude Codeを使用するため、ホストマシンの認証情報をマウントする必要があります。

```bash
# ホストマシンでClaude認証情報を設定
claude  # 初回実行時に認証

# 認証情報ファイルの確認
ls ~/.claude/.credentials.json
```

Docker Composeでは以下の設定により認証情報をマウントします：

```yaml
summarizer-worker:
  volumes:
    - ~/.claude/.credentials.json:/root/.claude/.credentials.json:ro
  environment:
    AI_PROVIDER: claude-code
```

**重要事項**:
- 認証情報ファイルは読み取り専用（`:ro`）でマウント
- コンテナ内のパス: `/root/.claude/.credentials.json`
- `AI_PROVIDER=claude-code`を設定してClaude Codeを優先使用

### 設定ファイル

```yaml
# config/ai.yaml
ai:
  default_provider: openai
  providers:
    openai:
      enabled: true
      model: gpt-4o-mini
      max_input_tokens: 8000
      max_output_tokens: 500
      temperature: 0.3
      rate_limit: 60
    anthropic:
      enabled: true
      model: claude-3-5-haiku-20241022
      max_input_tokens: 100000
      max_output_tokens: 500
      temperature: 0.3
      rate_limit: 50
```

## セキュリティ考慮事項

1. **APIキー管理**: 環境変数または Secrets Manager使用
2. **入力検証**: テキストサイズ制限とサニタイゼーション
3. **出力検証**: AI生成コンテンツの基本的な検証
4. **ログ**: APIキーや個人情報を含まない

## パフォーマンス最適化

### バッチ処理

- 複数論文の並列処理（最大10並列）
- プロバイダー別のレート制限管理
- キュー優先度による処理順序制御

### キャッシング

- 同一論文の再処理防止
- ハッシュベースの重複検出
- TTL: 7日間

## モニタリング

### メトリクス

- API呼び出し成功率
- 平均応答時間
- トークン使用量
- エラー率（プロバイダー別）

### ログ出力

```python
logger.info("Summary generated successfully",
    model="gpt-4o-mini",
    paper_id="1234567890",
    input_tokens=3500,
    output_tokens=450,
    duration_ms=2300
)
```

## トラブルシューティング

### よくある問題

1. **APIキーエラー**
   - 環境変数の確認
   - APIキーの有効性確認

2. **レート制限エラー**
   - リトライ間隔の調整
   - 並列数の削減

3. **タイムアウトエラー**
   - タイムアウト値の増加
   - テキストサイズの削減

## 今後の拡張

1. **追加プロバイダー対応**
   - Google Gemini
   - Local LLM（Ollama等）

2. **高度な要約機能**
   - 多段階要約
   - 比較要約
   - 図表説明の生成

3. **品質評価**
   - 要約品質スコアリング
   - 人間によるフィードバック統合
