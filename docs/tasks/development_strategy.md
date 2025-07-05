# RefNet 並列開発戦略

## 概要

RefNet論文関係性可視化システムを効率的に開発するため、git worktreeを活用した並列開発戦略を採用する。本文書では、4フェーズに分割したタスク実行戦略、前提条件、並列作業方法を定義する。

**注意**: 詳細なタスク実装手順については、各フェーズディレクトリ（phase_01/, phase_02/, phase_03/, phase_04/）内のタスクファイルを参照すること。

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

1. **Phase 1: プロジェクト基盤構築（メインブランチで実施）**
   - プロジェクト全体のディレクトリ構造作成
   - Monorepoツール（moonrepo）の設定
   - 共通ライブラリの基盤設定
   - 環境設定管理システム

2. **Phase 2: データ基盤構築（メインブランチで実施）**
   - SQLAlchemyモデル定義
   - データベースマイグレーション設定
   - 共通データアクセス層

3. **Phase 3: コアサービス開発（各worktreeで並列実施）**
   - APIゲートウェイサービス
   - クローラーサービス
   - 要約サービス
   - Markdownジェネレーター

4. **Phase 4: インフラ・運用（一部並列で実施）**
   - Docker統合環境
   - 監視・アラート機能
   - セキュリティ・認証機能
   - バッチ処理・スケジューリング

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

## レビュー観点

### 戦略全体の妥当性
- [ ] 4フェーズの分割が論理的で、依存関係が明確に定義されているか
- [ ] monorepo構成の利点が適切に活用されているか
- [ ] 並列開発戦略がプロジェクトの規模と複雑さに適しているか
- [ ] 各フェーズの成果物が次フェーズの前提条件を満たしているか

### 技術選択の適切性
- [ ] moonrepo + uvの組み合わせが効率的な開発環境を提供するか
- [ ] Python 3.12の要件が全コンポーネントで一貫しているか
- [ ] FastAPI + Celery + PostgreSQLの技術スタックが要件に適合するか
- [ ] Dockerを用いたコンテナ化戦略が本番運用に適しているか

### 実装計画の具体性
- [ ] 各タスクの作業範囲が明確で重複がないか
- [ ] 実装手順が再現可能で、チームメンバーが理解しやすいか
- [ ] テスト戦略（単体・統合・E2E）が包括的か
- [ ] 品質保証の仕組み（linting、型チェック、カバレッジ）が十分か

### リソースと作業計画
- [ ] 並列作業による効率化が実現可能か
- [ ] ボトルネックとなる作業が特定され、対策が講じられているか
- [ ] チームのスキルレベルと作業内容が適切にマッチしているか

### リスク管理
- [ ] 技術的リスクが特定され、軽減策が計画されているか
- [ ] 外部依存（Semantic Scholar API等）の障害対応が考慮されているか
- [ ] データ損失やセキュリティ問題への対策が適切か
- [ ] 進捗遅延時のリカバリプランが明確か

### 運用・保守性
- [ ] 本番環境での監視・ログ収集体制が計画されているか
- [ ] バックアップとディザスタリカバリの方針が明確か
- [ ] 新機能追加やスケールアウトの拡張性が考慮されているか
- [ ] ドキュメント管理と知識共有の仕組みが整備されているか
