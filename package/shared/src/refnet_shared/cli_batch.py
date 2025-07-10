"""バッチ処理管理CLI."""

import click
import structlog

from refnet_shared.celery_app import celery_app
from refnet_shared.tasks.scheduled_tasks import (
    backup_database,
    cleanup_old_logs,
    collect_new_papers,
    database_maintenance,
    generate_markdown_files,
    generate_stats_report,
    process_pending_summaries,
    system_health_check,
)

logger = structlog.get_logger(__name__)


@click.group()
def batch() -> None:
    """バッチ処理管理."""
    pass


@batch.command()
def status() -> None:
    """スケジュールタスクの状態表示."""
    i = celery_app.control.inspect()

    # アクティブなタスク
    active_tasks = i.active()
    if active_tasks:
        click.echo("Active Tasks:")
        for worker, tasks in active_tasks.items():
            click.echo(f"  Worker: {worker}")
            for task in tasks:
                click.echo(f"    - {task['name']} (ID: {task['id']})")
    else:
        click.echo("No active tasks")

    # スケジュールされたタスク
    scheduled_tasks = i.scheduled()
    if scheduled_tasks:
        click.echo("\nScheduled Tasks:")
        for worker, tasks in scheduled_tasks.items():
            click.echo(f"  Worker: {worker}")
            for task in tasks:
                click.echo(f"    - {task['request']['task']} at {task['eta']}")


@batch.command()
@click.argument("task_name")
def run(task_name: str) -> None:
    """指定されたタスクを即座に実行."""
    task_mapping = {
        "collect-papers": collect_new_papers,
        "process-summaries": process_pending_summaries,
        "generate-markdown": generate_markdown_files,
        "db-maintenance": database_maintenance,
        "health-check": system_health_check,
        "cleanup-logs": cleanup_old_logs,
        "backup-db": backup_database,
        "stats-report": generate_stats_report,
    }

    if task_name not in task_mapping:
        click.echo(f"Unknown task: {task_name}")
        click.echo(f"Available tasks: {', '.join(task_mapping.keys())}")
        return

    task = task_mapping[task_name]
    click.echo(f"Running task: {task_name}")

    result = task.delay()
    click.echo(f"Task submitted with ID: {result.id}")


@batch.command()
def schedule() -> None:
    """現在のスケジュール設定を表示."""
    schedule = celery_app.conf.beat_schedule

    click.echo("Scheduled Tasks:")
    for name, config in schedule.items():
        click.echo(f"  {name}:")
        click.echo(f"    Task: {config['task']}")
        click.echo(f"    Schedule: {config['schedule']}")
        if "kwargs" in config:
            click.echo(f"    Args: {config['kwargs']}")


@batch.command()
@click.option("--worker", default=None, help="Specific worker to purge")
def purge(worker: str) -> None:
    """タスクキューをクリア."""
    if worker:
        celery_app.control.purge(worker)
        click.echo(f"Purged tasks for worker: {worker}")
    else:
        celery_app.control.purge()
        click.echo("Purged all tasks")


@batch.command()
@click.argument("task_id")
def revoke(task_id: str) -> None:
    """タスクを取り消し."""
    celery_app.control.revoke(task_id, terminate=True)
    click.echo(f"Revoked task: {task_id}")


@batch.command()
@click.option("--days", default=7, help="Number of days to look back")
def history(days: int) -> None:
    """タスク実行履歴表示."""
    # 実際の実装では、タスク実行履歴をデータベースに保存し、
    # ここで表示する必要がある
    click.echo(f"Task history for the last {days} days:")
    click.echo("(Implementation needed: store task history in database)")


if __name__ == "__main__":
    batch()
