# Task: バッチ処理・自動化システム

## タスクの目的

Celery Beatを使用した定期タスクスケジューリング、自動データ収集・処理、システムメンテナンス自動化を実装し、RefNetシステムの運用自動化を実現する。

## 前提条件

- Phase 3 が完了している
- Docker環境が構築済み
- 全サービスが正常稼働
- Celeryワーカーが利用可能

## 実施内容

### 1. Celery Beat スケジューラー設定

#### package/shared/src/refnet_shared/celery_app.py

```python
"""Celery アプリケーション設定."""

from celery import Celery
from celery.schedules import crontab
from refnet_shared.config.environment import load_environment_settings
import structlog


logger = structlog.get_logger(__name__)
settings = load_environment_settings()

# Celeryアプリケーション作成
celery_app = Celery(
    "refnet",
    broker=settings.celery_broker_url or settings.redis.url,
    backend=settings.celery_result_backend or settings.redis.url,
    include=[
        "refnet_shared.tasks.scheduled_tasks",
        "refnet_crawler.tasks",
        "refnet_summarizer.tasks",
        "refnet_generator.tasks"
    ]
)

# Celery設定
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1時間
    task_soft_time_limit=3300,  # 55分
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,

    # スケジュール設定
    beat_schedule={
        # 論文データ収集（毎日 2:00）
        "daily-paper-collection": {
            "task": "refnet.scheduled.collect_new_papers",
            "schedule": crontab(hour=2, minute=0),
            "kwargs": {"max_papers": 100}
        },

        # 要約生成（毎日 3:00）
        "daily-summarization": {
            "task": "refnet.scheduled.process_pending_summaries",
            "schedule": crontab(hour=3, minute=0),
            "kwargs": {"batch_size": 50}
        },

        # Markdown生成（毎日 4:00）
        "daily-markdown-generation": {
            "task": "refnet.scheduled.generate_markdown_files",
            "schedule": crontab(hour=4, minute=0),
            "kwargs": {"batch_size": 100}
        },

        # データベースメンテナンス（毎週日曜 1:00）
        "weekly-db-maintenance": {
            "task": "refnet.scheduled.database_maintenance",
            "schedule": crontab(hour=1, minute=0, day_of_week=0),
        },

        # システムヘルスチェック（30分毎）
        "system-health-check": {
            "task": "refnet.scheduled.system_health_check",
            "schedule": crontab(minute="*/30"),
        },

        # ログクリーンアップ（毎日 0:30）
        "daily-log-cleanup": {
            "task": "refnet.scheduled.cleanup_old_logs",
            "schedule": crontab(hour=0, minute=30),
            "kwargs": {"days_to_keep": 30}
        },

        # データバックアップ（毎日 1:00、本番環境のみ）
        "daily-backup": {
            "task": "refnet.scheduled.backup_database",
            "schedule": crontab(hour=1, minute=0),
            "options": {"queue": "backup"}
        } if settings.is_production() else {},

        # 統計レポート生成（毎週月曜 8:00）
        "weekly-stats-report": {
            "task": "refnet.scheduled.generate_stats_report",
            "schedule": crontab(hour=8, minute=0, day_of_week=1),
        }
    }
)


@celery_app.task(bind=True)
def debug_task(self):
    """デバッグタスク."""
    print(f'Request: {self.request!r}')
```

### 2. スケジュールタスク実装

#### package/shared/src/refnet_shared/tasks/scheduled_tasks.py

```python
"""スケジュールタスク実装."""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from celery import Task
from sqlalchemy.orm import Session
from refnet_shared.celery_app import celery_app
from refnet_shared.models.database import Paper, ProcessingQueue, Author
from refnet_shared.models.database_manager import db_manager
from refnet_shared.utils.metrics import MetricsCollector
import structlog


logger = structlog.get_logger(__name__)


class CallbackTask(Task):
    """コールバック付きタスク基底クラス."""

    def on_success(self, retval, task_id, args, kwargs):
        """タスク成功時のコールバック."""
        logger.info("Task completed successfully", task_id=task_id, task_name=self.name)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """タスク失敗時のコールバック."""
        logger.error("Task failed", task_id=task_id, task_name=self.name, error=str(exc))


@celery_app.task(base=CallbackTask, name="refnet.scheduled.collect_new_papers")
def collect_new_papers(max_papers: int = 100) -> Dict[str, Any]:
    """新しい論文の収集."""
    logger.info("Starting scheduled paper collection", max_papers=max_papers)

    try:
        with db_manager.get_session() as session:
            # 未処理の論文IDを取得
            pending_papers = session.query(Paper).filter(
                Paper.crawl_status == "pending"
            ).limit(max_papers).all()

            collected_count = 0

            for paper in pending_papers:
                # クローラータスクをキューに追加
                from refnet_crawler.tasks import crawl_paper_task
                crawl_paper_task.delay(paper.paper_id)
                collected_count += 1

            logger.info("Paper collection scheduled", count=collected_count)

            return {
                "status": "success",
                "papers_scheduled": collected_count,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error("Failed to collect new papers", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(base=CallbackTask, name="refnet.scheduled.process_pending_summaries")
def process_pending_summaries(batch_size: int = 50) -> Dict[str, Any]:
    """未要約論文の処理."""
    logger.info("Starting scheduled summarization", batch_size=batch_size)

    try:
        with db_manager.get_session() as session:
            # 要約が必要な論文を取得
            papers_to_summarize = session.query(Paper).filter(
                Paper.crawl_status == "completed",
                Paper.summary_status == "pending",
                Paper.pdf_url.isnot(None)
            ).limit(batch_size).all()

            processed_count = 0

            for paper in papers_to_summarize:
                # 要約タスクをキューに追加
                from refnet_summarizer.tasks import summarize_paper_task
                summarize_paper_task.delay(paper.paper_id)
                processed_count += 1

            logger.info("Summarization tasks scheduled", count=processed_count)

            return {
                "status": "success",
                "summaries_scheduled": processed_count,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error("Failed to process pending summaries", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(base=CallbackTask, name="refnet.scheduled.generate_markdown_files")
def generate_markdown_files(batch_size: int = 100) -> Dict[str, Any]:
    """Markdownファイルの生成."""
    logger.info("Starting scheduled markdown generation", batch_size=batch_size)

    try:
        with db_manager.get_session() as session:
            # Markdown生成が必要な論文を取得
            papers_to_generate = session.query(Paper).filter(
                Paper.summary_status == "completed"
            ).limit(batch_size).all()

            generated_count = 0

            for paper in papers_to_generate:
                # 生成タスクをキューに追加
                from refnet_generator.tasks import generate_markdown_task
                generate_markdown_task.delay(paper.paper_id)
                generated_count += 1

            logger.info("Markdown generation tasks scheduled", count=generated_count)

            return {
                "status": "success",
                "markdown_files_scheduled": generated_count,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error("Failed to generate markdown files", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(base=CallbackTask, name="refnet.scheduled.database_maintenance")
def database_maintenance() -> Dict[str, Any]:
    """データベースメンテナンス."""
    logger.info("Starting scheduled database maintenance")

    try:
        with db_manager.get_session() as session:
            maintenance_tasks = []

            # 古い処理キューエントリのクリーンアップ
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            deleted_queue_items = session.query(ProcessingQueue).filter(
                ProcessingQueue.created_at < cutoff_date,
                ProcessingQueue.status.in_(["completed", "failed"])
            ).delete()

            if deleted_queue_items > 0:
                maintenance_tasks.append(f"Cleaned up {deleted_queue_items} old queue items")

            # 統計情報の更新
            session.execute("ANALYZE;")
            maintenance_tasks.append("Updated database statistics")

            # 未使用インデックスの確認（ログのみ）
            # 実際の削除は手動で行う

            session.commit()

            logger.info("Database maintenance completed", tasks=maintenance_tasks)

            return {
                "status": "success",
                "maintenance_tasks": maintenance_tasks,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error("Database maintenance failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(base=CallbackTask, name="refnet.scheduled.system_health_check")
def system_health_check() -> Dict[str, Any]:
    """システムヘルスチェック."""
    logger.info("Starting system health check")

    try:
        health_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {},
            "metrics": {},
            "overall_status": "healthy"
        }

        with db_manager.get_session() as session:
            # データベース接続チェック
            try:
                session.execute("SELECT 1")
                health_status["services"]["database"] = "healthy"
            except Exception as e:
                health_status["services"]["database"] = f"unhealthy: {str(e)}"
                health_status["overall_status"] = "degraded"

            # Redis接続チェック
            try:
                from refnet_shared.middleware.rate_limiter import rate_limiter
                rate_limiter.redis_client.ping()
                health_status["services"]["redis"] = "healthy"
            except Exception as e:
                health_status["services"]["redis"] = f"unhealthy: {str(e)}"
                health_status["overall_status"] = "degraded"

            # データベースメトリクス取得
            total_papers = session.query(Paper).count()
            completed_summaries = session.query(Paper).filter(
                Paper.summary_status == "completed"
            ).count()

            health_status["metrics"] = {
                "total_papers": total_papers,
                "completed_summaries": completed_summaries,
                "completion_rate": completed_summaries / total_papers if total_papers > 0 else 0
            }

            # メトリクスの更新
            status_counts = {
                "crawl": {},
                "summary": {},
                "pdf": {}
            }

            for status_type in status_counts.keys():
                column = getattr(Paper, f"{status_type}_status")
                for status in ["pending", "completed", "failed"]:
                    count = session.query(Paper).filter(column == status).count()
                    status_counts[status_type][status] = count

            MetricsCollector.update_paper_counts(total_papers, status_counts)

        logger.info("System health check completed", status=health_status["overall_status"])

        return health_status

    except Exception as e:
        logger.error("System health check failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(base=CallbackTask, name="refnet.scheduled.cleanup_old_logs")
def cleanup_old_logs(days_to_keep: int = 30) -> Dict[str, Any]:
    """古いログのクリーンアップ."""
    logger.info("Starting log cleanup", days_to_keep=days_to_keep)

    try:
        import os
        import glob
        from pathlib import Path

        log_dirs = ["/var/log/refnet", "/app/logs", "./logs"]
        cleaned_files = []
        total_size_freed = 0

        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        for log_dir in log_dirs:
            if os.path.exists(log_dir):
                for log_file in glob.glob(f"{log_dir}/*.log*"):
                    file_path = Path(log_file)

                    # ファイル作成日時をチェック
                    if datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff_date:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        cleaned_files.append(str(file_path))
                        total_size_freed += file_size

        logger.info("Log cleanup completed",
                   files_cleaned=len(cleaned_files),
                   size_freed_mb=total_size_freed / (1024 * 1024))

        return {
            "status": "success",
            "files_cleaned": len(cleaned_files),
            "size_freed_bytes": total_size_freed,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error("Log cleanup failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(base=CallbackTask, name="refnet.scheduled.backup_database")
def backup_database() -> Dict[str, Any]:
    """データベースバックアップ."""
    logger.info("Starting database backup")

    try:
        import subprocess
        from refnet_shared.config.environment import load_environment_settings

        settings = load_environment_settings()

        if not settings.is_production():
            logger.info("Skipping backup in non-production environment")
            return {
                "status": "skipped",
                "reason": "non-production environment",
                "timestamp": datetime.utcnow().isoformat()
            }

        # バックアップファイル名
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = f"/backups/refnet_backup_{timestamp}.sql"

        # pg_dumpコマンド実行
        cmd = [
            "pg_dump",
            f"--host={settings.database.host}",
            f"--port={settings.database.port}",
            f"--username={settings.database.username}",
            f"--dbname={settings.database.database}",
            f"--file={backup_file}",
            "--no-password",
            "--verbose"
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = settings.database.password

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode == 0:
            # バックアップファイルサイズ取得
            backup_size = Path(backup_file).stat().st_size

            logger.info("Database backup completed",
                       backup_file=backup_file,
                       size_mb=backup_size / (1024 * 1024))

            return {
                "status": "success",
                "backup_file": backup_file,
                "size_bytes": backup_size,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            logger.error("Database backup failed", error=result.stderr)
            return {
                "status": "error",
                "error": result.stderr,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        logger.error("Database backup failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@celery_app.task(base=CallbackTask, name="refnet.scheduled.generate_stats_report")
def generate_stats_report() -> Dict[str, Any]:
    """統計レポート生成."""
    logger.info("Starting stats report generation")

    try:
        with db_manager.get_session() as session:
            # 基本統計
            total_papers = session.query(Paper).count()
            total_authors = session.query(Author).count()

            # 処理状況統計
            crawl_completed = session.query(Paper).filter(Paper.crawl_status == "completed").count()
            summary_completed = session.query(Paper).filter(Paper.summary_status == "completed").count()

            # 最近1週間の処理数
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_papers = session.query(Paper).filter(Paper.created_at >= week_ago).count()

            # 年別論文分布
            year_distribution = {}
            year_stats = session.query(Paper.year, Paper.year).group_by(Paper.year).all()
            for year, count in year_stats:
                if year:
                    year_distribution[str(year)] = count

            report = {
                "timestamp": datetime.utcnow().isoformat(),
                "summary": {
                    "total_papers": total_papers,
                    "total_authors": total_authors,
                    "crawl_completion_rate": crawl_completed / total_papers if total_papers > 0 else 0,
                    "summary_completion_rate": summary_completed / total_papers if total_papers > 0 else 0,
                    "recent_papers_week": recent_papers
                },
                "year_distribution": year_distribution,
                "processing_status": {
                    "crawl_completed": crawl_completed,
                    "summary_completed": summary_completed,
                    "crawl_pending": total_papers - crawl_completed,
                    "summary_pending": crawl_completed - summary_completed
                }
            }

        # レポートファイル保存
        report_file = f"/app/output/stats_report_{datetime.utcnow().strftime('%Y%m%d')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info("Stats report generated", report_file=report_file)

        return {
            "status": "success",
            "report_file": report_file,
            "stats": report["summary"],
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error("Stats report generation failed", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
```

### 3. バッチ処理管理CLI

#### package/shared/src/refnet_shared/cli_batch.py

```python
"""バッチ処理管理CLI."""

import click
from celery import current_app
from refnet_shared.celery_app import celery_app
from refnet_shared.tasks.scheduled_tasks import *
import structlog


logger = structlog.get_logger(__name__)


@click.group()
def batch():
    """バッチ処理管理."""
    pass


@batch.command()
def status():
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
@click.argument('task_name')
def run(task_name: str):
    """指定されたタスクを即座に実行."""
    task_mapping = {
        "collect-papers": collect_new_papers,
        "process-summaries": process_pending_summaries,
        "generate-markdown": generate_markdown_files,
        "db-maintenance": database_maintenance,
        "health-check": system_health_check,
        "cleanup-logs": cleanup_old_logs,
        "backup-db": backup_database,
        "stats-report": generate_stats_report
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
def schedule():
    """現在のスケジュール設定を表示."""
    schedule = celery_app.conf.beat_schedule

    click.echo("Scheduled Tasks:")
    for name, config in schedule.items():
        click.echo(f"  {name}:")
        click.echo(f"    Task: {config['task']}")
        click.echo(f"    Schedule: {config['schedule']}")
        if 'kwargs' in config:
            click.echo(f"    Args: {config['kwargs']}")


@batch.command()
@click.option('--worker', default=None, help='Specific worker to purge')
def purge(worker: str):
    """タスクキューをクリア."""
    if worker:
        celery_app.control.purge(worker)
        click.echo(f"Purged tasks for worker: {worker}")
    else:
        celery_app.control.purge()
        click.echo("Purged all tasks")


@batch.command()
@click.argument('task_id')
def revoke(task_id: str):
    """タスクを取り消し."""
    celery_app.control.revoke(task_id, terminate=True)
    click.echo(f"Revoked task: {task_id}")


@batch.command()
@click.option('--days', default=7, help='Number of days to look back')
def history(days: int):
    """タスク実行履歴表示."""
    # 実際の実装では、タスク実行履歴をデータベースに保存し、
    # ここで表示する必要がある
    click.echo(f"Task history for the last {days} days:")
    click.echo("(Implementation needed: store task history in database)")


if __name__ == '__main__':
    batch()
```

### 4. Docker設定更新

#### Dockerfile.beat (Celery Beat用)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# システム依存関係
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係
COPY pyproject.toml uv.lock ./
RUN pip install uv
RUN uv sync --frozen

# アプリケーションコピー
COPY src/ ./src/

# 環境変数
ENV PYTHONPATH=/app/src

# Celery Beat用ディレクトリ作成
RUN mkdir -p /app/celerybeat

# 起動コマンド
CMD ["celery", "-A", "refnet_shared.celery_app", "beat", "--loglevel=info", "--pidfile=/app/celerybeat/celerybeat.pid", "--schedule=/app/celerybeat/celerybeat-schedule"]
```

### 5. 監視・アラート統合

#### package/shared/src/refnet_shared/tasks/monitoring_tasks.py

```python
"""監視・アラート統合タスク."""

from celery import Task
from refnet_shared.celery_app import celery_app
from refnet_shared.utils.metrics import MetricsCollector
import structlog


logger = structlog.get_logger(__name__)


class MonitoringTask(Task):
    """監視機能付きタスク基底クラス."""

    def on_success(self, retval, task_id, args, kwargs):
        """タスク成功時の監視メトリクス更新."""
        MetricsCollector.track_task(self.name, "SUCCESS")
        logger.info("Task completed", task_name=self.name, task_id=task_id)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """タスク失敗時の監視メトリクス更新."""
        MetricsCollector.track_task(self.name, "FAILURE")
        logger.error("Task failed", task_name=self.name, task_id=task_id, error=str(exc))

        # 重要なタスクの失敗時はアラート送信
        critical_tasks = [
            "refnet.scheduled.database_maintenance",
            "refnet.scheduled.backup_database"
        ]

        if self.name in critical_tasks:
            # アラート送信ロジック
            self._send_alert(f"Critical task failed: {self.name}", str(exc))

    def _send_alert(self, subject: str, message: str):
        """アラート送信."""
        # 実際の実装では、メール・Slack・Webhookなどにアラート送信
        logger.critical("ALERT", subject=subject, message=message)


# 既存のタスクを監視機能付きに変更
@celery_app.task(base=MonitoringTask, name="refnet.scheduled.critical_system_check")
def critical_system_check() -> Dict[str, Any]:
    """重要なシステムチェック."""
    # データベース接続、Redis接続、ディスク容量など
    # 重要なシステム要素をチェック
    pass
```

### 6. テスト

#### tests/test_batch_automation.py

```python
"""バッチ自動化テスト."""

import pytest
from celery.result import EagerResult
from refnet_shared.tasks.scheduled_tasks import *
from refnet_shared.celery_app import celery_app


class TestBatchAutomation:
    """バッチ自動化テスト."""

    def test_collect_new_papers_task(self):
        """新規論文収集タスクテスト."""
        # Celeryをeagerモードに設定
        celery_app.conf.task_always_eager = True

        result = collect_new_papers.delay(max_papers=10)
        assert isinstance(result, EagerResult)
        assert result.successful()

        response = result.get()
        assert response["status"] == "success"
        assert "papers_scheduled" in response

    def test_system_health_check_task(self):
        """システムヘルスチェックタスクテスト."""
        celery_app.conf.task_always_eager = True

        result = system_health_check.delay()
        assert result.successful()

        response = result.get()
        assert "services" in response
        assert "metrics" in response
        assert "overall_status" in response

    def test_database_maintenance_task(self):
        """データベースメンテナンスタスクテスト."""
        celery_app.conf.task_always_eager = True

        result = database_maintenance.delay()
        assert result.successful()

        response = result.get()
        assert response["status"] == "success"
        assert "maintenance_tasks" in response

    @pytest.mark.slow
    def test_beat_schedule_configuration(self):
        """Beat スケジュール設定テスト."""
        schedule = celery_app.conf.beat_schedule

        # 必要なスケジュールタスクが設定されているかチェック
        required_tasks = [
            "daily-paper-collection",
            "daily-summarization",
            "daily-markdown-generation",
            "weekly-db-maintenance",
            "system-health-check"
        ]

        for task_name in required_tasks:
            assert task_name in schedule, f"Missing scheduled task: {task_name}"
            assert "task" in schedule[task_name]
            assert "schedule" in schedule[task_name]

    def test_cleanup_old_logs_task(self):
        """ログクリーンアップタスクテスト."""
        celery_app.conf.task_always_eager = True

        result = cleanup_old_logs.delay(days_to_keep=7)
        assert result.successful()

        response = result.get()
        assert response["status"] == "success"
        assert "files_cleaned" in response
```

## スコープ

- Celery Beat による定期タスクスケジューリング
- 自動論文収集・要約・生成処理
- システムメンテナンス自動化
- ヘルスチェック・監視自動化
- バッチ処理管理CLI

**スコープ外:**
- 高度なワークフロー管理（Airflow等）
- 複雑な依存関係管理
- リアルタイムストリーミング処理
- 大規模分散処理

## 参照するドキュメント

- `/docs/automation/scheduling.md`
- `/docs/automation/maintenance.md`
- `/docs/development/coding-standards.md`

## 完了条件

### 必須条件
- [ ] Celery Beat スケジューラーが動作
- [ ] 定期タスクが適切にスケジュールされている
- [ ] バッチ処理管理CLIが動作
- [ ] システムヘルスチェックが動作
- [ ] データベースメンテナンスが動作
- [ ] ログクリーンアップが動作

### 自動化条件
- [ ] 論文収集の自動化
- [ ] 要約生成の自動化
- [ ] Markdown生成の自動化
- [ ] データベースバックアップの自動化
- [ ] システム監視の自動化

### テスト条件
- [ ] バッチタスクのテストが作成されている
- [ ] スケジュール設定のテストが成功
- [ ] タスク実行のテストが成功
- [ ] エラーハンドリングのテストが成功

## トラブルシューティング

### よくある問題

1. **スケジューラーが動作しない**
   - 解決策: Celery Beat プロセス、設定ファイルを確認

2. **タスクが実行されない**
   - 解決策: ワーカープロセス、キュー設定を確認

3. **バックアップが失敗する**
   - 解決策: ディスク容量、権限設定を確認

4. **メンテナンスタスクでエラー**
   - 解決策: データベース接続、ロック状況を確認

## 次のタスクへの引き継ぎ

### Phase 4 完了への前提条件
- バッチ自動化システムが正常稼働
- 全定期タスクが適切に実行
- 監視・アラートが統合済み

### 引き継ぎファイル
- `package/shared/src/refnet_shared/celery_app.py` - Celery設定
- `package/shared/src/refnet_shared/tasks/` - スケジュールタスク
- `package/shared/src/refnet_shared/cli_batch.py` - 管理CLI
- バッチ処理設定・テスト
