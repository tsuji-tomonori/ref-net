# 並列開発戦略

## 概要

論文関係性可視化システムを効率的に開発するため、git worktreeを活用した並列開発戦略を採用する。本文書では、タスクの分解、前提条件、並列作業方法を定義する。

## git worktree による並列開発手法

### 1. 基本構成

```bash
# メインリポジトリ（Phase 1-2基盤開発用）
/home/t-tsuji/project/ref-net/

# 各コンポーネント開発用worktree
/home/t-tsuji/project/ref-net-worktrees/
├── api/         # APIゲートウェイ開発
├── crawler/     # クローラーサービス開発
├── summarizer/  # 要約サービス開発
├── generator/   # Markdownジェネレーター開発
└── infra/       # インフラ・運用機能開発
```

### 2. worktree作成手順

```bash
# worktree用ディレクトリの作成
mkdir -p ~/project/ref-net-worktrees

# Phase 3: 各サービス用のworktree作成
cd ~/project/ref-net
git worktree add ../ref-net-worktrees/api claude/api-$(date +'%Y%m%d%H%M%S')
git worktree add ../ref-net-worktrees/crawler claude/crawler-$(date +'%Y%m%d%H%M%S')
git worktree add ../ref-net-worktrees/summarizer claude/summarizer-$(date +'%Y%m%d%H%M%S')
git worktree add ../ref-net-worktrees/generator claude/generator-$(date +'%Y%m%d%H%M%S')

# Phase 4: インフラ用worktree作成
git worktree add ../ref-net-worktrees/infra claude/infra-$(date +'%Y%m%d%H%M%S')
```

### 3. 開発フロー

1. **Phase 1-2: 基盤開発（メインブランチで実施）**
   - プロジェクト全体のディレクトリ構造作成
   - Monorepoツール（moonrepo）の設定
   - 共通の開発環境設定
   - データベースモデル定義
   - マイグレーション設定

2. **Phase 3: 並列コンポーネント開発（各worktreeで実施）**
   - 各サービスの独立実装
   - 単体テストの作成
   - ローカル動作確認

3. **Phase 4: インフラ・運用（一部並列で実施）**
   - Docker統合環境
   - 監視・アラート機能
   - セキュリティ・認証機能

4. **統合（メインブランチで実施）**
   - 各worktreeからのPRマージ
   - 統合テスト
   - Docker Compose環境での動作確認

## 競合回避のガイドライン

### 1. ファイル競合の回避

- 各worktreeは自身のpackageディレクトリ内でのみ作業
- 共通ファイル（pyproject.toml等）の編集は最小限に
- 新規ファイル作成を優先し、既存ファイル編集は避ける

### 2. 依存関係の管理

- sharedパッケージのインターフェースは事前に確定
- 各サービス間の直接依存は禁止
- 通信はAPI経由またはメッセージキュー経由

### 3. 設定ファイルの扱い

- 環境変数による設定を優先
- 各サービス固有の設定は独自ファイルに分離
- 共通設定の変更は基盤フェーズで実施

## チーム開発の役割分担例

### 開発者1: テックリード・基盤担当
```bash
# Phase 1-2実行（メインブランチ）
cd ~/project/ref-net
# Phase 1: プロジェクト基盤構築
# Phase 2: データ基盤構築

# Phase 3実行（APIブランチ）
cd ~/project/ref-net-worktrees/api
# APIサービス実装
```

### 開発者2: バックエンド担当
```bash
# Phase 2完了を待つ
cd ~/project/ref-net-worktrees/crawler
# クローラーサービス実装
```

### 開発者3: AI・データ処理担当
```bash
# Phase 2完了を待つ
cd ~/project/ref-net-worktrees/summarizer
# 要約サービス実装
```

### 開発者4: フロントエンド・生成担当
```bash
# Phase 2完了を待つ
cd ~/project/ref-net-worktrees/generator
# Markdownジェネレーター実装
```

### インフラ担当（Phase 4）
```bash
# Phase 3基本機能完了後
cd ~/project/ref-net-worktrees/infra
# Docker・監視・セキュリティ実装
```

## マージ戦略

### 1. PRの作成タイミング

- 各コンポーネントの基本機能完成時
- 単体テスト合格後
- moon :check が正常終了後

### 2. マージ順序

1. Phase 1-2: 基盤のPR
2. Phase 3: 各サービスのPR（順不同）
3. Phase 4: インフラ・運用のPR
4. 統合設定のPR

### 3. コンフリクト解消

- 基本的にコンフリクトは発生しない設計
- 発生時はfeature branchでrebase実施
- 必要に応じてペアプログラミングで解決

## 成功基準

- 全worktreeで `moon :check` が正常終了
- 各サービスの単体テストカバレッジ80%以上
- Docker Composeで全サービス起動成功
- 基本的な論文取得・要約・Markdown生成フロー動作確認
- 本番環境での安定稼働

## トラブルシューティング

### よくある問題

1. **パッケージ依存関係エラー**
   - 解決策: `uv sync`を実行してパッケージを同期

2. **テスト失敗**
   - 解決策: 依存関係を確認し、sharedパッケージが最新か確認

3. **Docker起動失敗**
   - 解決策: `.env`ファイルの設定を確認

4. **worktreeでのコンフリクト**
   - 解決策: メインブランチからrebaseを実行

### ヘルプリソース

- 各フェーズディレクトリ内のREADME.md
- プロジェクトの`CLAUDE.md`
- 開発規約: `docs/development/`配下
