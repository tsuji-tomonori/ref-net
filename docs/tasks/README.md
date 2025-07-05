# RefNet 並列開発タスク一覧

## 概要

このディレクトリには、RefNet論文関係性可視化システムを効率的に並列開発するためのタスク定義が含まれています。

## タスク実行順序

### Phase 0: 前提タスク（順次実行）

これらのタスクは並列開発を開始する前に完了する必要があります。

| タスク | ファイル | 説明 | 実行時間 |
|--------|----------|------|----------|
| プロジェクト構造作成 | [00_project_structure.md](00_project_structure.md) | 全体のディレクトリ構造とパッケージ初期化 | 30分 |
| Monorepo設定 | [01_monorepo_setup.md](01_monorepo_setup.md) | moonrepoによるモノレポ環境構築 | 45分 |
| 共通基盤設定 | [02_shared_foundation.md](02_shared_foundation.md) | 共通ライブラリの基本設定 | 60分 |

**合計**: 約2時間15分

### Phase 1: 基盤開発（shared worktreeで実施）

| タスク | ファイル | 説明 | 実行時間 |
|--------|----------|------|----------|
| データベースモデル定義 | [10_database_models.md](10_database_models.md) | SQLAlchemyモデル・Pydanticスキーマ定義 | 3時間 |

### Phase 2: 並列コンポーネント開発

これらのタスクは独立したworktreeで並列実行可能です。

| タスク | ファイル | 説明 | 実行時間 | 依存関係 |
|--------|----------|------|----------|----------|
| APIサービス | [20_api_service.md](20_api_service.md) | FastAPI APIゲートウェイ実装 | 4時間 | Phase 1 |
| クローラーサービス | [21_crawler_service.md](21_crawler_service.md) | Semantic Scholar API統合 | 5時間 | Phase 1 |
| 要約サービス | [22_summarizer_service.md](22_summarizer_service.md) | PDF処理・LLM要約実装 | 4時間 | Phase 1 |
| ジェネレーター | [23_generator_service.md](23_generator_service.md) | Obsidian Markdown生成 | 3時間 | Phase 1 |
| Docker環境 | [30_docker_setup.md](30_docker_setup.md) | Docker Compose統合環境 | 2時間 | 独立 |

## git worktree セットアップ

### 1. worktree用ディレクトリの作成

```bash
mkdir -p ~/project/ref-net-worktrees
cd ~/project/ref-net
```

### 2. 各コンポーネント用worktreeの作成

```bash
# 共通基盤用
git worktree add ../ref-net-worktrees/shared claude/shared-$(date +'%Y%m%d%H%M%S')

# 各サービス用
git worktree add ../ref-net-worktrees/api claude/api-$(date +'%Y%m%d%H%M%S')
git worktree add ../ref-net-worktrees/crawler claude/crawler-$(date +'%Y%m%d%H%M%S')
git worktree add ../ref-net-worktrees/summarizer claude/summarizer-$(date +'%Y%m%d%H%M%S')
git worktree add ../ref-net-worktrees/generator claude/generator-$(date +'%Y%m%d%H%M%S')

# Docker環境用
git worktree add ../ref-net-worktrees/docker claude/docker-$(date +'%Y%m%d%H%M%S')
```

### 3. 作業ディレクトリの確認

```bash
git worktree list
```

## 推奨開発フロー

### 開発者1: 基盤・API担当

```bash
# Phase 0実行（メインブランチ）
cd ~/project/ref-net
# 00_project_structure.md の実行
# 01_monorepo_setup.md の実行
# 02_shared_foundation.md の実行
git add . && git commit -m "feat: プロジェクト基盤セットアップ"

# Phase 1実行（sharedブランチ）
cd ~/project/ref-net-worktrees/shared
# 10_database_models.md の実行
git add . && git commit -m "feat: データベースモデル定義"

# Phase 2実行（APIブランチ）
cd ~/project/ref-net-worktrees/api
# 20_api_service.md の実行
git add . && git commit -m "feat: APIサービス実装"
```

### 開発者2: クローラー担当

```bash
# Phase 1完了を待つ
cd ~/project/ref-net-worktrees/crawler
# 21_crawler_service.md の実行
git add . && git commit -m "feat: クローラーサービス実装"
```

### 開発者3: 要約・生成担当

```bash
# Phase 1完了を待つ
cd ~/project/ref-net-worktrees/summarizer
# 22_summarizer_service.md の実行
git add . && git commit -m "feat: 要約サービス実装"

cd ~/project/ref-net-worktrees/generator
# 23_generator_service.md の実行
git add . && git commit -m "feat: ジェネレーターサービス実装"
```

### 開発者4: インフラ担当

```bash
# Phase 0完了後すぐに開始可能
cd ~/project/ref-net-worktrees/docker
# 30_docker_setup.md の実行
git add . && git commit -m "feat: Docker統合環境構築"
```

## マージ戦略

### 1. sharedブランチの優先マージ

```bash
# sharedブランチを最初にマージ
cd ~/project/ref-net
git checkout main
git merge claude/shared-<timestamp>
```

### 2. 各サービスブランチのマージ

```bash
# 依存関係を考慮してマージ
git merge claude/api-<timestamp>
git merge claude/crawler-<timestamp>
git merge claude/summarizer-<timestamp>
git merge claude/generator-<timestamp>
git merge claude/docker-<timestamp>
```

### 3. 統合テスト

```bash
# 全体の動作確認
moon run :check
make dev-up
make test
```

## 完了チェックリスト

### Phase 0: 前提タスク
- [ ] プロジェクト構造が作成されている
- [ ] moonrepoが設定されている
- [ ] 共通基盤が設定されている
- [ ] `moon :check` が正常終了する

### Phase 1: 基盤開発
- [ ] データベースモデルが実装されている
- [ ] 単体テストが80%以上のカバレッジを達成している

### Phase 2: サービス開発
- [ ] 各サービスが実装されている
- [ ] 各サービスの単体テストが通る
- [ ] Docker環境が構築されている
- [ ] 統合テストが通る

### 最終確認
- [ ] 全サービスがDocker Composeで起動する
- [ ] APIエンドポイントが正常に動作する
- [ ] 論文取得→要約→Markdown生成のフロー動作確認
- [ ] Obsidianで論文ネットワークが可視化される

## 見積もり時間

| フェーズ | 作業内容 | 1人での作業時間 | 4人並列での作業時間 |
|----------|----------|----------------|-------------------|
| Phase 0 | 前提タスク | 2.25時間 | 2.25時間 |
| Phase 1 | 基盤開発 | 3時間 | 3時間 |
| Phase 2 | 並列開発 | 18時間 | 5時間（最大） |
| 統合・テスト | 統合作業 | 2時間 | 2時間 |
| **合計** | | **25.25時間** | **12.25時間** |

並列開発により、約**50%の時間短縮**が期待できます。

## 注意事項

1. **依存関係の順守**: Phase 1完了後にPhase 2を開始
2. **コミュニケーション**: 各worktreeでの作業状況を共有
3. **テスト実行**: 各段階で`moon :check`の実行を確認
4. **競合回避**: 同一ファイルの編集は避ける
5. **定期同期**: メインブランチからの定期的なrebase

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

- 各タスクファイル内の「参照するドキュメント」セクション
- プロジェクトの`CLAUDE.md`
- 開発規約: `docs/development/`配下

## 次のステップ

全タスク完了後：
1. 統合テストの実行
2. パフォーマンステスト
3. セキュリティ監査
4. ドキュメント更新
5. 本番デプロイメント準備
