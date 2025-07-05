# Task: Monorepo（moonrepo）のセットアップ

## タスクの目的

moonrepoを使用してモノレポ環境を構築し、複数パッケージの統合的な開発・テスト・ビルド環境を整備する。Phase 1の並列開発基盤として、統一されたタスク実行環境を提供する。

## 前提条件

- 00_project_structure.mdが完了している
- 各パッケージディレクトリが存在する
- 基本的なpyproject.tomlが配置済み

## 実施内容

### 1. moonrepoのインストール

```bash
# プロジェクトルートで実行
curl -fsSL https://moonrepo.dev/install/moon.sh | bash

# または npm経由（Node.js環境がある場合）
npm install -g @moonrepo/cli

# インストール確認
moon --version
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

  # 並列実行数（CPUコア数に基づく）
  inheritColorsForPipedTasks: true
  logRunningTasks: true

  # 出力設定
  archiveOutputs: false

# VCS設定
vcs:
  provider: "git"
  defaultBranch: "main"

# 通知設定
notifier:
  webhookUrl: ""  # 必要に応じて設定
```

### 4. .moon/toolchain.yml の設定

```yaml
# Toolchain configuration
$schema: "https://moonrepo.dev/schemas/toolchain.json"
version: "1"

# Python設定
python:
  version: "3.12"

  # 仮想環境の設定（uvを使用）
  packageManager: "pip"

  # 依存関係管理
  dependencyFile: "pyproject.toml"
  lockfileFile: "uv.lock"
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
    command: "uv sync"
    inputs:
      - "pyproject.toml"
      - "uv.lock"
    options:
      cache: true

  # 依存関係の更新
  update-deps:
    command: "uv lock --upgrade"
    inputs:
      - "pyproject.toml"
    outputs:
      - "uv.lock"

  # 開発環境のセットアップ
  dev-setup:
    deps:
      - install
    command: "uv pip install -e ."

  # クリーンアップ
  clean:
    command: "rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov dist *.egg-info"

  # セキュリティチェック
  security:
    command: "uv pip audit"
    inputs:
      - "pyproject.toml"
      - "uv.lock"
```

### 6. プロジェクト検出の設定

`.moon/projects.yml` を作成（オプション）：

```yaml
# プロジェクト自動検出の設定
shared:
  id: "shared"
  source: "package/shared"
  tags: ["library", "core"]
  language: "python"
  type: "library"

api:
  id: "api"
  source: "package/api"
  tags: ["service", "api"]
  language: "python"
  type: "application"
  dependsOn: ["shared"]

crawler:
  id: "crawler"
  source: "package/crawler"
  tags: ["service", "worker"]
  language: "python"
  type: "application"
  dependsOn: ["shared"]

summarizer:
  id: "summarizer"
  source: "package/summarizer"
  tags: ["service", "worker"]
  language: "python"
  type: "application"
  dependsOn: ["shared"]

generator:
  id: "generator"
  source: "package/generator"
  tags: ["service", "worker"]
  language: "python"
  type: "application"
  dependsOn: ["shared"]
```

### 7. 統合テスト用スクリプトの作成

`scripts/moon-check.sh` を作成：

```bash
#!/bin/bash
set -e

echo "Running moon quality checks..."

# 依存関係のインストール
echo "Installing dependencies..."
moon run :install

# 全プロジェクトのチェック実行
echo "Running checks for all projects..."
moon check --all

# カバレッジレポートの統合
echo "Generating coverage report..."
moon run :coverage-report || echo "Coverage report skipped (not implemented yet)"

echo "All checks completed successfully!"
```

### 8. 開発用便利スクリプトの作成

`scripts/dev.sh` を作成：

```bash
#!/bin/bash
set -e

COMMAND=${1:-help}

case $COMMAND in
    "install")
        echo "Installing all dependencies..."
        moon run :install
        ;;
    "check")
        echo "Running all checks..."
        moon run :check
        ;;
    "test")
        PROJECT=${2:-}
        if [ -z "$PROJECT" ]; then
            moon run :test
        else
            moon run $PROJECT:test
        fi
        ;;
    "lint")
        moon run :lint
        ;;
    "format")
        moon run :format
        ;;
    "clean")
        echo "Cleaning all projects..."
        moon run :clean
        ;;
    "help")
        echo "Usage: $0 {install|check|test|lint|format|clean|help}"
        echo ""
        echo "Commands:"
        echo "  install     Install all dependencies"
        echo "  check       Run all quality checks"
        echo "  test [proj] Run tests (all or specific project)"
        echo "  lint        Run linting"
        echo "  format      Format code"
        echo "  clean       Clean generated files"
        echo "  help        Show this help message"
        ;;
    *)
        echo "Unknown command: $COMMAND"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
```

### 9. 実行可能権限の設定

```bash
chmod +x scripts/moon-check.sh
chmod +x scripts/dev.sh
```

## スコープ

- moonrepoのインストールと初期設定
- ワークスペース設定ファイルの作成
- 共通タスクテンプレートの定義
- Python環境との統合設定
- 開発用便利スクリプトの作成

**スコープ外:**
- 各パッケージ固有のタスク定義
- CI/CDパイプラインの設定
- デプロイメント設定
- 詳細なキャッシュ戦略

## 参照するドキュメント

- `/docs/development/coding-standards.md`
- `/CLAUDE.md`
- [moonrepo公式ドキュメント](https://moonrepo.dev/docs)

## 完了条件

### 必須条件
- [ ] moonrepoがインストールされている
- [ ] `moon --version` が正常に実行できる
- [ ] `.moon/workspace.yml` が作成されている
- [ ] `.moon/toolchain.yml` が作成されている
- [ ] `.moon/tasks.yml` が作成されている
- [ ] `.moon/projects.yml` が作成されている
- [ ] `moon list` でプロジェクト一覧が表示される
- [ ] `moon run :install` が実行できる

### 動作確認
- [ ] `moon check shared` が正常終了する
- [ ] `scripts/dev.sh check` が正常実行できる
- [ ] `scripts/moon-check.sh` が正常実行できる
- [ ] 各パッケージで `moon run <project>:lint` が実行できる

### ドキュメント確認
- [ ] moonrepo設定ファイルにコメントが記載されている
- [ ] スクリプトファイルにusage情報が含まれている

## トラブルシューティング

### よくある問題

1. **moonrepoインストールが失敗する**
   - 解決策: 権限を確認、または npm 経由でインストール

2. **`moon list` が空を返す**
   - 解決策: `.moon/workspace.yml` の projects 設定を確認

3. **タスクが見つからない**
   - 解決策: 各パッケージの `moon.yml` が存在するか確認

4. **Python環境が認識されない**
   - 解決策: `.moon/toolchain.yml` のPython設定を確認

### ヘルプリソース

- [Moonrepo Documentation](https://moonrepo.dev/docs)
- [Moonrepo Configuration Reference](https://moonrepo.dev/docs/config)
- プロジェクトの `docs/development/coding-standards.md`

## レビュー観点

### 技術的正確性と実装可能性
- [ ] moonrepo のインストールと設定が正しく実行されている
- [ ] .moon/workspace.yml の設定がプロジェクト構造と一致している
- [ ] .moon/toolchain.yml の Python 設定が適切
- [ ] タスク定義が正しく動作する
- [ ] uv との統合が適切に設定されている

### 統合考慮事項
- [ ] 既存プロジェクト構造との連携が適切
- [ ] 各パッケージの依存関係が正しく設定されている
- [ ] タスクの依存関係と実行順序が適切
- [ ] キャッシュ戦略が適切に設定されている

### 品質標準
- [ ] コーディング規約に準拠した設定ファイル
- [ ] エラーハンドリングとログ出力が適切
- [ ] スクリプトの使用方法が明確に文書化されている
- [ ] テスト実行環境が適切に設定されている

### セキュリティと性能考慮事項
- [ ] セキュリティチェックが統合されている
- [ ] 並列実行時のリソース管理が適切
- [ ] キャッシュ機能が適切に設定されている
- [ ] ビルド成果物のセキュリティが適切

### 保守性とドキュメント
- [ ] 設定ファイルに適切なコメントが記載されている
- [ ] 開発者が理解しやすいドキュメント構成
- [ ] トラブルシューティング情報が充実している
- [ ] アップグレードパスが明確に定義されている

### Moonrepo 固有の観点
- [ ] ワークスペース設定がプロジェクト規模に適切
- [ ] プロジェクト自動検出が正しく動作する
- [ ] タスクの依存関係グラフが適切
- [ ] キャッシュ戦略がパフォーマンスに貢献している
- [ ] スクリプトの使い勝手が良い
- [ ] エラーハンドリングが適切に実装されている

## 次のタスクへの引き継ぎ

### 02_shared_foundation.md への前提条件
- moonrepoが正常に動作する
- 全パッケージがmoonrepoに認識されている
- 共通タスクが実行可能

### 引き継ぎファイル
- `.moon/` - moonrepo設定ディレクトリ
- `scripts/dev.sh` - 開発用スクリプト
- `scripts/moon-check.sh` - 品質チェックスクリプト
