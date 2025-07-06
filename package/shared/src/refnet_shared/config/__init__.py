"""設定管理モジュール."""

from typing import Any

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
        return (
            f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        )


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

    def __init__(self, **kwargs: Any) -> None:
        """初期化.

        Args:
            **kwargs: Pydantic BaseSettingsに渡される設定値
                     環境変数やファイルからの設定値を動的に受け取るため Any 型を使用
        """
        super().__init__(**kwargs)

        # Celery URLのデフォルト設定
        if not self.celery_broker_url:
            self.celery_broker_url = self.redis.url
        if not self.celery_result_backend:
            self.celery_result_backend = self.redis.url


# グローバル設定インスタンス
settings = Settings()
