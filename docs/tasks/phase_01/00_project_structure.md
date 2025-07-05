# Task: プロジェクト全体構造の作成

## タスクの目的

並列開発を開始する前に、プロジェクト全体のディレクトリ構造を作成し、各コンポーネントが独立して開発できる基盤を整備する。このタスクはPhase 1の事前準備として、他のすべてのタスクの前提条件となる。

## 実施内容

### 1. ディレクトリ構造の作成

```bash
# プロジェクトルートで実行
mkdir -p package/{api,crawler,summarizer,generator,shared}
mkdir -p package/shared/{models,config,utils}
mkdir -p scripts
mkdir -p tests/{unit,integration}
mkdir -p output/papers
mkdir -p docs/{api,database,infrastructure,development}
```

### 2. 各パッケージの初期化

各パッケージディレクトリに以下を作成：

#### uv init による初期化

```bash
cd package/api && uv init
cd package/crawler && uv init
cd package/summarizer && uv init
cd package/generator && uv init
cd package/shared && uv init
```

#### pyproject.toml の設定

各パッケージの `pyproject.toml` を以下の内容で更新：

```toml
[project]
name = "<package-name>"
version = "0.1.0"
description = "<package-description>"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "mypy>=1.16.1",
    "pytest>=8.4.1",
    "ruff>=0.12.1",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
extra_checks = true
```

### 3. 初期 moon.yml の作成

各パッケージに基本的な `moon.yml` を作成：

```yaml
# package/<package-name>/moon.yml
type: application
language: python

tasks:
  lint:
    command: ruff check .
    inputs:
      - "**/*.py"

  format:
    command: ruff format .
    inputs:
      - "**/*.py"

  typecheck:
    command: mypy .
    inputs:
      - "**/*.py"

  test:
    command: pytest tests/ -v
    inputs:
      - "**/*.py"
      - "tests/**/*.py"

  check:
    deps:
      - lint
      - typecheck
      - test
```

### 4. .gitignore の更新

プロジェクトルートの `.gitignore` に追加：

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/
.venv/

# Testing
.coverage
.pytest_cache/
htmlcov/
.tox/
.mypy_cache/
.dmypy.json
dmypy.json

# UV
.venv/

# Output
output/

# Environment
.env
.env.local
.env.development
.env.staging
.env.production

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# Documentation
docs/_build/
```

### 5. 基本的なディレクトリREADME作成

各主要ディレクトリにREADME.mdを作成：

#### package/README.md
```markdown
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
```

### 6. 基本的なテスト構造の作成

```bash
# テスト用設定ファイル
touch tests/__init__.py
touch tests/conftest.py
```

#### tests/conftest.py
```python
"""pytest設定."""

import pytest
import os
import sys

# プロジェクトルートをPYTHONPATHに追加
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, "package"))

@pytest.fixture
def project_root_path():
    """プロジェクトルートパス."""
    return project_root
```

## スコープ

- プロジェクト全体のディレクトリ構造作成
- 各パッケージの初期設定ファイル作成
- Pythonパッケージとしての初期化
- 開発ツールの設定（ruff, mypy, pytest）
- 基本的なドキュメント構造

**スコープ外:**
- 各パッケージの実装
- Dockerファイルの作成
- CI/CD設定
- 詳細なAPI設計

## 参照するドキュメント

- `/docs/architecture/project-structure.md`
- `/docs/development/coding-standards.md`
- `/CLAUDE.md`

## moon のテンプレート

moonrepoは、JavaScriptエコシステムで生まれたビルドツールですが、言語に依存しないタスクランナーとして使用できます。

### moon.yml の基本構造

```yaml
type: application | library  # プロジェクトタイプ
language: python | node | ...  # 使用言語

# 継承（オプション）
extends: ./shared/moon.yml

# タスク定義
tasks:
  <task-name>:
    command: <実行コマンド>
    inputs:  # 変更監視対象
      - "**/*.py"
    outputs:  # 生成物（キャッシュ用）
      - "dist/"
    deps:  # 依存タスク
      - <other-task>
```

### check タスクについて

`check` タスクは、コード品質を保証する全てのチェックを実行する統合タスクです：

```yaml
tasks:
  check:
    deps:
      - lint      # コードスタイルチェック
      - typecheck # 型チェック
      - test      # ユニットテスト
```

`moon :check` を実行することで、全パッケージの品質チェックを並列実行できます。

## 完了条件

- [ ] 全ディレクトリ構造が作成されている
- [ ] 各パッケージに pyproject.toml が配置されている
- [ ] 各パッケージに moon.yml が配置されている
- [ ] プロジェクトルートで `ls package/` が5つのディレクトリを表示する
- [ ] .gitignore が適切に設定されている
- [ ] 基本的なREADME.mdが各ディレクトリに存在する
- [ ] tests/conftest.py が作成されている

## レビュー観点

### 技術的正確性と実装可能性
- [ ] ディレクトリ構造がプロジェクトアーキテクチャと一致している
- [ ] pyproject.toml の依存関係設定が適切で実行可能
- [ ] moon.yml のタスク定義が正しく設定されている
- [ ] Python 3.12 の機能と互換性がある
- [ ] 各パッケージのモジュール構造が適切に設計されている

### 統合考慮事項
- [ ] 各パッケージ間の依存関係が明確に定義されている
- [ ] 共通ライブラリの位置づけが適切
- [ ] moonrepo による統合管理が正しく設定されている
- [ ] 他のフェーズタスクとの連携が考慮されている

### 品質標準
- [ ] コーディング規約に準拠したファイル構成
- [ ] テスト構造が適切に設計されている
- [ ] .gitignore が包括的で適切
- [ ] エラーハンドリングとロギングの基盤が適切

### セキュリティと性能考慮事項
- [ ] 機密情報がリポジトリに含まれていない
- [ ] セキュリティ設定の基盤が適切
- [ ] パフォーマンスに影響する設定が適切
- [ ] 権限管理の基盤が考慮されている

### 保守性とドキュメント
- [ ] 各ディレクトリの目的が明確に文書化されている
- [ ] 拡張性を考慮した構造設計
- [ ] 開発者が理解しやすい構成
- [ ] 継続的な保守を考慮したファイル配置

### プロジェクト構造固有の観点
- [ ] モノレポ構成が適切に設計されている
- [ ] パッケージ間の依存関係に循環参照がない
- [ ] 各パッケージの責務が明確に分離されている
- [ ] 開発・テスト・本番の各環境で正しく動作する構成
- [ ] 並列開発に適した基盤構造

## 次のタスクへの引き継ぎ

### 01_monorepo_setup.md への前提条件
- 全パッケージディレクトリが存在
- 基本的な pyproject.toml が配置済み
- プロジェクトルート構造が確立済み

### 引き継ぎファイル
- `package/*/pyproject.toml` - パッケージ設定
- `package/*/moon.yml` - タスク設定
- `.gitignore` - Git除外設定
- `tests/conftest.py` - テスト設定
