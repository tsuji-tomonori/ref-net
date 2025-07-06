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
from refnet_shared.utils.migration_utils import migration_manager


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


@main.group()
def migrate() -> None:
    """データベースマイグレーション管理."""
    pass


@migrate.command()
@click.argument('message')
@click.option(
    '--autogenerate/--no-autogenerate',
    default=True,
    help='Auto-generate migration from model changes'
)
def create_migration(message: str, autogenerate: bool) -> None:
    """新しいマイグレーション作成."""
    try:
        revision_id = migration_manager.create_migration(message, autogenerate)
        click.echo(f"✅ Migration created: {revision_id}")
    except Exception as e:
        click.echo(f"❌ Migration creation failed: {e}")
        exit(1)


@migrate.command()
@click.option('--revision', default='head', help='Target revision (default: head)')
@click.option('--backup/--no-backup', default=True, help='Create backup before migration')
def upgrade(revision: str, backup: bool) -> None:
    """マイグレーション実行."""
    try:
        if backup:
            backup_file = migration_manager.backup_before_migration()
            if backup_file:
                click.echo(f"📁 Backup created: {backup_file}")

        migration_manager.run_migrations(revision)
        click.echo(f"✅ Migrations applied to: {revision}")
    except Exception as e:
        click.echo(f"❌ Migration failed: {e}")
        exit(1)


@migrate.command()
@click.argument('revision')
@click.option('--confirm', is_flag=True, help='Confirm downgrade operation')
def downgrade(revision: str, confirm: bool) -> None:
    """マイグレーションのダウングレード."""
    if not confirm:
        click.echo("⚠️  Downgrade operation requires --confirm flag")
        exit(1)

    try:
        migration_manager.downgrade(revision)
        click.echo(f"✅ Downgraded to: {revision}")
    except Exception as e:
        click.echo(f"❌ Downgrade failed: {e}")
        exit(1)


@migrate.command()
def status() -> None:
    """マイグレーション状態表示."""
    try:
        validation = migration_manager.validate_migrations()

        click.echo(f"Status: {validation['status']}")
        click.echo(f"Current revision: {validation['current_revision'] or 'None'}")
        click.echo(f"Available migrations: {validation['available_migrations']}")
        click.echo(f"Pending migrations: {validation['pending_migrations']}")

        if validation['issues']:
            click.echo("\n⚠️  Issues:")
            for issue in validation['issues']:
                click.echo(f"  - {issue}")

        if validation['status'] != 'valid':
            exit(1)

    except Exception as e:
        click.echo(f"❌ Status check failed: {e}")
        exit(1)


@migrate.command()
def history() -> None:
    """マイグレーション履歴表示."""
    try:
        history = migration_manager.get_migration_history()

        if not history:
            click.echo("No migrations found")
            return

        click.echo("Migration History:")
        for migration in history:
            status = "→ CURRENT" if migration['is_current'] else ""
            click.echo(f"  {migration['revision_id']}: {migration['message']} {status}")

    except Exception as e:
        click.echo(f"❌ History retrieval failed: {e}")
        exit(1)


@migrate.command()
@click.option('--confirm', is_flag=True, help='Confirm database reset')
def reset(confirm: bool) -> None:
    """データベースリセット（危険な操作）."""
    if not confirm:
        click.echo("⚠️  Database reset requires --confirm flag")
        click.echo("This operation will DELETE ALL DATA!")
        exit(1)

    try:
        migration_manager.reset_database(confirm=True)
        click.echo("✅ Database reset completed")
    except Exception as e:
        click.echo(f"❌ Database reset failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
