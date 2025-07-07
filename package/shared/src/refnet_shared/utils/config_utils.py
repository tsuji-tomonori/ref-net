"""設定管理ユーティリティ."""

import json
import os
from pathlib import Path
from typing import Any

from refnet_shared.config.environment import Environment, EnvironmentSettings


def get_env_file_path(environment: Environment) -> Path:
    """環境ファイルパス取得."""
    return Path(f".env.{environment.value}")


def create_env_file_from_template(environment: Environment, overrides: dict[str, Any] | None = None) -> None:
    """テンプレートから環境ファイル作成."""
    template_path = Path(".env.example")
    env_path = get_env_file_path(environment)

    if not template_path.exists():
        raise FileNotFoundError("Template file .env.example not found")

    # テンプレートの読み込み
    with open(template_path) as f:
        content = f.read()

    # 環境固有の値を設定
    if overrides:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "=" in line and not line.strip().startswith("#"):
                key = line.split("=")[0].strip()
                if key in overrides:
                    lines[i] = f"{key}={overrides[key]}"
        content = "\n".join(lines)

    # ファイル作成
    with open(env_path, "w") as f:
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

    with open(output_path, "w") as f:
        json.dump(safe_settings, f, indent=2)


def check_required_env_vars(environment: Environment) -> dict[str, bool]:
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
