# Task: 環境設定管理システム

## タスクの目的

開発・ステージング・本番環境を適切に分離し、環境ごとの設定管理システムを確立する。セキュリティを考慮した設定管理と、設定値の検証機能を実装する。

## 前提条件

- 00_project_structure.mdが完了している
- 01_monorepo_setup.mdが完了している
- 02_shared_foundation.mdが完了している
- 基本的な設定管理クラスが実装済み

## 実施内容

### 1. 環境別設定ファイルの作成

#### .env.example（テンプレート）
```bash
# =================================================
# RefNet環境設定テンプレート
# このファイルをコピーして .env として使用してください
# =================================================

# 環境設定
NODE_ENV=development
DEBUG=true

# データベース設定
DATABASE__HOST=localhost
DATABASE__PORT=5432
DATABASE__DATABASE=refnet
DATABASE__USERNAME=refnet
DATABASE__PASSWORD=your_secure_password_here

# Redis設定
REDIS__HOST=localhost
REDIS__PORT=6379
REDIS__DATABASE=0

# 外部APIキー（本番環境では必須）
SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_api_key
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# セキュリティ設定（本番環境では必須変更）
SECURITY__JWT_SECRET=your_very_secure_jwt_secret_key_here
SECURITY__JWT_ALGORITHM=HS256
SECURITY__JWT_EXPIRATION_MINUTES=60

# ログ設定
LOGGING__LEVEL=INFO
LOGGING__FORMAT=json
LOGGING__FILE_PATH=

# Celery設定
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=

# 出力設定
OUTPUT_DIR=./output

# アプリケーション設定
APP_NAME=RefNet
VERSION=0.1.0
```

#### .env.development
```bash
# 開発環境設定
NODE_ENV=development
DEBUG=true

# データベース設定（開発用）
DATABASE__HOST=localhost
DATABASE__PORT=5432
DATABASE__DATABASE=refnet_dev
DATABASE__USERNAME=refnet_dev
DATABASE__PASSWORD=refnet_dev_password

# Redis設定（開発用）
REDIS__HOST=localhost
REDIS__PORT=6379
REDIS__DATABASE=0

# ログ設定（開発用）
LOGGING__LEVEL=DEBUG
LOGGING__FORMAT=console

# セキュリティ設定（開発用・緩い設定）
SECURITY__JWT_SECRET=development-jwt-secret-key
SECURITY__JWT_EXPIRATION_MINUTES=480  # 8時間

# 外部APIキー（開発用・オプション）
SEMANTIC_SCHOLAR_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

#### .env.staging
```bash
# ステージング環境設定
NODE_ENV=staging
DEBUG=false

# データベース設定（ステージング用）
DATABASE__HOST=staging-db.example.com
DATABASE__PORT=5432
DATABASE__DATABASE=refnet_staging
DATABASE__USERNAME=refnet_staging
DATABASE__PASSWORD=staging_secure_password

# Redis設定（ステージング用）
REDIS__HOST=staging-redis.example.com
REDIS__PORT=6379
REDIS__DATABASE=0

# ログ設定（ステージング用）
LOGGING__LEVEL=INFO
LOGGING__FORMAT=json
LOGGING__FILE_PATH=/var/log/refnet/app.log

# セキュリティ設定（ステージング用）
SECURITY__JWT_SECRET=staging-jwt-secret-key-change-in-production
SECURITY__JWT_EXPIRATION_MINUTES=60

# 外部APIキー（ステージング用）
SEMANTIC_SCHOLAR_API_KEY=staging_semantic_scholar_key
OPENAI_API_KEY=staging_openai_key
ANTHROPIC_API_KEY=staging_anthropic_key
```

#### .env.production
```bash
# 本番環境設定
NODE_ENV=production
DEBUG=false

# データベース設定（本番用）
DATABASE__HOST=prod-db.example.com
DATABASE__PORT=5432
DATABASE__DATABASE=refnet_production
DATABASE__USERNAME=refnet_production
DATABASE__PASSWORD=production_very_secure_password

# Redis設定（本番用）
REDIS__HOST=prod-redis.example.com
REDIS__PORT=6379
REDIS__DATABASE=0

# ログ設定（本番用）
LOGGING__LEVEL=WARNING
LOGGING__FORMAT=json
LOGGING__FILE_PATH=/var/log/refnet/app.log

# セキュリティ設定（本番用・必須変更）
SECURITY__JWT_SECRET=production-jwt-secret-key-must-be-very-secure
SECURITY__JWT_EXPIRATION_MINUTES=30

# 外部APIキー（本番用・必須）
SEMANTIC_SCHOLAR_API_KEY=production_semantic_scholar_key
OPENAI_API_KEY=production_openai_key
ANTHROPIC_API_KEY=production_anthropic_key
```

### 2. 環境設定拡張クラス

`package/shared/src/refnet_shared/config/environment.py`:

```python
"""環境設定管理."""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any

from pydantic import BaseModel, Field, validator
from refnet_shared.config import Settings
from refnet_shared.exceptions import ConfigurationError


class Environment(str, Enum):
    """環境種別."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class EnvironmentSettings(Settings):
    """環境対応設定クラス."""

    environment: Environment = Environment.DEVELOPMENT

    model_config = {
        "env_file": [
            ".env",
            ".env.local",
            f".env.{os.getenv('NODE_ENV', 'development')}",
        ],
        "env_file_encoding": "utf-8",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
    }

    @validator("environment", pre=True)
    def validate_environment(cls, v):
        """環境値の検証."""
        if isinstance(v, str):
            try:
                return Environment(v.lower())
            except ValueError:
                raise ValueError(f"Invalid environment: {v}")
        return v

    def is_development(self) -> bool:
        """開発環境かどうか."""
        return self.environment == Environment.DEVELOPMENT

    def is_staging(self) -> bool:
        """ステージング環境かどうか."""
        return self.environment == Environment.STAGING

    def is_production(self) -> bool:
        """本番環境かどうか."""
        return self.environment == Environment.PRODUCTION

    def is_testing(self) -> bool:
        """テスト環境かどうか."""
        return self.environment == Environment.TESTING


class ConfigValidator:
    """設定検証クラス."""

    def __init__(self, settings: EnvironmentSettings):
        """初期化."""
        self.settings = settings
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> None:
        """全設定の検証."""
        self._validate_database()
        self._validate_security()
        self._validate_external_apis()
        self._validate_logging()
        self._validate_environment_specific()

        if self.errors:
            raise ConfigurationError(f"Configuration errors: {'; '.join(self.errors)}")

    def _validate_database(self) -> None:
        """データベース設定検証."""
        db = self.settings.database

        if not db.host:
            self.errors.append("DATABASE__HOST is required")

        if not db.username:
            self.errors.append("DATABASE__USERNAME is required")

        if not db.password:
            self.errors.append("DATABASE__PASSWORD is required")

        if self.settings.is_production():
            if db.password == "refnet" or "test" in db.password.lower():
                self.errors.append("Production database password is too weak")

    def _validate_security(self) -> None:
        """セキュリティ設定検証."""
        security = self.settings.security

        if self.settings.is_production():
            if "development" in security.jwt_secret or "test" in security.jwt_secret:
                self.errors.append("Production JWT secret must be changed from default")

            if len(security.jwt_secret) < 32:
                self.errors.append("Production JWT secret must be at least 32 characters")

            if security.jwt_expiration_minutes > 60:
                self.warnings.append("JWT expiration time is quite long for production")

    def _validate_external_apis(self) -> None:
        """外部API設定検証."""
        if self.settings.is_production():
            if not self.settings.semantic_scholar_api_key:
                self.warnings.append("SEMANTIC_SCHOLAR_API_KEY not set (rate limiting may apply)")

            if not self.settings.openai_api_key and not self.settings.anthropic_api_key:
                self.errors.append("Either OPENAI_API_KEY or ANTHROPIC_API_KEY must be set in production")

    def _validate_logging(self) -> None:
        """ログ設定検証."""
        logging = self.settings.logging

        if logging.file_path:
            file_path = Path(logging.file_path)
            if not file_path.parent.exists():
                self.errors.append(f"Log directory does not exist: {file_path.parent}")

    def _validate_environment_specific(self) -> None:
        """環境固有の検証."""
        if self.settings.is_production():
            if self.settings.debug:
                self.errors.append("DEBUG must be false in production")

            if self.settings.logging.level.upper() == "DEBUG":
                self.warnings.append("DEBUG log level in production may impact performance")


def load_environment_settings() -> EnvironmentSettings:
    """環境設定の読み込み."""
    # 環境変数から環境種別を取得
    env = os.getenv("NODE_ENV", "development").lower()
    os.environ["ENVIRONMENT"] = env

    settings = EnvironmentSettings()

    # 設定検証
    validator = ConfigValidator(settings)
    validator.validate_all()

    # 警告の表示
    if validator.warnings:
        import warnings
        for warning in validator.warnings:
            warnings.warn(f"Configuration warning: {warning}")

    return settings
```

### 3. 設定管理ユーティリティ

`package/shared/src/refnet_shared/utils/config_utils.py`:

```python
"""設定管理ユーティリティ."""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

from refnet_shared.config.environment import Environment, EnvironmentSettings


def get_env_file_path(environment: Environment) -> Path:
    """環境ファイルパス取得."""
    return Path(f".env.{environment.value}")


def create_env_file_from_template(environment: Environment, overrides: Optional[Dict[str, Any]] = None) -> None:
    """テンプレートから環境ファイル作成."""
    template_path = Path(".env.example")
    env_path = get_env_file_path(environment)

    if not template_path.exists():
        raise FileNotFoundError("Template file .env.example not found")

    # テンプレートの読み込み
    with open(template_path, 'r') as f:
        content = f.read()

    # 環境固有の値を設定
    if overrides:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '=' in line and not line.strip().startswith('#'):
                key = line.split('=')[0].strip()
                if key in overrides:
                    lines[i] = f"{key}={overrides[key]}"
        content = '\n'.join(lines)

    # ファイル作成
    with open(env_path, 'w') as f:
        f.write(content)


def export_settings_to_json(settings: EnvironmentSettings, output_path: Path) -> None:
    """設定をJSONファイルにエクスポート（機密情報を除く）."""
    safe_settings = {
        "app_name": settings.app_name,
        "version": settings.version,
        "environment": settings.environment.value,
        "debug": settings.debug,
        "database": {
            "host": settings.database.host,
            "port": settings.database.port,
            "database": settings.database.database,
            "username": settings.database.username,
            # パスワードは除外
        },
        "redis": {
            "host": settings.redis.host,
            "port": settings.redis.port,
            "database": settings.redis.database,
        },
        "logging": {
            "level": settings.logging.level,
            "format": settings.logging.format,
            "file_path": settings.logging.file_path,
        },
        "security": {
            "jwt_algorithm": settings.security.jwt_algorithm,
            "jwt_expiration_minutes": settings.security.jwt_expiration_minutes,
            # JWT秘密鍵は除外
        },
        "output_dir": settings.output_dir,
    }

    with open(output_path, 'w') as f:
        json.dump(safe_settings, f, indent=2)


def check_required_env_vars(environment: Environment) -> Dict[str, bool]:
    """必須環境変数のチェック."""
    required_vars = {
        Environment.DEVELOPMENT: [
            "DATABASE__HOST",
            "DATABASE__USERNAME",
            "DATABASE__PASSWORD",
        ],
        Environment.STAGING: [
            "DATABASE__HOST",
            "DATABASE__USERNAME",
            "DATABASE__PASSWORD",
            "SECURITY__JWT_SECRET",
        ],
        Environment.PRODUCTION: [
            "DATABASE__HOST",
            "DATABASE__USERNAME",
            "DATABASE__PASSWORD",
            "SECURITY__JWT_SECRET",
            "OPENAI_API_KEY",  # または ANTHROPIC_API_KEY
        ],
    }

    result = {}
    for var in required_vars.get(environment, []):
        result[var] = bool(os.getenv(var))

    return result
```

### 4. CLI機能の拡張

`package/shared/src/refnet_shared/cli.py` に環境管理コマンドを追加:

```python
"""CLI機能の拡張."""

import click
from pathlib import Path
from refnet_shared.config.environment import Environment, load_environment_settings, ConfigValidator
from refnet_shared.utils.config_utils import (
    create_env_file_from_template,
    export_settings_to_json,
    check_required_env_vars
)


@main.group()
def env() -> None:
    """環境設定管理."""
    pass


@env.command()
@click.argument('environment', type=click.Choice(['development', 'staging', 'production']))
def create(environment: str) -> None:
    """環境設定ファイル作成."""
    env_enum = Environment(environment)
    try:
        create_env_file_from_template(env_enum)
        click.echo(f"✅ Created .env.{environment} from template")
    except FileNotFoundError as e:
        click.echo(f"❌ Error: {e}")
        exit(1)


@env.command()
def validate() -> None:
    """現在の環境設定を検証."""
    try:
        settings = load_environment_settings()
        validator = ConfigValidator(settings)
        validator.validate_all()

        click.echo(f"✅ Configuration is valid for {settings.environment.value} environment")

        if validator.warnings:
            click.echo("\n⚠️  Warnings:")
            for warning in validator.warnings:
                click.echo(f"  - {warning}")

    except Exception as e:
        click.echo(f"❌ Configuration error: {e}")
        exit(1)


@env.command()
@click.option('--output', '-o', default='config.json', help='Output file path')
def export(output: str) -> None:
    """設定をJSONファイルにエクスポート."""
    try:
        settings = load_environment_settings()
        export_settings_to_json(settings, Path(output))
        click.echo(f"✅ Settings exported to {output}")
    except Exception as e:
        click.echo(f"❌ Export error: {e}")
        exit(1)


@env.command()
@click.argument('environment', type=click.Choice(['development', 'staging', 'production']))
def check(environment: str) -> None:
    """必須環境変数をチェック."""
    env_enum = Environment(environment)
    result = check_required_env_vars(env_enum)

    click.echo(f"Environment variable check for {environment}:")

    all_ok = True
    for var, is_set in result.items():
        status = "✅" if is_set else "❌"
        click.echo(f"  {status} {var}")
        if not is_set:
            all_ok = False

    if all_ok:
        click.echo(f"\n✅ All required variables are set for {environment}")
    else:
        click.echo(f"\n❌ Some required variables are missing for {environment}")
        exit(1)
```

### 5. テストの追加

`tests/test_environment_config.py`:

```python
"""環境設定テスト."""

import os
import pytest
from unittest.mock import patch
from refnet_shared.config.environment import Environment, EnvironmentSettings, ConfigValidator
from refnet_shared.exceptions import ConfigurationError


def test_environment_enum():
    """環境Enum テスト."""
    assert Environment.DEVELOPMENT == "development"
    assert Environment.STAGING == "staging"
    assert Environment.PRODUCTION == "production"


def test_environment_settings_defaults():
    """環境設定デフォルト値テスト."""
    settings = EnvironmentSettings()
    assert settings.environment == Environment.DEVELOPMENT
    assert settings.is_development() is True
    assert settings.is_production() is False


@patch.dict(os.environ, {"NODE_ENV": "production"})
def test_environment_settings_production():
    """本番環境設定テスト."""
    settings = EnvironmentSettings(environment="production")
    assert settings.environment == Environment.PRODUCTION
    assert settings.is_production() is True
    assert settings.is_development() is False


def test_config_validator_development():
    """開発環境設定検証テスト."""
    settings = EnvironmentSettings(
        environment=Environment.DEVELOPMENT,
        database__host="localhost",
        database__username="test",
        database__password="test"
    )

    validator = ConfigValidator(settings)
    validator.validate_all()  # エラーが発生しないことを確認


def test_config_validator_production_weak_password():
    """本番環境弱いパスワード検証テスト."""
    settings = EnvironmentSettings(
        environment=Environment.PRODUCTION,
        database__host="localhost",
        database__username="prod",
        database__password="test"  # 弱いパスワード
    )

    validator = ConfigValidator(settings)
    with pytest.raises(ConfigurationError):
        validator.validate_all()


def test_config_validator_production_weak_jwt():
    """本番環境弱いJWT検証テスト."""
    settings = EnvironmentSettings(
        environment=Environment.PRODUCTION,
        database__host="localhost",
        database__username="prod",
        database__password="strong_password",
        security__jwt_secret="development-secret"  # 弱いJWT
    )

    validator = ConfigValidator(settings)
    with pytest.raises(ConfigurationError):
        validator.validate_all()


def test_config_validator_production_no_api_keys():
    """本番環境APIキーなし検証テスト."""
    settings = EnvironmentSettings(
        environment=Environment.PRODUCTION,
        database__host="localhost",
        database__username="prod",
        database__password="strong_password",
        security__jwt_secret="very_secure_jwt_secret_key_for_production"
    )

    validator = ConfigValidator(settings)
    with pytest.raises(ConfigurationError):
        validator.validate_all()
```

### 6. ドキュメント更新

`package/shared/README.md` に環境設定セクションを追加:

```markdown
## 環境設定

### 環境ファイルの作成

```bash
# 開発環境用設定ファイル作成
refnet-shared env create development

# ステージング環境用設定ファイル作成
refnet-shared env create staging

# 本番環境用設定ファイル作成
refnet-shared env create production
```

### 設定検証

```bash
# 現在の環境設定を検証
refnet-shared env validate

# 特定環境の必須変数チェック
refnet-shared env check production
```

### 設定エクスポート

```bash
# 設定をJSONでエクスポート（機密情報除く）
refnet-shared env export --output config.json
```

### 環境切り替え

```bash
# 環境変数で指定
export NODE_ENV=production

# または.envファイルで指定
echo "NODE_ENV=production" > .env
```
```

## スコープ

- 環境別設定ファイルの作成
- 環境設定検証システム
- CLI環境管理機能
- セキュリティ設定の強化
- 設定値のバリデーション

**スコープ外:**
- CI/CD環境での設定管理
- Secretsマネージャー統合
- 動的設定変更機能
- 設定値の暗号化

## 参照するドキュメント

- `/docs/security/configuration.md`
- `/docs/development/coding-standards.md`
- `/CLAUDE.md`

## 完了条件

### 必須条件
- [ ] 各環境用の.envファイルが作成されている
- [ ] 環境設定クラスが実装されている
- [ ] 設定検証機能が実装されている
- [ ] CLI環境管理コマンドが実装されている
- [ ] 環境切り替えが正常に動作する

### セキュリティ条件
- [ ] 本番環境でのデフォルト値が安全
- [ ] 機密情報がログに出力されない
- [ ] 設定ファイルが.gitignoreに追加されている
- [ ] 弱い設定値の検証が動作する

### テスト条件
- [ ] 環境設定のテストが作成されている
- [ ] 設定検証のテストが作成されている
- [ ] テストカバレッジが80%以上

### ドキュメント条件
- [ ] 環境設定のドキュメントが更新されている
- [ ] CLI使用方法が記載されている

## トラブルシューティング

### よくある問題

1. **環境ファイルが読み込まれない**
   - 解決策: ファイル名と NODE_ENV の値を確認

2. **設定検証でエラーが出る**
   - 解決策: 必須環境変数が設定されているか確認

3. **本番環境でデバッグ情報が出力される**
   - 解決策: DEBUG=false、LOG_LEVEL=WARNING に設定

## レビュー観点

### 技術的正確性と実装可能性
- [ ] 環境別設定ファイルが正しく読み込まれる
- [ ] 環境変数の優先順位が適切
- [ ] 設定検証ロジックが正しく動作する
- [ ] CLI コマンドが正しく実装されている
- [ ] 環境切り替えが適切に動作する

### 統合考慮事項
- [ ] 共通ライブラリとの統合が適切
- [ ] 既存設定システムとの互換性
- [ ] 環境間の設定継承が適切
- [ ] 外部サービスとの統合設定が適切

### 品質標準
- [ ] コーディング規約に準拠したコード品質
- [ ] 設定ファイルに適切なコメントが記載されている
- [ ] テストカバレッジが80%以上
- [ ] エラーメッセージが理解しやすい

### セキュリティと性能考慮事項
- [ ] 機密情報がファイルにハードコードされていない
- [ ] 本番環境でのセキュリティ設定が適切
- [ ] パスワードやシークレットがログに出力されない
- [ ] 設定検証がセキュリティリスクを検出する
- [ ] デフォルト設定がセキュア

### 保守性とドキュメント
- [ ] 環境設定のドキュメントが充実している
- [ ] トラブルシューティング情報が充実している
- [ ] 設定の変更方法が明確に記載されている
- [ ] 新しい環境追加の手順が明確

### 環境管理固有の観点
- [ ] 開発・ステージング・本番環境の分離が適切
- [ ] 環境切り替えが簡単で安全
- [ ] 設定ファイルのテンプレートが適切
- [ ] 環境別の設定値が適切に設定されている
- [ ] 設定検証が各環境に適切に対応している
- [ ] エクスポート機能がセキュリティを考慮している

## 次のタスクへの引き継ぎ

### Phase 2 への前提条件
- 環境別設定管理システムが確立済み
- 設定検証機能が動作済み
- セキュリティ設定が適切に管理されている

### 引き継ぎファイル
- `.env.example` - 設定テンプレート
- `.env.development` - 開発環境設定
- `.env.staging` - ステージング環境設定
- `.env.production` - 本番環境設定
- `package/shared/src/refnet_shared/config/environment.py` - 環境設定クラス
