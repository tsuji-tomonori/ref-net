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
