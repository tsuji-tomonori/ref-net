# Task: 共通基盤（shared）の初期設定

## タスクの目的

全コンポーネントが依存する共通基盤を最初に構築し、並列開発における依存関係の基盤を整備する。このタスクは Phase 2以降の全てのサービスが使用する基本ライブラリとなる。

## 前提条件

- 00_project_structure.mdが完了している
- 01_monorepo_setup.mdが完了している
- moonrepoが正常に動作する

## 実施内容

### 1. 共通パッケージの基本構造

```bash
# package/shared配下の構造
cd package/shared
mkdir -p src/refnet_shared/{models,config,utils,exceptions}
touch src/refnet_shared/__init__.py
touch src/refnet_shared/models/__init__.py
touch src/refnet_shared/config/__init__.py
touch src/refnet_shared/utils/__init__.py
touch src/refnet_shared/exceptions/__init__.py
```

### 2. pyproject.toml の設定

```toml
[project]
name = "refnet-shared"
version = "0.1.0"
description = "Shared utilities and models for ref-net system"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "sqlalchemy>=2.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "alembic>=1.13.0",
    "psycopg2-binary>=2.9.0",
    "redis>=5.0.0",
    "celery>=5.3.0",
    "structlog>=23.0.0",
    "mypy>=1.16.1",
    "pytest>=8.4.1",
    "ruff>=0.12.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project.scripts]
refnet-shared = "refnet_shared.cli:main"

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

### 3. moon.yml の設定

```yaml
type: library
language: python

dependsOn:
  - root

tasks:
  install:
    command: uv sync
    inputs:
      - "pyproject.toml"
      - "uv.lock"

  lint:
    command: ruff check src/
    inputs:
      - "src/**/*.py"

  format:
    command: ruff format src/
    inputs:
      - "src/**/*.py"

  typecheck:
    command: mypy src/
    inputs:
      - "src/**/*.py"

  test:
    command: pytest tests/
    inputs:
      - "src/**/*.py"
      - "tests/**/*.py"

  build:
    command: python -m build
    inputs:
      - "src/**/*.py"
      - "pyproject.toml"
    outputs:
      - "dist/"

  check:
    deps:
      - lint
      - typecheck
      - test
```

### 4. 基本的なエントリーポイントの作成

`src/refnet_shared/__init__.py`:

```python
"""RefNet共通ライブラリ."""

__version__ = "0.1.0"
__all__ = ["__version__"]
```

`src/refnet_shared/exceptions/__init__.py`:

```python
"""RefNet共通例外クラス."""


class RefNetException(Exception):
    """RefNetシステムの基底例外クラス."""

    pass


class ConfigurationError(RefNetException):
    """設定エラー."""

    pass


class DatabaseError(RefNetException):
    """データベース関連エラー."""

    pass


class ExternalAPIError(RefNetException):
    """外部API関連エラー."""

    pass


class ProcessingError(RefNetException):
    """処理エラー."""

    pass


class ValidationError(RefNetException):
    """検証エラー."""

    pass
```

### 5. 設定管理の基本クラス

`src/refnet_shared/config/__init__.py`:

```python
"""設定管理モジュール."""

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    """データベース設定."""

    host: str = "localhost"
    port: int = 5432
    database: str = "refnet"
    username: str = "refnet"
    password: str = "refnet"

    @property
    def url(self) -> str:
        """SQLAlchemy接続URL."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


class RedisConfig(BaseModel):
    """Redis設定."""

    host: str = "localhost"
    port: int = 6379
    database: int = 0

    @property
    def url(self) -> str:
        """Redis接続URL."""
        return f"redis://{self.host}:{self.port}/{self.database}"


class LoggingConfig(BaseModel):
    """ログ設定."""

    level: str = "INFO"
    format: str = "json"  # json or console
    file_path: str | None = None


class SecurityConfig(BaseModel):
    """セキュリティ設定."""

    jwt_secret: str = "development-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60


class Settings(BaseSettings):
    """アプリケーション設定."""

    # 基本設定
    app_name: str = "RefNet"
    version: str = "0.1.0"
    debug: bool = False

    # データベース設定
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # Redis設定
    redis: RedisConfig = Field(default_factory=RedisConfig)

    # ログ設定
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # セキュリティ設定
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # 外部API設定
    semantic_scholar_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Celery設定
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    # 出力設定
    output_dir: str = "./output"

    model_config = {
        "env_file": ".env",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
    }

    def __init__(self, **kwargs):
        """初期化."""
        super().__init__(**kwargs)

        # Celery URLのデフォルト設定
        if not self.celery_broker_url:
            self.celery_broker_url = self.redis.url
        if not self.celery_result_backend:
            self.celery_result_backend = self.redis.url


# グローバル設定インスタンス
settings = Settings()
```

### 6. ロギング設定

`src/refnet_shared/utils/__init__.py`:

```python
"""ユーティリティモジュール."""

import logging
import sys
from typing import Any, Dict

import structlog
from refnet_shared.config import settings


def setup_logging() -> None:
    """ロギング設定の初期化."""
    # 基本設定
    logging.basicConfig(
        level=getattr(logging, settings.logging.level.upper()),
        stream=sys.stdout,
    )

    # Structlogの設定
    if settings.logging.format == "json":
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """ロガー取得."""
    return structlog.get_logger(name)


def validate_required_settings() -> None:
    """必須設定の検証."""
    errors = []

    # データベース設定の検証
    if not settings.database.host:
        errors.append("DATABASE__HOST is required")

    # 本番環境でのセキュリティ設定検証
    if not settings.debug:
        if settings.security.jwt_secret == "development-secret-key":
            errors.append("SECURITY__JWT_SECRET must be set in production")

    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")


def get_app_info() -> Dict[str, Any]:
    """アプリケーション情報取得."""
    return {
        "name": settings.app_name,
        "version": settings.version,
        "debug": settings.debug,
        "database_url": settings.database.url.replace(settings.database.password, "***"),
        "redis_url": settings.redis.url,
        "logging_level": settings.logging.level,
    }
```

### 7. CLIエントリーポイント

`src/refnet_shared/cli.py`:

```python
"""共通ライブラリCLI."""

import click
from refnet_shared.config import settings
from refnet_shared.utils import get_app_info, setup_logging, validate_required_settings


@click.group()
def main() -> None:
    """RefNet共通ライブラリCLI."""
    setup_logging()


@main.command()
def info() -> None:
    """アプリケーション情報表示."""
    app_info = get_app_info()
    for key, value in app_info.items():
        click.echo(f"{key}: {value}")


@main.command()
def validate() -> None:
    """設定検証."""
    try:
        validate_required_settings()
        click.echo("✅ Configuration is valid")
    except ValueError as e:
        click.echo(f"❌ Configuration error: {e}")
        exit(1)


@main.command()
def version() -> None:
    """バージョン表示."""
    click.echo(f"RefNet Shared Library v{settings.version}")


if __name__ == "__main__":
    main()
```

### 8. 基本的なテストセットアップ

`tests/conftest.py`:

```python
"""pytest設定."""

import pytest
from refnet_shared.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """テスト用設定."""
    return Settings(
        debug=True,
        database__host="localhost",
        database__database="refnet_test",
        redis__database=1,
        logging__level="DEBUG",
        security__jwt_secret="test-secret-key",
    )


@pytest.fixture
def mock_env_vars(monkeypatch):
    """テスト用環境変数."""
    test_vars = {
        "DATABASE__HOST": "localhost",
        "DATABASE__DATABASE": "refnet_test",
        "REDIS__DATABASE": "1",
        "LOGGING__LEVEL": "DEBUG",
    }
    for key, value in test_vars.items():
        monkeypatch.setenv(key, value)
```

`tests/test_config.py`:

```python
"""設定テスト."""

import pytest
from refnet_shared.config import Settings, DatabaseConfig, RedisConfig


def test_database_config():
    """データベース設定テスト."""
    config = DatabaseConfig(
        host="testhost",
        port=5433,
        database="testdb",
        username="testuser",
        password="testpass"
    )

    expected_url = "postgresql://testuser:testpass@testhost:5433/testdb"
    assert config.url == expected_url


def test_redis_config():
    """Redis設定テスト."""
    config = RedisConfig(host="redishost", port=6380, database=2)

    expected_url = "redis://redishost:6380/2"
    assert config.url == expected_url


def test_settings_defaults():
    """設定デフォルト値テスト."""
    settings = Settings()

    assert settings.app_name == "RefNet"
    assert settings.version == "0.1.0"
    assert settings.debug is False
    assert settings.database.host == "localhost"
    assert settings.redis.host == "localhost"


def test_settings_with_test_fixture(test_settings):
    """テスト用設定テスト."""
    assert test_settings.debug is True
    assert test_settings.database.database == "refnet_test"
    assert test_settings.redis.database == 1
```

### 9. README.md の作成

`README.md`:

```markdown
# RefNet Shared Library

RefNet論文関係性可視化システムの共通ライブラリです。

## 機能

- 設定管理（Pydantic Settings）
- ロギング設定（structlog）
- 共通例外クラス
- ユーティリティ関数

## インストール

```bash
uv sync
```

## 使用方法

### 設定

```python
from refnet_shared.config import settings

# データベースURL取得
db_url = settings.database.url

# Redis URL取得
redis_url = settings.redis.url
```

### ロギング

```python
from refnet_shared.utils import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)
logger.info("Hello, world!")
```

### CLI

```bash
# アプリケーション情報表示
refnet-shared info

# 設定検証
refnet-shared validate

# バージョン表示
refnet-shared version
```

## 開発

```bash
# テスト実行
moon run shared:test

# リント実行
moon run shared:lint

# 型チェック
moon run shared:typecheck

# 全チェック実行
moon run shared:check
```
```

## スコープ

- 共通パッケージの基本構造作成
- 設定管理システムの基盤
- 共通例外クラスの定義
- ロギング設定の基盤
- 基本的なテスト環境の設定
- CLIエントリーポイントの作成

**スコープ外:**
- 具体的なデータベースモデル定義
- 外部API クライアント実装
- 複雑なビジネスロジック
- キャッシュ機能

## 参照するドキュメント

- `/docs/database/schema.md`
- `/docs/development/coding-standards.md`
- `/CLAUDE.md`

## 完了条件

### 必須条件
- [ ] `package/shared/src/refnet_shared/` の基本構造が作成されている
- [ ] pyproject.toml が適切に設定されている
- [ ] moon.yml が作成されている
- [ ] 基本的な設定管理クラスが実装されている
- [ ] 共通例外クラスが定義されている
- [ ] ロギング設定が実装されている
- [ ] CLIエントリーポイントが作成されている

### 動作確認
- [ ] `cd package/shared && moon run shared:install` が正常終了する
- [ ] `cd package/shared && moon run shared:check` が正常終了する
- [ ] `refnet-shared info` が正常実行できる
- [ ] `refnet-shared validate` が正常実行できる

### テスト条件
- [ ] 単体テストが作成されている
- [ ] テストカバレッジが80%以上
- [ ] 型チェックが通る
- [ ] リントチェックが通る

## トラブルシューティング

### よくある問題

1. **インポートエラーが発生する**
   - 解決策: `src/` ディレクトリ構造を確認、`__init__.py` が存在するか確認

2. **設定が読み込まれない**
   - 解決策: 環境変数名が正しいか確認、`.env` ファイルの場所を確認

3. **テストが失敗する**
   - 解決策: テスト用設定が正しく適用されているか確認

## 次のタスクへの引き継ぎ

### 03_environment_config.md への前提条件
- 基本的な設定管理システムが動作する
- ロギングシステムが動作する
- 共通例外クラスが利用可能

### Phase 2 への前提条件
- 共通ライブラリがインポート可能
- 設定管理システムが確立済み
- テスト基盤が整備済み

### 引き継ぎファイル
- `package/shared/src/refnet_shared/` - 共通ライブラリ
- `package/shared/pyproject.toml` - パッケージ設定
- `package/shared/tests/` - テストファイル
