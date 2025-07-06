"""環境設定管理."""

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import field_validator

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
        "extra": "allow",
    }

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: Any) -> Environment:
        """環境値の検証.

        Args:
            v: 検証対象の値

        Returns:
            Environment: 検証済みの環境値

        Raises:
            ValueError: 無効な環境値の場合
        """
        if isinstance(v, str):
            try:
                return Environment(v.lower())
            except ValueError as e:
                raise ValueError(f"Invalid environment: {v}") from e
        if isinstance(v, Environment):
            return v
        raise ValueError(f"Invalid environment type: {type(v)}")

    def is_development(self) -> bool:
        """開発環境かどうか.

        Returns:
            bool: 開発環境の場合 True
        """
        return self.environment == Environment.DEVELOPMENT

    def is_staging(self) -> bool:
        """ステージング環境かどうか.

        Returns:
            bool: ステージング環境の場合 True
        """
        return self.environment == Environment.STAGING

    def is_production(self) -> bool:
        """本番環境かどうか.

        Returns:
            bool: 本番環境の場合 True
        """
        return self.environment == Environment.PRODUCTION

    def is_testing(self) -> bool:
        """テスト環境かどうか.

        Returns:
            bool: テスト環境の場合 True
        """
        return self.environment == Environment.TESTING


class ConfigValidator:
    """設定検証クラス."""

    def __init__(self, settings: EnvironmentSettings) -> None:
        """初期化.

        Args:
            settings: 検証対象の設定
        """
        self.settings = settings
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_all(self) -> None:
        """全設定の検証.

        Raises:
            ConfigurationError: 設定エラーがある場合
        """
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
                self.errors.append(
                    "Either OPENAI_API_KEY or ANTHROPIC_API_KEY must be set in production"
                )

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
    """環境設定の読み込み.

    Returns:
        EnvironmentSettings: 読み込まれた環境設定

    Raises:
        ConfigurationError: 設定エラーがある場合
    """
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
            warnings.warn(f"Configuration warning: {warning}", stacklevel=2)

    return settings
