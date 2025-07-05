# 並列開発戦略

## 概要

論文関係性可視化システムを効率的に開発するため、git worktreeを活用した並列開発戦略を採用する。本文書では、タスクの分解、前提条件、並列作業方法を定義する。

## git worktree による並列開発手法

### 1. 基本構成

```bash
# メインリポジトリ（共通基盤開発用）
/home/t-tsuji/project/ref-net/

# 各コンポーネント開発用worktree
/home/t-tsuji/project/ref-net-worktrees/
├── shared/      # 共通ライブラリ開発
├── api/         # APIゲートウェイ開発
├── crawler/     # クローラーサービス開発
├── summarizer/  # 要約サービス開発
└── generator/   # Markdownジェネレーター開発
```

### 2. worktree作成手順

```bash
# worktree用ディレクトリの作成
mkdir -p ~/project/ref-net-worktrees

# 各コンポーネント用のworktree作成
cd ~/project/ref-net
git worktree add ../ref-net-worktrees/shared claude/shared-$(date +'%Y%m%d%H%M%S')
git worktree add ../ref-net-worktrees/api claude/api-$(date +'%Y%m%d%H%M%S')
git worktree add ../ref-net-worktrees/crawler claude/crawler-$(date +'%Y%m%d%H%M%S')
git worktree add ../ref-net-worktrees/summarizer claude/summarizer-$(date +'%Y%m%d%H%M%S')
git worktree add ../ref-net-worktrees/generator claude/generator-$(date +'%Y%m%d%H%M%S')
```

### 3. 開発フロー

1. **Phase 0: 前提タスク（メインブランチで実施）**
   - プロジェクト全体のディレクトリ構造作成
   - Monorepoツール（moonrepo）の設定
   - 共通の開発環境設定

2. **Phase 1: 基盤開発（shared worktreeで実施）**
   - データベースモデル定義
   - 共通ユーティリティ
   - 設定管理モジュール

3. **Phase 2: 並列コンポーネント開発（各worktreeで実施）**
   - 各サービスの独立実装
   - 単体テストの作成
   - ローカル動作確認

4. **Phase 3: 統合（メインブランチで実施）**
   - 各worktreeからのPRマージ
   - 統合テスト
   - Docker Compose環境での動作確認

## タスク分類

### 前提タスク（Phase 0）

順次実行が必要なタスク：

1. **00_project_structure** - プロジェクト全体構造の作成
2. **01_monorepo_setup** - Moonrepoの設定
3. **02_shared_foundation** - 共通基盤の初期設定

### 並列可能タスク（Phase 1-2）

競合が発生しないよう、以下の原則で分離：

1. **ディレクトリ分離**: 各コンポーネントは独自のpackage配下で開発
2. **依存関係の明確化**: sharedパッケージへの依存は読み取り専用
3. **インターフェース定義**: 事前にAPI仕様・データモデルを確定

### 並列タスクリスト

#### 基盤系（shared worktree）
- **10_database_models** - SQLAlchemyモデル定義
- **11_config_management** - 設定管理システム
- **12_common_utilities** - 共通ユーティリティ

#### サービス系（各worktree）
- **20_api_service** - APIゲートウェイ実装
- **21_crawler_service** - クローラーサービス実装
- **22_summarizer_service** - 要約サービス実装
- **23_generator_service** - Markdownジェネレーター実装

#### インフラ系（独立worktree可能）
- **30_docker_setup** - Docker環境構築
- **31_database_init** - PostgreSQL初期化
- **32_redis_setup** - Redis設定

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
- 共通設定の変更は前提タスクで実施

## マージ戦略

### 1. PRの作成タイミング

- 各コンポーネントの基本機能完成時
- 単体テスト合格後
- moon :check が正常終了後

### 2. マージ順序

1. shared基盤のPR
2. 独立サービスのPR（順不同）
3. 統合設定のPR

### 3. コンフリクト解消

- 基本的にコンフリクトは発生しない設計
- 発生時はfeature branchでrebase実施
- 必要に応じてペアプログラミングで解決

## 成功基準

- 全worktreeで `moon :check` が正常終了
- 各サービスの単体テストカバレッジ80%以上
- Docker Composeで全サービス起動成功
- 基本的な論文取得・要約・Markdown生成フロー動作確認

## レビュー観点

### 戦略の妥当性
- [ ] 並列開発による効率化が実現できる設計になっているか
- [ ] git worktreeの使用方法が適切で、チーム開発に適用可能か
- [ ] フェーズ分割が論理的で、依存関係が明確に定義されているか
- [ ] 各コンポーネントの独立性が保たれているか

### 技術的実現性
- [ ] 提案されたディレクトリ構造が実装可能か
- [ ] moonrepoとgit worktreeの組み合わせが技術的に妥当か
- [ ] 並列作業時の競合回避策が十分か
- [ ] マージ戦略がプロジェクトの規模に適しているか

### プロセスの明確性
- [ ] 各フェーズの作業内容が明確に定義されているか
- [ ] 開発フローがチームメンバーに理解しやすいか
- [ ] コンフリクト解消手順が具体的で実行可能か
- [ ] 成功基準が測定可能で明確か

### 保守性・拡張性
- [ ] 新しいコンポーネント追加時の手順が明確か
- [ ] 開発チームの拡大に対応できる構造か
- [ ] CI/CDパイプラインとの整合性が考慮されているか
- [ ] ドキュメント管理とバージョン管理が適切か
