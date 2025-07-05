# Task: Monorepo（moonrepo）のセットアップ

## タスクの目的

moonrepoを使用してモノレポ環境を構築し、複数パッケージの統合的な開発・テスト・ビルド環境を整備する。

## 実施内容

### 1. moonrepoのインストール

```bash
# プロジェクトルートで実行
curl -fsSL https://moonrepo.dev/install/moon.sh | bash

# または npm経由
npm install -g @moonrepo/cli
```

### 2. moon workspace の初期化

```bash
# プロジェクトルートで実行
moon init

# 以下のプロンプトに回答
# - Workspace name: ref-net
# - Version control: git
# - Package manager: other (uvを使用)
```

### 3. .moon/workspace.yml の設定

```yaml
# Workspace configuration
$schema: "https://moonrepo.dev/schemas/workspace.json"
version: "1"

# プロジェクト設定
projects:
  - "package/*"

# タスクランナー設定
runner:
  # キャッシュ設定
  cacheLifetime: "7 days"

  # 並列実行数
  inheritColorsForPipedTasks: true
  logRunningTasks: true

# VCS設定
vcs:
  provider: "git"
  defaultBranch: "main"
```

### 4. .moon/toolchain.yml の設定

```yaml
# Toolchain configuration
$schema: "https://moonrepo.dev/schemas/toolchain.json"
version: "1"

# Python設定
python:
  version: "3.12"

  # 仮想環境の設定
  venvTool: "uv"

  # 依存関係管理
  dependencyFile: "pyproject.toml"
```

### 5. 共通タスクテンプレートの作成

`.moon/tasks.yml` を作成：

```yaml
# 全プロジェクト共通のタスク定義
$schema: "https://moonrepo.dev/schemas/tasks.json"

# 共通タスク
tasks:
  # 依存関係のインストール
  install:
    command: "uv pip sync requirements.txt"
    inputs:
      - "pyproject.toml"
      - "requirements.txt"

  # 依存関係の更新
  update-deps:
    command: "uv pip compile pyproject.toml -o requirements.txt"
    inputs:
      - "pyproject.toml"
    outputs:
      - "requirements.txt"

  # 開発環境のセットアップ
  dev-setup:
    deps:
      - install
    command: "uv pip install -e ."

  # クリーンアップ
  clean:
    command: "rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov"
```

### 6. プロジェクト検出の設定

`.moon/projects.yml` を作成（オプション）：

```yaml
# プロジェクト自動検出の設定
shared:
  path: "package/shared"
  tags: ["library", "core"]

api:
  path: "package/api"
  tags: ["service", "api"]

crawler:
  path: "package/crawler"
  tags: ["service", "worker"]

summarizer:
  path: "package/summarizer"
  tags: ["service", "worker"]

generator:
  path: "package/generator"
  tags: ["service", "worker"]
```

### 7. CI統合用スクリプトの作成

`scripts/moon-check.sh` を作成：

```bash
#!/bin/bash
set -e

echo "Running moon checks..."

# 依存関係のインストール
moon run :install

# 全プロジェクトのチェック実行
moon check --all

# カバレッジレポートの統合
moon run :coverage-report
```

## スコープ

- moonrepoのインストールと初期設定
- ワークスペース設定ファイルの作成
- 共通タスクテンプレートの定義
- Python環境との統合設定

**スコープ外:**
- 各パッケージ固有のタスク定義
- CI/CDパイプラインの設定
- デプロイメント設定

## 参照するドキュメント

- `/docs/development/coding-standards.md`
- `/CLAUDE.md`
- [moonrepo公式ドキュメント](https://moonrepo.dev/docs)

## 完了条件

- [ ] moonrepoがインストールされている
- [ ] `.moon/workspace.yml` が作成されている
- [ ] `.moon/toolchain.yml` が作成されている
- [ ] `.moon/tasks.yml` が作成されている
- [ ] `moon list` でプロジェクト一覧が表示される
- [ ] `moon run :install` が実行できる

## レビュー観点

### インストールと設定
- [ ] moonrepoのインストール手順が正確で再現可能か
- [ ] 必要なシステム要件が満たされているか
- [ ] 代替インストール方法（npm）の選択基準が明確か
- [ ] インストール後の動作確認手順が適切か

### 設定ファイルの妥当性
- [ ] workspace.ymlの設定が適切で必要な機能を網羅しているか
- [ ] toolchain.ymlのPython設定がプロジェクト要件に合致しているか
- [ ] tasks.ymlの共通タスクが効率的で再利用可能か
- [ ] JSONスキーマ参照が正しく設定されているか

### プロジェクト統合
- [ ] プロジェクト検出の設定が漏れなく対象を捕捉しているか
- [ ] タグ付けが論理的で検索・フィルタに有効か
- [ ] 依存関係の解決順序が適切に設定されているか
- [ ] パッケージ間の分離と統合のバランスが取れているか

### 開発効率性
- [ ] キャッシュ設定が適切で開発速度を向上させるか
- [ ] 並列実行の設定が最適化されているか
- [ ] タスクの依存関係が論理的で無駄がないか
- [ ] CI統合スクリプトが実用的で保守しやすいか

### 技術的整合性
- [ ] uvとmoonrepoの統合が適切に設定されているか
- [ ] Pythonツールチェーンの設定が一貫しているか
- [ ] VCS設定がプロジェクトのGitフローに適合しているか
- [ ] 他の開発ツールとの競合や重複がないか
