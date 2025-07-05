# Task: 共通基盤（shared）の初期設定

## タスクの目的

全コンポーネントが依存する共通基盤を最初に構築し、並列開発における依存関係の基盤を整備する。

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
```

### 5. 設定管理の基本クラス

`src/refnet_shared/config/__init__.py`:

```python
"""設定管理モジュール."""

from pydantic import BaseModel
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


class Settings(BaseSettings):
    """アプリケーション設定."""
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()

    # 環境変数の設定
    semantic_scholar_api_key: str | None = None
    openai_api_key: str | None = None

    # ロギング設定
    log_level: str = "INFO"

    model_config = {
        "env_file": ".env",
        "env_nested_delimiter": "__",
    }


# グローバル設定インスタンス
settings = Settings()
```

### 6. ロギング設定

`src/refnet_shared/utils/__init__.py`:

```python
"""ユーティリティモジュール."""

import structlog
from refnet_shared.config import settings


def setup_logging() -> None:
    """ロギング設定の初期化."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """ロガー取得."""
    return structlog.get_logger(name)
```

### 7. 基本的なテストセットアップ

`tests/conftest.py`:

```python
"""pytest設定."""

import pytest
from refnet_shared.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """テスト用設定."""
    return Settings(
        database__host="localhost",
        database__database="refnet_test",
        redis__database=1,
    )
```

## スコープ

- 共通パッケージの基本構造作成
- 設定管理システムの基盤
- 共通例外クラスの定義
- ロギング設定の基盤
- 基本的なテスト環境の設定

**スコープ外:**
- 具体的なデータベースモデル定義
- 外部API クライアント実装
- 複雑なビジネスロジック

## 参照するドキュメント

- `/docs/database/schema.md`
- `/docs/development/coding-standards.md`
- `/CLAUDE.md`

## 完了条件

- [ ] package/shared/src/refnet_shared/ の基本構造が作成されている
- [ ] pyproject.toml が適切に設定されている
- [ ] moon.yml が作成されている
- [ ] 基本的な設定管理クラスが実装されている
- [ ] 共通例外クラスが定義されている
- [ ] ロギング設定が実装されている
- [ ] `cd package/shared && moon check` が正常終了する
