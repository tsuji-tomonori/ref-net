"""共通ライブラリCLI."""

from pathlib import Path

import click

from refnet_shared.config import settings
from refnet_shared.config.environment import ConfigValidator, Environment, load_environment_settings
from refnet_shared.utils import get_app_info, setup_logging, validate_required_settings
from refnet_shared.utils.config_utils import (
    check_required_env_vars,
    create_env_file_from_template,
    export_settings_to_json,
)


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


@main.group()
def env() -> None:
    """環境設定管理."""
    pass


@env.command()
@click.argument("environment", type=click.Choice(["development", "staging", "production"]))
def create(environment: str) -> None:
    """環境設定ファイル作成.

    Args:
        environment: 作成する環境設定ファイルの種別
    """
    env_enum = Environment(environment)
    try:
        create_env_file_from_template(env_enum)
        click.echo(f"✅ Created .env.{environment} from template")
    except FileNotFoundError as e:
        click.echo(f"❌ Error: {e}")
        exit(1)


@env.command("validate")
def env_validate() -> None:
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
@click.option("--output", "-o", default="config.json", help="Output file path")
def export(output: str) -> None:
    """設定をJSONファイルにエクスポート.

    Args:
        output: 出力ファイルパス
    """
    try:
        settings = load_environment_settings()
        export_settings_to_json(settings, Path(output))
        click.echo(f"✅ Settings exported to {output}")
    except Exception as e:
        click.echo(f"❌ Export error: {e}")
        exit(1)


@env.command()
@click.argument("environment", type=click.Choice(["development", "staging", "production"]))
def check(environment: str) -> None:
    """必須環境変数をチェック.

    Args:
        environment: チェック対象の環境
    """
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


if __name__ == "__main__":
    main()
