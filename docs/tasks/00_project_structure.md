# Task: プロジェクト全体構造の作成

## タスクの目的

並列開発を開始する前に、プロジェクト全体のディレクトリ構造を作成し、各コンポーネントが独立して開発できる基盤を整備する。

## 実施内容

### 1. ディレクトリ構造の作成

```bash
# プロジェクトルートで実行
mkdir -p package/{api,crawler,summarizer,generator,shared}
mkdir -p package/shared/{models,config,utils}
mkdir -p scripts
mkdir -p tests/{unit,integration}
mkdir -p output/papers
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

### 3. moon.yml の作成

各パッケージに `moon.yml` を作成：

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
    command: pytest tests/
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

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

## スコープ

- プロジェクト全体のディレクトリ構造作成
- 各パッケージの初期設定ファイル作成
- Pythonパッケージとしての初期化
- 開発ツールの設定（ruff, mypy, pytest）

**スコープ外:**
- 各パッケージの実装
- Dockerファイルの作成
- CI/CD設定

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
- [ ] プロジェクトルートで `moon :check` が実行できる（エラーは許容）
- [ ] .gitignore が適切に設定されている

## レビュー観点

### 構造設計の妥当性
- [ ] ディレクトリ構造がプロジェクトの要件を満たしているか
- [ ] パッケージ分割が論理的で保守しやすいか
- [ ] 依存関係の方向性が適切に設計されているか
- [ ] 将来の機能拡張に対応できる柔軟性があるか

### 設定ファイルの適切性
- [ ] pyproject.tomlの設定が各パッケージの目的に適しているか
- [ ] ruff/mypyの設定がコーディング規約に準拠しているか
- [ ] moon.ymlのタスク定義が開発フローに適しているか
- [ ] 共通設定と個別設定が適切に分離されているか

### 開発環境の整合性
- [ ] Python 3.12の要件が全体で一貫しているか
- [ ] 依存関係のバージョンが互換性を保っているか
- [ ] 開発ツールの設定が標準化されているか
- [ ] 環境変数や設定ファイルの管理方法が明確か

### 運用・保守性
- [ ] .gitignoreが適切で漏れがないか
- [ ] ログやキャッシュファイルの配置が適切か
- [ ] バックアップや復旧手順が考慮されているか
- [ ] チーム開発でのファイル競合リスクが最小化されているか

### コンプライアンス
- [ ] ライセンス要件が満たされているか
- [ ] セキュリティ上の懸念事項がないか
- [ ] 組織のコーディング標準に準拠しているか
- [ ] 外部依存関係のライセンスが確認されているか
